"""Explicit operator-only live test; never enabled by the public application."""
import json
import os
import argparse
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from claimcascade.agents import analyse_live
from claimcascade.core import baseline, candidates
from claimcascade.evaluation import evaluate
from claimcascade.schemas import Settings
from claimcascade.synthetic import generate
from claimcascade.requests import RequestPolicy, provider_status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--min-interval',type=float,default=30)
    parser.add_argument('--max-attempts',type=int,default=12)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--held-out',action='store_true')
    parser.add_argument('--claim-count',type=int,default=50,choices=range(1,51))
    parser.add_argument('--reuse-extractions',type=Path,action='append',default=[],help='Explicitly reuse source-validated extraction checkpoints only')
    args = parser.parse_args()
    # Request events below retain structured failures without repeated ADK stack traces.
    logging.getLogger('google_adk').setLevel(logging.CRITICAL)
    policy = RequestPolicy(min_interval_seconds=args.min_interval,max_attempts=args.max_attempts)
    claims, bulletins, truth = generate(args.seed,args.held_out)
    claims = claims[:args.claim_count]
    selected = {c.claim_id for c in claims}
    truth = dict(truth,events={k:v for k,v in truth['events'].items() if k in selected},
                 duplicates={k:v for k,v in truth['duplicates'].items() if k in selected and v in selected})
    edges = candidates(claims,Settings())
    stages = []
    def stage_started(stage):
        stages.append(stage)
        print(f'Stage: {stage}',flush=True)
    folder = Path('data/live-tests')
    folder.mkdir(parents=True,exist_ok=True)
    path = folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    recovered,provenance={},[]
    model=os.getenv('GEMINI_MODEL','gemini-3.5-flash')
    for source in args.reuse_extractions:
        data=json.loads(source.read_text(encoding='utf-8'))
        if any(data.get(k)!=v for k,v in [('seed',args.seed),('held_out',args.held_out),('claim_count',args.claim_count)]):
            raise ValueError('Checkpoint dataset identity differs')
        if data.get('model',model)!=model:
            raise ValueError('Checkpoint model differs')
        if any(data.get('request_policy',{}).get(k)!=getattr(policy,k) for k in ('temperature','thinking_level')):
            raise ValueError('Checkpoint generation settings differ')
        outputs={k:v for k,v in data.get('schema_validated_outputs',{}).items() if k.startswith('extractor_')}
        if not outputs or recovered.keys() & outputs.keys():
            raise ValueError('Checkpoint stages are absent or overlap')
        recovered.update(outputs)
        provenance.append({'file':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                           'stages':list(outputs),'model_recorded':data.get('model') is not None})
    progress = {'status':'running','claim_count':len(claims),'seed':args.seed,'held_out':args.held_out,
                'model':model,'checkpoint_sources':provenance,
                'request_policy':policy.model_dump(),'events':[],'schema_validated_outputs':dict(recovered),'telemetry':[]}
    def persist():
        path.write_text(json.dumps(progress,indent=2),encoding='utf-8')
    def request_event(event):
        progress['events'].append(event)
        persist()
        print(json.dumps(event),flush=True)
    def checkpoint(stage,output,telemetry):
        progress['schema_validated_outputs'][stage] = output
        progress['telemetry'] = telemetry
        persist()
    try:
        result = analyse_live(claims,bulletins,edges,os.getenv('GEMINI_MODEL','gemini-3.5-flash'),on_stage=stage_started,
                              request_policy=policy,on_request=request_event,on_checkpoint=checkpoint,completed_extractions=recovered)
    except Exception as error:
        evidence = {'status':'failed','stages_started':stages,'error_type':type(error).__name__,'provider_code':provider_status(error)}
        progress.update(evidence)
        persist()
        print(json.dumps(evidence,indent=2))
        return 1
    result['metrics'] = evaluate([c['members'] for c in result['proposals']['clusters']],edges,truth,[c.claim_id for c in claims])
    result['baseline_metrics'] = evaluate(baseline(claims,edges),edges,truth,[c.claim_id for c in claims])
    result['status']='complete'
    result.update(claim_count=len(claims),seed=args.seed,held_out=args.held_out)
    result.update(model=model,checkpoint_sources=provenance)
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'result_file':str(path),'clusters':len(result['proposals']['clusters']),
                      'logical_calls':len(result['telemetry']),'provider_attempts':len(result['request_attempts']),
                      'metrics':result['metrics'],'baseline_metrics':result['baseline_metrics']},indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
