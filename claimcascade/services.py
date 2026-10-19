from .core import baseline, canonical_ids, total, validate_proposals
from .schemas import Cluster, Evidence, Proposals


def offline_analysis(claims, edges):
    groups = baseline(claims, edges)
    lookup = {c.claim_id:c for c in claims}
    clusters = [Cluster(cluster_id=f'R{i+1}', description='Rules-only time and distance group; common cause unverified',
                        members=g, evidence=[Evidence(claim_id=c, excerpt=lookup[c].narrative) for c in g],
                        ambiguities=['Narrative compatibility has not been assessed by an agent.']) for i,g in enumerate(groups)]
    used = {m for g in groups for m in g}
    proposals = Proposals(clusters=clusters,unassigned=[c.claim_id for c in claims if c.claim_id not in used])
    validate_proposals(proposals,claims)
    return dict(proposals=proposals.model_dump(), challenge={'objections':[]}, report={'explanations':[]}, facts=[],
                totals={c.cluster_id:total(claims,c.members) for c in clusters},telemetry=[])


def validate_review(payload, claims):
    known = {c.claim_id for c in claims}
    mapping = canonical_ids(claims, payload.get('duplicates',{}))
    used, canonical_groups, group_ids = set(), {}, set()
    for group in payload['groups']:
        if not group['cluster_id'] or group['cluster_id'] in group_ids:
            raise ValueError('Cluster IDs must be nonempty and unique')
        group_ids.add(group['cluster_id'])
        members = set(group['members'])
        if len(members) < 2 or len(members) != len(group['members']) or not members <= known or members & used:
            raise ValueError('Review groups need at least two unique, known, non-overlapping notifications')
        if group['decision'] not in ['pending','approved','rejected']:
            raise ValueError('Invalid review decision')
        if len({mapping[m] for m in members}) < 2:
            raise ValueError('A shared event needs at least two underlying claims')
        for member in members:
            canonical = mapping[member]
            if canonical in canonical_groups and canonical_groups[canonical] != group['cluster_id']:
                raise ValueError('Confirmed duplicates cannot span different clusters')
            canonical_groups[canonical] = group['cluster_id']
        used |= members
    return payload


def review_revision(payload, previous, claims):
    """Validate and invalidate approvals when a saved review is edited."""
    import copy
    payload = copy.deepcopy(validate_review(payload,claims))
    if previous is not None:
        old = {g['cluster_id']:g['members'] for g in previous['groups']}
        for group in payload['groups']:
            if set(group['members']) != set(old.get(group['cluster_id'],[])) or payload['duplicates'] != previous['duplicates']:
                group['decision'] = 'pending'
    for pair in payload.get('dismissed_duplicates',[]):
        if not isinstance(pair,list) or len(pair)!=2 or len(set(pair))!=2 or not set(pair) <= {c.claim_id for c in claims}:
            raise ValueError('Dismissed duplicates must be pairs of distinct known notification IDs')
    return payload
