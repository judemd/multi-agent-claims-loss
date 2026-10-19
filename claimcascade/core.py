import csv
import hashlib
import io
import json
import math
from decimal import Decimal

from .schemas import Claim, Proposals, Settings


def validate_claims(rows):
    claims = [Claim.model_validate(row) for row in rows]
    if not claims or len(claims) > 100:
        raise ValueError("Supply between 1 and 100 notifications")
    ids = [c.claim_id for c in claims]
    if len(ids) != len(set(ids)):
        raise ValueError("claim_id must be unique")
    return claims


def load_csv(content: str):
    rows = []
    for row in csv.DictReader(io.StringIO(content.lstrip('\ufeff'))):
        rows.append({k: (None if v == '' else v) for k, v in row.items()})
    return validate_claims(rows)


def dump_claims_csv(claims):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(Claim.model_fields),lineterminator='\n')
    writer.writeheader()
    writer.writerows(c.model_dump(mode='json') for c in claims)
    return output.getvalue()


def snapshot(claims, bulletins, settings, model, mode):
    content = dict(claims=sorted([c.model_dump(mode='json') for c in claims], key=lambda c: c['claim_id']),
                   bulletins=sorted([b.model_dump(mode='json') for b in bulletins], key=lambda b: b['bulletin_id']),
                   settings=settings.model_dump(), model=model, mode=mode, pipeline_version='1')
    digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    return digest, content


def distance(a, b):
    if a.x is None or b.x is None:
        return None
    return math.hypot(a.x - b.x, a.y - b.y)


def time_gap(a, b):
    if a.incident_start is None or b.incident_start is None:
        return None
    return max(0, (a.incident_start - (b.incident_end or b.incident_start)).total_seconds(),
               (b.incident_start - (a.incident_end or a.incident_start)).total_seconds()) / 3600


def candidates(claims, settings: Settings):
    edges = []
    for i, a in enumerate(claims):
        for b in claims[i + 1:]:
            d, t = distance(a, b), time_gap(a, b)
            # Missing coordinates cannot support a spatial candidate. Missing time is explicit.
            if d is not None and d <= settings.distance_km and (t is None or t <= settings.time_gap_hours):
                edges.append(dict(a=a.claim_id, b=b.claim_id, distance_km=round(d, 3),
                                  gap_hours=t, timing_unknown=t is None))
    return edges


def baseline(claims, edges):
    pairs = {frozenset((e['a'], e['b'])) for e in edges if not e['timing_unknown']}
    groups = []
    for claim in sorted(claims, key=lambda c: c.claim_id):
        for group in groups:
            if all(frozenset((claim.claim_id, member)) in pairs for member in group):
                group.append(claim.claim_id)
                break
        else:
            groups.append([claim.claim_id])
    return [g for g in groups if len(g) > 1]


def validate_evidence(items, claims):
    lookup = {c.claim_id: c for c in claims}
    for item in items:
        if item.claim_id not in lookup or item.excerpt not in lookup[item.claim_id].narrative:
            raise ValueError("Evidence must reference a known claim and an exact narrative excerpt")


def validate_proposals(proposals: Proposals, claims):
    known = {c.claim_id for c in claims}
    used, cluster_ids = set(), set()
    for cluster in proposals.clusters:
        if cluster.cluster_id in cluster_ids:
            raise ValueError("Cluster IDs must be unique")
        cluster_ids.add(cluster.cluster_id)
        members = set(cluster.members)
        if len(members) != len(cluster.members) or not members <= known or used & members:
            raise ValueError("Invalid, duplicate, or overlapping membership")
        validate_evidence(cluster.evidence, claims)
        if {e.claim_id for e in cluster.evidence} != members:
            raise ValueError("Every member requires its own evidence")
        used |= members
    if len(proposals.unassigned) != len(set(proposals.unassigned)) or set(proposals.unassigned) != known - used:
        raise ValueError("Unassigned claims must exactly cover the remaining claims")
    return proposals


def suspected_duplicates(claims):
    return [(a.claim_id, b.claim_id) for i, a in enumerate(claims) for b in claims[i+1:]
            if a.narrative.strip().casefold() == b.narrative.strip().casefold()]


def canonical_ids(claims, duplicate_map):
    known = {c.claim_id for c in claims}
    if any(k not in known or v not in known or k == v for k, v in duplicate_map.items()):
        raise ValueError("Invalid duplicate mapping")
    if set(duplicate_map) & set(duplicate_map.values()):
        raise ValueError("Duplicate chains and cycles are not supported; select one canonical notification")
    return {k: duplicate_map.get(k, k) for k in known}


def total(claims, members, duplicate_map=None):
    mapping = canonical_ids(claims, duplicate_map or {})
    lookup = {c.claim_id: c for c in claims}
    if not set(members) <= lookup.keys():
        raise ValueError("Unknown claim in total")
    ids = {mapping[c] for c in members}
    amounts = [lookup[c].reported_amount_gbp for c in ids]
    return dict(label='Reported claim amount', known_amount_gbp=str(sum((a for a in amounts if a is not None), Decimal('0.00'))),
                missing_amount_count=sum(a is None for a in amounts), underlying_claim_count=len(ids))
