import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import JSON, Column, Integer, MetaData, String, Table, create_engine, select


metadata = MetaData()
runs = Table('runs', metadata,
    Column('id', String, primary_key=True), Column('snapshot_hash', String, nullable=False),
    Column('created_at', String, nullable=False), Column('status', String, nullable=False),
    Column('snapshot', JSON, nullable=False), Column('result', JSON), Column('error', String))
reviews = Table('reviews', metadata,
    Column('id', String, primary_key=True), Column('run_id', String, nullable=False),
    Column('revision', Integer, nullable=False), Column('created_at', String, nullable=False),
    Column('payload', JSON, nullable=False))


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, url=None):
        url = url or os.getenv('DATABASE_URL', 'sqlite:///data/claimcascade.db')
        if url.startswith('sqlite:///') and ':memory:' not in url:
            Path(url.removeprefix('sqlite:///')).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, connect_args={'check_same_thread':False} if url.startswith('sqlite') else {}, pool_pre_ping=True)
        metadata.create_all(self.engine)

    def start(self, digest, content):
        run_id = str(uuid4())
        with self.engine.begin() as conn:
            conn.execute(runs.insert().values(id=run_id, snapshot_hash=digest, created_at=now(), status='running', snapshot=content))
        return run_id

    def finish(self, run_id, result=None, error=None):
        with self.engine.begin() as conn:
            conn.execute(runs.update().where(runs.c.id==run_id).values(status='failed' if error else 'complete', result=result, error=error))

    def list_runs(self):
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(runs).order_by(runs.c.created_at.desc())).mappings()]

    def history(self, run_id):
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(reviews).where(reviews.c.run_id==run_id).order_by(reviews.c.revision)).mappings()]

    def save_review(self, run_id, payload):
        # Single local reviewer; immutable revisions. Hosted writes are kept in short transactions.
        with self.engine.begin() as conn:
            run = conn.execute(select(runs).where(runs.c.id==run_id)).mappings().first()
            if not run or run['status'] != 'complete':
                raise ValueError('Only completed runs can be reviewed')
            revision = len(conn.execute(select(reviews.c.id).where(reviews.c.run_id==run_id)).all()) + 1
            conn.execute(reviews.insert().values(id=str(uuid4()), run_id=run_id, revision=revision, created_at=now(), payload=payload))
