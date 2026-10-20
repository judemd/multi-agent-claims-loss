from streamlit.testing.v1 import AppTest
from pathlib import Path
import pytest


def test_rules_workflow_and_rerun(monkeypatch,tmp_path):
    monkeypatch.setenv('DATABASE_URL','sqlite:///'+str(tmp_path/'ui.db'))
    monkeypatch.setenv('CLAIMCASCADE_ALLOW_PAID_CALLS','false')
    app = AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=30).run()
    assert not app.exception
    next(b for b in app.button if b.label=='Generate 50 synthetic notifications').click().run()
    assert not app.exception
    next(b for b in app.button if b.label=='Analyse').click().run()
    assert not app.exception
    from claimcascade.persistence import Store
    store = Store()
    assert len(store.list_runs())==1
    app.run()
    assert len(store.list_runs())==1
    assert not app.exception
    next(b for b in app.button if b.label=='Analyse').click().run()
    assert len(store.list_runs())==1
    assert not app.exception


@pytest.mark.parametrize('legacy', [False, True])
def test_report_references_and_legacy_warning(monkeypatch, tmp_path, legacy):
    import streamlit as st
    st.cache_resource.clear()
    import claimcascade.services
    original = claimcascade.services.offline_analysis
    def analysis(claims, edges):
        result = original(claims, edges)
        result['report']['explanations'] = [dict(cluster_id=c['cluster_id'],
            observed_facts=c['evidence'][:1],
            hypotheses=[dict(text='A shared cause is unconfirmed.', claim_ids=c['members'][:1])],
            missing_information=[]) for c in result['proposals']['clusters']]
        if legacy:
            result['report']['explanations'][0]['observed_facts'] = ['Unvalidated historical prose']
        return result
    monkeypatch.setattr(claimcascade.services, 'offline_analysis', analysis)
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///'+str(tmp_path/'reports.db'))
    monkeypatch.setenv('CLAIMCASCADE_ALLOW_PAID_CALLS', 'false')
    app = AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py', default_timeout=30).run()
    next(b for b in app.button if b.label=='Generate 50 synthetic notifications').click().run()
    next(b for b in app.button if b.label=='Analyse').click().run()
    assert not app.exception
    warnings = [w.value for w in app.warning]
    assert any('historical report' in w for w in warnings) == legacy
    if not legacy:
        assert any('Referenced claims:' in m.value for m in app.markdown)
