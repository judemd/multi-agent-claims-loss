from streamlit.testing.v1 import AppTest
from pathlib import Path


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
