import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from claimcascade.core import (baseline, candidates, distance, dump_claims_csv, load_csv,
    snapshot, time_gap, total, validate_claims, validate_evidence, validate_proposals)
from claimcascade.evaluation import evaluate
from claimcascade.persistence import Store
from claimcascade.schemas import Claim, Evidence, Proposals, Settings
from claimcascade.services import offline_analysis, review_revision, validate_review
from claimcascade.synthetic import generate


@pytest.fixture
def dataset():
    return generate()


def test_generation_and_csv(dataset):
    claims, bulletins, truth = dataset
    again = generate()
    assert [c.model_dump() for c in claims] == [c.model_dump() for c in again[0]]
    assert len(claims) == 50
    assert len(set(truth['events'].values()) - {v for v in truth['events'].values() if v.startswith('isolated')}) == 3
    assert load_csv(dump_claims_csv(claims)) == claims
    encoded = json.dumps([c.model_dump(mode='json') for c in claims])
    assert 'duplicate_of_claim_id' not in encoded and 'event_id' not in encoded
    assert len(truth['duplicates']) == 2


def test_schema_and_time(dataset):
    c = dataset[0][0]
    row = c.model_dump()
    row['notification_timestamp'] = '2026-01-01T00:00:00'
    with pytest.raises(ValidationError):
        Claim.model_validate(row)
    row = c.model_dump()
    row['duplicate_of_claim_id'] = 'C001'
    with pytest.raises(ValidationError):
        Claim.model_validate(row)
    with pytest.raises(ValueError):
        validate_claims([c.model_dump(),c.model_dump()])
    a = c.model_copy(update={'x':0,'y':0,'incident_start':None,'incident_end':None})
    b = c.model_copy(update={'x':3,'y':4})
    assert distance(a,b) == 5
    assert time_gap(a,b) is None
    edges = candidates([a,b],Settings())
    assert edges[0]['timing_unknown']
    assert baseline([a,b],edges) == []


def test_chain_merging(dataset):
    template = next(c for c in dataset[0] if c.incident_start)
    claims = [template.model_copy(update={'claim_id':name,'x':x,'y':0}) for name,x in [('A',0),('B',8),('C',16)]]
    edges = candidates(claims,Settings(distance_km=10))
    assert len(edges)==2
    assert baseline(claims,edges)==[['A','B']]
    assert candidates([claims[0].model_copy(update={'loss_type':'stock'}),claims[1].model_copy(update={'loss_type':'interruption'})],Settings())


def test_evidence_and_membership(dataset):
    claims = dataset[0]
    result = offline_analysis(claims,candidates(claims,Settings()))
    proposals = Proposals.model_validate(result['proposals'])
    validate_proposals(proposals,claims)
    with pytest.raises(ValueError):
        validate_evidence([Evidence(claim_id=claims[0].claim_id,excerpt='invented')],claims)
    with pytest.raises(ValueError):
        validate_evidence([Evidence(claim_id='UNKNOWN',excerpt=claims[0].narrative)],claims)
    first = proposals.clusters[0]
    first.members.append(first.members[0])
    with pytest.raises(ValueError):
        validate_proposals(proposals,claims)


def test_amounts_and_duplicates(dataset):
    template = dataset[0][0]
    claims = [template.model_copy(update={'claim_id':'A','reported_amount_gbp':Decimal('12.34')}),
              template.model_copy(update={'claim_id':'B','reported_amount_gbp':Decimal('50')}),
              template.model_copy(update={'claim_id':'C','reported_amount_gbp':None})]
    assert total(claims,['A','B','C'])['known_amount_gbp']=='62.34'
    result = total(claims,['A','B','C'],{'B':'A'})
    assert result['known_amount_gbp']=='12.34' and result['missing_amount_count']==1
    with pytest.raises(ValueError):
        total(claims,['A'],{'A':'B','B':'A'})


def test_hand_checked_metrics():
    truth = {'events':{'A':'E','B':'E','C':'F','D':'E'},'duplicates':{'D':'A'}}
    edges = [{'a':'A','b':'B'},{'a':'A','b':'C'}]
    metrics = evaluate([['A','B','C']],edges,truth,truth['events'])
    assert metrics['precision']==pytest.approx(1/3)
    assert metrics['recall']==1
    assert metrics['f1']==.5
    assert metrics['candidate_recall']==1
    assert len(metrics['incorrect_merges'])==2
    assert evaluate([],edges,truth,truth['events'])['precision'] is None


def test_snapshot_and_history(dataset,tmp_path):
    claims, bulletins, _ = dataset
    digest, content = snapshot(claims,bulletins,Settings(),'model','rules')
    assert digest == snapshot(list(reversed(claims)),bulletins,Settings(),'model','rules')[0]
    assert digest != snapshot(claims,bulletins,Settings(distance_km=11),'model','rules')[0]
    store = Store('sqlite:///'+str(tmp_path/'test.db'))
    run = store.start(digest,content)
    store.finish(run,result=offline_analysis(claims,candidates(claims,Settings())))
    store.save_review(run,{'groups':[],'duplicates':{}})
    store.save_review(run,{'groups':[],'duplicates':{},'note':'second'})
    assert len(store.history(run))==2
    assert store.history(run)[0]['payload'].get('note') is None
    assert store.list_runs()[0]['snapshot_hash']==digest


def test_review_validation(dataset):
    claims = dataset[0]
    ids = [c.claim_id for c in claims[:4]]
    payload = {'groups':[{'cluster_id':'A','members':ids[:2],'decision':'approved'}],'duplicates':{}}
    validate_review(payload,claims)
    payload['groups'].append({'cluster_id':'B','members':ids[1:3],'decision':'pending'})
    with pytest.raises(ValueError):
        validate_review(payload,claims)


def test_live_is_explicitly_gated(monkeypatch,dataset):
    from claimcascade.agents import analyse_live
    monkeypatch.setenv('CLAIMCASCADE_ALLOW_PAID_CALLS','false')
    with pytest.raises(RuntimeError,match='disabled'):
        analyse_live(dataset[0],dataset[1],[],'unused')


def test_edited_approval_invalidated(dataset):
    import copy
    claims = dataset[0]
    ids = [c.claim_id for c in claims[:4]]
    previous = {'groups':[dict(cluster_id='A',members=ids[:2],decision='approved',note='')],'duplicates':{}}
    edited = copy.deepcopy(previous)
    edited['groups'][0]['members'] = ids[1:3]
    assert review_revision(edited,previous,claims)['groups'][0]['decision']=='pending'
    assert previous['groups'][0]['decision']=='approved'
    assert review_revision(previous,previous,claims)['groups'][0]['decision']=='approved'


def test_public_mode_refuses_paid_calls(monkeypatch,dataset):
    from claimcascade.agents import analyse_live
    monkeypatch.setenv('CLAIMCASCADE_ALLOW_PAID_CALLS','true')
    monkeypatch.setenv('CLAIMCASCADE_PUBLIC_DEMO','true')
    with pytest.raises(RuntimeError,match='Public demo'):
        analyse_live(dataset[0],dataset[1],[],'unused')
