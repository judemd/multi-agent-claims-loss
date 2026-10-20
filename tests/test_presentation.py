import pytest

from claimcascade.presentation import parse_duplicates, parse_dismissed


def test_blank_editor_rows_do_not_change_confirmations():
    assert parse_duplicates([{'duplicate':'C049','canonical':'C004'}, {'duplicate':'','canonical':None}]) == {'C049':'C004'}
    assert parse_dismissed([{'claim_a':'C031','claim_b':'C033'}, {'claim_a':None,'claim_b':''}]) == [['C031','C033']]


@pytest.mark.parametrize('rows', [
    [{'duplicate':'C049','canonical':''}],
    [{'duplicate':'','canonical':'C004'}],
    [{'duplicate':'C049','canonical':'C004'}, {'duplicate':'C049','canonical':'C005'}],
])
def test_incomplete_or_conflicting_confirmations_are_not_silently_dropped(rows):
    with pytest.raises(ValueError):
        parse_duplicates(rows)


def test_partial_dismissed_pair_is_not_silently_dropped():
    with pytest.raises(ValueError):
        parse_dismissed([{'claim_a':'C031','claim_b':''}])
