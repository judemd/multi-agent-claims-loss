"""Offline baseline benchmark over held-out seeds; never invokes a model."""
import json

from claimcascade.core import baseline, candidates
from claimcascade.evaluation import evaluate
from claimcascade.schemas import Settings
from claimcascade.synthetic import generate


if __name__ == '__main__':
    rows = []
    for seed in range(100,105):
        claims, _, truth = generate(seed,True)
        edges = candidates(claims,Settings())
        metrics = evaluate(baseline(claims,edges),edges,truth,[c.claim_id for c in claims])
        rows.append(dict(seed=seed,**{k:v for k,v in metrics.items() if k not in ['incorrect_merges','missed_connections']},
                         incorrect_merge_count=len(metrics['incorrect_merges']),missed_connection_count=len(metrics['missed_connections'])))
    print(json.dumps(rows,indent=2))
