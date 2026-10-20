"""Recheck a saved live result without making any model calls."""
import argparse
import json
import hashlib
from decimal import Decimal
from pathlib import Path

from claimcascade.core import validate_evidence, validate_proposals
from claimcascade.schemas import Extraction, Proposals
from claimcascade.synthetic import generate


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('result_file',type=Path)
    args=parser.parse_args()
    result=json.loads(args.result_file.read_text(encoding='utf-8'))
    if result.get('status')!='complete':
        raise ValueError('Only a completed run can be verified')
    claims,_,truth=generate(result['seed'],result['held_out'])
    claims=claims[:result['claim_count']]
    lookup={c.claim_id:c for c in claims}
    proposals=validate_proposals(Proposals.model_validate(result['proposals']),claims)
    facts=Extraction.model_validate({'facts':result['facts']})
    validate_evidence(facts.facts,claims)
    financial=[]
    for cluster in proposals.clusters:
        amounts=[lookup[c].reported_amount_gbp for c in cluster.members]
        # Independent integer-pence check of operational totals: suspected duplicates stay counted.
        expected_pence=sum(int(a*100) for a in amounts if a is not None)
        observed=result['totals'][cluster.cluster_id]
        if (int(Decimal(observed['known_amount_gbp'])*100)!=expected_pence
                or observed['missing_amount_count']!=sum(a is None for a in amounts)
                or observed['underlying_claim_count']!=len(cluster.members)
                or observed['label']!='Reported claim amount'):
            raise ValueError(f'Financial aggregation check failed: {cluster.cluster_id}')
        financial.append({'cluster_id':cluster.cluster_id,'members':len(cluster.members),
                          'missing_amounts':observed['missing_amount_count'],'arithmetic_correct':True})
    usage=[u for stage in result['telemetry'] for u in stage['usage']]
    reused_usage=[]
    for source in result.get('checkpoint_sources',[]):
        path=Path(source['file'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Checkpoint source file changed after recovery')
        saved=json.loads(path.read_text(encoding='utf-8'))
        reused_usage.extend(u for stage in saved.get('telemetry',[]) if stage['stage'] in source['stages'] for u in stage['usage'])
        if saved.get('usage'):
            reused_usage.append(saved['usage'])
    attempts=result['request_attempts']
    summary=dict(result_file=str(args.result_file),claim_count=len(claims),seed=result['seed'],held_out=result['held_out'],
        clusters=len(proposals.clusters),unassigned=len(result['proposals']['unassigned']),extracted_facts=len(facts.facts),
        challenger_objections=len(result['challenge']['objections']),
        evidence_and_membership_valid=True,financial_checks=financial,
        new_logical_calls=len(result['telemetry']),reused_extraction_stages=len(result.get('reused_extractions',{})),provider_attempts=len(attempts),
        failed_attempts=sum(a['status']!='complete' for a in attempts),
        recorded_stage_seconds=round(sum(t['latency_seconds'] for t in result['telemetry']),2),
        tokens={key:sum(u.get(key) or 0 for u in usage) for key in
                ['prompt_token_count','candidates_token_count','thoughts_token_count','total_token_count']},
        completed_stage_tokens_including_reuse={key:sum(u.get(key) or 0 for u in usage+reused_usage) for key in
                ['prompt_token_count','candidates_token_count','thoughts_token_count','total_token_count']},
        metrics=result['metrics'],baseline_metrics=result['baseline_metrics'])
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
