import hashlib
import json

import pytest

from claimcascade.core import total
from claimcascade.schemas import Report
from claimcascade.synthetic import generate
from scripts.diagnose_challenger import prepare as prepare_challenger
from scripts.diagnose_reporter import prepare


def test_reporter_rejects_mismatched_sources_and_incomplete_explanations(tmp_path):
    claims, _, _ = generate(42, False)
    members = [c.claim_id for c in claims[:2]]
    proposals = dict(clusters=[dict(cluster_id='event-a', description='Hypothesis', members=members,
        evidence=[dict(claim_id=c.claim_id, excerpt=c.narrative) for c in claims[:2]])],
        unassigned=[c.claim_id for c in claims[2:]])
    source = tmp_path/'source.json'
    source.write_text(json.dumps(dict(seed=42, held_out=False, claim_count=50,
        model='gemini-3.5-flash', request_policy=dict(temperature=1.0, thinking_level='LOW'),
        schema_validated_outputs={**{f'extractor_{i}':{'facts':[]} for i in range(5)},
                                   'investigator':proposals})))
    input_payload = prepare_challenger(source)[3]
    checkpoint = dict(status='complete', stage='challenger', seed=42, held_out=False,
        claim_count=50, model='gemini-3.5-flash',
        request_policy=dict(temperature=1.0, thinking_level='LOW'),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        payload_sha256=hashlib.sha256(json.dumps(input_payload).encode()).hexdigest(),
        schema_validated_outputs={'challenger':{'objections':[dict(cluster_id='event-a', concern='Unresolved')]}})
    challenger = tmp_path/'challenger.json'
    challenger.write_text(json.dumps(checkpoint))
    request = prepare(source, challenger)
    assert request[3]['totals']['event-a'] == total(claims, members)
    assert request[3]['challenge']['objections'][0]['concern'] == 'Unresolved'
    explanation = dict(cluster_id='event-a', observed_facts=[], hypotheses=[], missing_information=[])
    request[4](Report(explanations=[explanation]))
    for explanations in [[], [explanation, explanation], [dict(explanation, cluster_id='wrong')]]:
        with pytest.raises(ValueError, match='exactly'):
            request[4](Report(explanations=explanations))
    checkpoint['payload_sha256'] = 'wrong'
    challenger.write_text(json.dumps(checkpoint))
    with pytest.raises(ValueError, match='not linked'):
        prepare(source, challenger)
