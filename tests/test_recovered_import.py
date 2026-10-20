from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from claimcascade.core import candidates
from claimcascade.schemas import Settings
from claimcascade.services import offline_analysis
from claimcascade.synthetic import generate
from scripts.import_recovered import import_pending


def test_imported_pending_revision_is_reviewable_without_inference(monkeypatch, tmp_path):
    claims, _, _ = generate(42, False)
    result = offline_analysis(claims, candidates(claims, Settings()))
    result.update(status='recovered_complete', reviewer_approved=False,
                  origin='linked checkpoints; not a fresh end-to-end run', model='gemini-3.5-flash',
                  sources={'test':{'file':'offline fixture', 'sha256':'offline'}})
    result['report']['explanations'] = [dict(cluster_id=c['cluster_id'],
        observed_facts=c['evidence'][:1], hypotheses=[], missing_information=[])
        for c in result['proposals']['clusters']]
    groups = [dict(cluster_id=c['cluster_id'], members=list(c['members']), decision='pending', note='Suggested')
              for c in result['proposals']['clusters']]
    edited = next(g for g in groups if len(g['members']) > 2)
    held = edited['members'].pop()
    draft = dict(status='pending_human_review', reviewer_approved=False, source_hashes=result['sources'],
                 review_payload=dict(groups=groups, duplicates={}, dismissed_duplicates=[]))
    database = tmp_path/'review.db'
    import_pending(result, draft, database)
    st.cache_resource.clear()
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///'+str(database))
    monkeypatch.setenv('CLAIMCASCADE_ALLOW_PAID_CALLS', 'false')
    import claimcascade.agents
    def forbidden(*args, **kwargs):
        raise AssertionError('Opening recovered history must not invoke a model')
    monkeypatch.setattr(claimcascade.agents, 'analyse_live', forbidden)
    app = AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py', default_timeout=30).run()
    assert not app.exception
    assert any('Recovered investigation' in info.value for info in app.info)
    rows = next(frame.value for frame in app.dataframe if 'cluster_id' in frame.value.columns)
    row = rows[rows['cluster_id'] == edited['cluster_id']].iloc[0]
    assert held not in row['claim_ids'].split(',')
    assert row['decision'] == 'pending'
    assert not app.warning
    st.cache_resource.clear()
