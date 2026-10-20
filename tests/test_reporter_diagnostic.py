import hashlib
import json

import pytest

from claimcascade.core import total
from claimcascade.schemas import Report
from claimcascade.synthetic import generate
from scripts.diagnose_challenger import prepare as prepare_challenger
from scripts.diagnose_reporter import prepare
from scripts.assemble_recovered import assemble, markdown
from scripts.import_recovered import import_pending
from claimcascade.persistence import Store


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
    reporter = tmp_path/'reporter.json'
    reporter_data = dict(status='complete', stage='reporter', seed=42, held_out=False,
        claim_count=50, model='gemini-3.5-flash', request_policy=dict(temperature=1.0, thinking_level='LOW'),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        challenger_source_sha256=hashlib.sha256(challenger.read_bytes()).hexdigest(),
        payload_sha256=hashlib.sha256(json.dumps(request[3]).encode()).hexdigest(),
        schema_validated_outputs={'reporter':{'explanations':[explanation]}})
    reporter.write_text(json.dumps(reporter_data))
    recovered = assemble(source, challenger, reporter)
    assert recovered['status'] == 'recovered_complete'
    assert recovered['reviewer_approved'] is False
    assert recovered['totals']['event-a'] == total(claims, members)
    assert 'Unresolved' in markdown(recovered)
    assert 'not a fresh end-to-end run' in markdown(recovered)
    assert ', '.join(members) in markdown(recovered)
    review_draft = dict(status='pending_human_review', reviewer_approved=False,
        source_hashes=recovered['sources'], review_payload=dict(groups=[dict(cluster_id='event-a',
            members=members, decision='pending', note='Review needed')], duplicates={}, dismissed_duplicates=[]))
    database = tmp_path/'recovered.db'
    run_id, created = import_pending(recovered, review_draft, database)
    assert created
    store = Store('sqlite:///'+str(database))
    assert store.history(run_id)[0]['payload']['groups'][0]['decision'] == 'pending'
    store.save_review(run_id, dict(review_draft['review_payload'], reviewer_note='Later revision'))
    assert import_pending(recovered, review_draft, database) == (run_id, False)
    assert len(store.list_runs()) == 1 and len(store.history(run_id)) == 2
    review_draft['review_payload']['groups'][0]['decision'] = 'approved'
    with pytest.raises(ValueError, match='cannot approve'):
        import_pending(recovered, review_draft, database)
    store.engine.dispose()
    reporter_data['payload_sha256'] = 'wrong'
    reporter.write_text(json.dumps(reporter_data))
    with pytest.raises(ValueError, match='not linked'):
        assemble(source, challenger, reporter)
    reporter_data['payload_sha256'] = hashlib.sha256(json.dumps(request[3]).encode()).hexdigest()
    reporter_data['schema_validated_outputs']['reporter']['explanations'][0]['hypotheses'] = [
        dict(text='Unproven', claim_ids=[claims[2].claim_id])]
    reporter.write_text(json.dumps(reporter_data))
    with pytest.raises(ValueError, match='invalid membership'):
        assemble(source, challenger, reporter)
    for explanations in [[], [explanation, explanation], [dict(explanation, cluster_id='wrong')]]:
        with pytest.raises(ValueError, match='exactly'):
            request[4](Report(explanations=explanations))
    checkpoint['payload_sha256'] = 'wrong'
    challenger.write_text(json.dumps(checkpoint))
    with pytest.raises(ValueError, match='not linked'):
        prepare(source, challenger)
