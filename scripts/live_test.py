"""Explicit operator-only live test; never enabled by the public application."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from claimcascade.agents import analyse_live
from claimcascade.core import candidates
from claimcascade.evaluation import evaluate
from claimcascade.schemas import Settings
from claimcascade.synthetic import generate


def main():
    claims, bulletins, truth = generate()
    edges = candidates(claims,Settings())
    stages = []
    def stage_started(stage):
        stages.append(stage)
        print(f'Stage: {stage}',flush=True)
    folder = Path('data/live-tests')
    folder.mkdir(parents=True,exist_ok=True)
    path = folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    try:
        result = analyse_live(claims,bulletins,edges,os.getenv('GEMINI_MODEL','gemini-3.5-flash'),on_stage=stage_started)
    except Exception as error:
        evidence = {'status':'failed','stages_started':stages,'error_type':type(error).__name__,
                    'provider_code':429 if '429' in str(error) else None}
        path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        print(json.dumps(evidence,indent=2))
        return 1
    result['metrics'] = evaluate([c['members'] for c in result['proposals']['clusters']],edges,truth,[c.claim_id for c in claims])
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'result_file':str(path),'clusters':len(result['proposals']['clusters']),
                      'logical_calls':len(result['telemetry']),'metrics':result['metrics']},indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
