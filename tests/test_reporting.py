import pytest
from pydantic import ValidationError

from claimcascade.reporting import validate_report
from claimcascade.schemas import Proposals, Report
from claimcascade.synthetic import generate


def fixture():
    claims, _, _ = generate(42, False)
    lookup = {c.claim_id:c for c in claims}
    members = [f'C{i:03}' for i in range(11,21) if i != 12]
    proposals = Proposals.model_validate(dict(clusters=[dict(cluster_id='rain', description='Unconfirmed',
        members=members, evidence=[dict(claim_id=c.claim_id, excerpt=c.narrative) for c in claims if c.claim_id in members])],
        unassigned=[c.claim_id for c in claims if c.claim_id not in members]))
    explanation = dict(cluster_id='rain', observed_facts=[dict(claim_id='C011', excerpt=lookup['C011'].narrative)],
        hypotheses=[dict(text='Heavy rain may be a shared cause.', claim_ids=['C011', 'C013'])],
        missing_information=[dict(text='The incident time needs confirmation.', claim_ids=['C011'])])
    return claims, proposals, explanation


def test_source_quotes_and_explicit_member_references_pass():
    claims, proposals, explanation = fixture()
    report = validate_report({'explanations':[explanation]}, proposals, claims)
    assert report.explanations[0].observed_facts[0].excerpt == next(c.narrative for c in claims if c.claim_id == 'C011')


@pytest.mark.parametrize('ids', [['C012'], ['C999'], ['C011', 'C011']])
def test_nonmember_unknown_and_duplicate_references_fail(ids):
    claims, proposals, explanation = fixture()
    explanation['hypotheses'][0]['claim_ids'] = ids
    with pytest.raises(ValueError, match='invalid membership'):
        validate_report({'explanations':[explanation]}, proposals, claims)


@pytest.mark.parametrize('text', ['C011 to C020 share an event.', 'C011–C020 share an event.',
                                 'C999 is involved.', 'c011 is involved.'])
def test_prose_identifiers_and_ranges_are_rejected(text):
    claims, proposals, explanation = fixture()
    explanation['hypotheses'][0]['text'] = text
    with pytest.raises(ValueError, match='structured references'):
        validate_report({'explanations':[explanation]}, proposals, claims)


def test_fabricated_or_wrong_member_observations_fail():
    claims, proposals, explanation = fixture()
    explanation['observed_facts'][0]['excerpt'] = 'This is invented.'
    with pytest.raises(ValueError, match='exact narrative'):
        validate_report({'explanations':[explanation]}, proposals, claims)
    explanation['observed_facts'] = [dict(claim_id='C012', excerpt=next(c.narrative for c in claims if c.claim_id == 'C012'))]
    with pytest.raises(ValueError, match='nonmember'):
        validate_report({'explanations':[explanation]}, proposals, claims)


def test_legacy_prose_report_is_not_silently_accepted():
    _, _, explanation = fixture()
    explanation['observed_facts'] = ['Claims C011 to C020 report flooding.']
    with pytest.raises(ValidationError):
        Report(explanations=[explanation])
