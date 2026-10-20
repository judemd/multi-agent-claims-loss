"""Readable display rows and review input parsing; stored payloads stay unchanged."""
from decimal import Decimal


def money(value):
    return f'£{Decimal(str(value)):,.2f}'


def amount_row(group, amount, decision=None):
    row = {'Group':group, 'Reported amount':money(amount['known_amount_gbp']),
           'Missing amounts':amount['missing_amount_count'],
           'Underlying claims':amount['underlying_claim_count']}
    if decision is not None:
        row['Decision'] = decision.capitalize()
    return row


def group_rows(groups):
    return [{'Group':g['cluster_id'], 'Claims':', '.join(g['members']),
             'Decision':g['decision'].capitalize(), 'Note':g.get('note','')} for g in groups]


def duplicate_rows(mapping):
    return [{'duplicate':duplicate, 'canonical':canonical} for duplicate, canonical in mapping.items()]


def parse_duplicates(rows):
    mapping = {}
    for row in rows:
        duplicate, canonical = str(row.get('duplicate') or '').strip(), str(row.get('canonical') or '').strip()
        if not duplicate and not canonical:
            continue
        if not duplicate or not canonical:
            raise ValueError('Each confirmed duplicate needs both notification IDs')
        if duplicate in mapping:
            raise ValueError('Each duplicate notification can appear only once')
        mapping[duplicate] = canonical
    return mapping


def parse_dismissed(rows):
    pairs = []
    for row in rows:
        a, b = str(row.get('claim_a') or '').strip(), str(row.get('claim_b') or '').strip()
        if not a and not b:
            continue
        if not a or not b:
            raise ValueError('Each dismissed duplicate pair needs both notification IDs')
        pairs.append([a,b])
    return pairs
