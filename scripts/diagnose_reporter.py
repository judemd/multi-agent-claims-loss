"""Validate linked synthetic checkpoints and prepare one operator-only reporter call."""
import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from claimcascade.core import total
from claimcascade.schemas import Challenge, Report
from claimcascade.synthetic import generate
from scripts.diagnose_adk_batch import diagnose
from scripts.diagnose_challenger import prepare as prepare_challenger

INSTRUCTION = 'Explain each proposal separating observed facts, hypotheses and missing information. Objections remain unresolved for the reviewer. Do not calculate or invent amounts.'


def prepare(source, challenger_source):
    challenger_input = prepare_challenger(source)
    data = json.loads(challenger_source.read_text(encoding='utf-8'))
    expected = dict(status='complete', stage='challenger', seed=42, held_out=False,
                    claim_count=50, model='gemini-3.5-flash')
    if any(data.get(k) != v for k, v in expected.items()):
        raise ValueError('Challenger checkpoint identity or status differs')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    input_hash = hashlib.sha256(json.dumps(challenger_input[3]).encode()).hexdigest()
    if data.get('source_sha256') != source_hash or data.get('payload_sha256') != input_hash:
        raise ValueError('Challenger checkpoint is not linked to this investigation')
    if any(data.get('request_policy', {}).get(k) != v for k, v in
           [('temperature', 1.0), ('thinking_level', 'LOW')]):
        raise ValueError('Challenger generation settings differ')
    challenge = Challenge.model_validate(data['schema_validated_outputs']['challenger'])
    challenger_input[4](challenge)
    claims, _, _ = generate(42, False)
    proposals = challenger_input[3]['proposals']
    totals = {c['cluster_id']:total(claims, c['members']) for c in proposals['clusters']}
    payload = dict(proposals=proposals, challenge=challenge.model_dump(), totals=totals)

    def validate(output):
        ids = {c['cluster_id'] for c in proposals['clusters']}
        if {e.cluster_id for e in output.explanations} != ids or len(output.explanations) != len(ids):
            raise ValueError('Reporter must explain exactly the proposed clusters')
    return ('reporter', INSTRUCTION, Report, payload, validate)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('challenger_source', type=Path)
    parser.add_argument('--inspect-only', action='store_true')
    args = parser.parse_args()
    prepared = prepare(args.source, args.challenger_source)
    provenance = dict(source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
        challenger_source_sha256=hashlib.sha256(args.challenger_source.read_bytes()).hexdigest(),
        payload_sha256=hashlib.sha256(json.dumps(prepared[3]).encode()).hexdigest(),
        component_bytes={k:len(json.dumps(v).encode()) for k, v in prepared[3].items()})
    if args.inspect_only:
        print(json.dumps(dict(**provenance, clusters=len(prepared[3]['proposals']['clusters']),
            objections=len(prepared[3]['challenge']['objections']), totals=prepared[3]['totals']), indent=2))
        return
    result = await diagnose(prepared=prepared)
    result.update(provenance)
    folder = Path('data/live-tests')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-reporter-diagnostic.json')
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(result_file=str(path), status=result['status'], sdk_calls=result['sdk_calls'])))


if __name__ == '__main__':
    asyncio.run(main())
