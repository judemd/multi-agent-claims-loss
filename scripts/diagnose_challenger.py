"""Rebuild and validate the failed synthetic challenger input before one diagnostic."""
import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from claimcascade.agents import narrative_schema
from claimcascade.core import candidates, validate_evidence, validate_proposals
from claimcascade.schemas import Challenge, Proposals, Settings
from claimcascade.synthetic import generate
from scripts.diagnose_adk_batch import diagnose

INSTRUCTION = 'Challenge timing, location, unsupported cause, chain merging and suspected duplicates. Suggest changes but do not alter membership.'


def prepare(source):
    data = json.loads(source.read_text(encoding='utf-8'))
    expected = dict(seed=42, held_out=False, claim_count=50, model='gemini-3.5-flash')
    if any(data.get(k) != v for k, v in expected.items()):
        raise ValueError('Checkpoint dataset or model differs')
    if any(data.get('request_policy', {}).get(k) != v for k, v in
           [('temperature', 1.0), ('thinking_level', 'LOW')]):
        raise ValueError('Checkpoint generation settings differ')
    claims, bulletins, _ = generate(42, False)
    outputs = data['schema_validated_outputs']
    facts = []
    for index in range(5):
        batch = claims[index*10:index*10+10]
        output = narrative_schema(batch).model_validate(outputs[f'extractor_{index}'])
        validate_evidence(output.facts, batch)
        facts.extend(f.model_dump() for f in output.facts)
    proposals = validate_proposals(Proposals.model_validate(outputs['investigator']), claims)
    payload = dict(claims=[c.model_dump(mode='json') for c in claims], facts=facts,
                   bulletins=[b.model_dump(mode='json') for b in bulletins],
                   candidate_edges=candidates(claims, Settings()), proposals=proposals.model_dump())

    def validate(output):
        lookup = {c.cluster_id:c for c in proposals.clusters}
        for objection in output.objections:
            if objection.cluster_id not in lookup:
                raise ValueError('Challenge references unknown cluster')
            members = set(lookup[objection.cluster_id].members)
            flat = [m for group in objection.suggested_splits for m in group]
            if not set(objection.suggested_removals) <= members or not set(flat) <= members or len(flat) != len(set(flat)):
                raise ValueError('Challenge references invalid membership')
    return ('challenger', INSTRUCTION, Challenge, payload, validate)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--inspect-only', action='store_true')
    args = parser.parse_args()
    prepared = prepare(args.source)
    sizes = {k:len(json.dumps(v).encode()) for k, v in prepared[3].items()}
    provenance = dict(source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
                      payload_sha256=hashlib.sha256(json.dumps(prepared[3]).encode()).hexdigest(),
                      component_bytes=sizes)
    if args.inspect_only:
        print(json.dumps(provenance, indent=2))
        return
    result = await diagnose(prepared=prepared)
    result.update(provenance)
    folder = Path('data/live-tests')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-challenger-diagnostic.json')
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(result_file=str(path), status=result['status'], sdk_calls=result['sdk_calls'])))


if __name__ == '__main__':
    asyncio.run(main())
