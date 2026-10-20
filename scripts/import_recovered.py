"""Import a validated recovered fixture and pending review into a local SQLite file."""
import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from claimcascade.core import baseline, candidates, snapshot, validate_proposals
from claimcascade.persistence import Store, now, reviews, runs
from claimcascade.reporting import validate_report
from claimcascade.schemas import Proposals, Settings
from claimcascade.services import review_revision
from claimcascade.synthetic import generate
from scripts.assemble_recovered import assemble


def import_pending(result, draft, database):
    if result.get('status') != 'recovered_complete' or result.get('reviewer_approved') is not False:
        raise ValueError('Only unapproved recovered results may be imported')
    if draft.get('status') != 'pending_human_review' or draft.get('reviewer_approved') is not False:
        raise ValueError('Only pending assistant review drafts may be imported')
    if draft.get('source_hashes') != result['sources']:
        raise ValueError('Review draft sources differ from the recovered investigation')
    claims, bulletins, truth = generate(42, False)
    proposals = validate_proposals(Proposals.model_validate(result['proposals']), claims)
    validate_report(result['report'], proposals, claims)
    original = dict(groups=[dict(cluster_id=c.cluster_id, members=c.members, decision='pending', note='')
                           for c in proposals.clusters], duplicates={}, dismissed_duplicates=[])
    payload = draft['review_payload']
    if any(g['decision'] != 'pending' for g in payload['groups']) or payload['duplicates']:
        raise ValueError('Import cannot approve groups or confirm duplicates')
    payload = review_revision(payload, original, claims)
    settings = Settings()
    edges = candidates(claims, settings)
    _, content = snapshot(claims, bulletins, settings, result['model'], 'Recovered checkpoints — pending review')
    content.update(pipeline_version='recovered-1', checkpoint_sources=result['sources'],
                   imported_review_sha256=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest())
    digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    imported = dict(result, edges=edges, baseline=baseline(claims, edges), evaluation_truth=truth, telemetry=[])
    store = Store('sqlite:///'+str(Path(database).resolve()).replace('\\', '/'))
    try:
        with store.engine.begin() as conn:
            existing = conn.execute(select(runs.c.id).where(runs.c.snapshot_hash == digest)).first()
            if existing:
                return existing[0], False
            run_id = str(uuid4())
            timestamp = now()
            conn.execute(runs.insert().values(id=run_id, snapshot_hash=digest, created_at=timestamp,
                status='complete', snapshot=content, result=imported))
            conn.execute(reviews.insert().values(id=str(uuid4()), run_id=run_id, revision=1,
                created_at=timestamp, payload=payload))
            return run_id, True
    finally:
        store.engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('challenger_source', type=Path)
    parser.add_argument('reporter_source', type=Path)
    parser.add_argument('review_draft', type=Path)
    parser.add_argument('--database', type=Path, default=Path('data/recovered-review.db'))
    args = parser.parse_args()
    result = assemble(args.source, args.challenger_source, args.reporter_source)
    draft = json.loads(args.review_draft.read_text(encoding='utf-8'))
    run_id, created = import_pending(result, draft, args.database)
    print(json.dumps(dict(run_id=run_id, created=created, database=str(args.database), decisions='pending')))


if __name__ == '__main__':
    main()
