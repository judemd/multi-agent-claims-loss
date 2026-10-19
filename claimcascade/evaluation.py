from itertools import combinations


def pairs(groups, canonical):
    result = set()
    for group in groups:
        members = sorted({canonical.get(c, c) for c in group})
        result.update(combinations(members, 2))
    return result


def evaluate(groups, edges, truth, known_ids):
    labels, canonical = truth['events'], truth.get('duplicates', {})
    if set(labels) != set(known_ids):
        raise ValueError('Ground truth does not match this dataset')
    if any(k not in labels or v not in labels or k == v for k,v in canonical.items()) or set(canonical) & set(canonical.values()):
        raise ValueError('Invalid ground truth duplicate mapping')
    by_event = {}
    for claim, label in labels.items():
        by_event.setdefault(label, []).append(claim)
    actual = pairs(by_event.values(), canonical)
    predicted = pairs(groups, canonical)
    available = pairs([[e['a'], e['b']] for e in edges], canonical)
    correct = actual & predicted
    precision = len(correct)/len(predicted) if predicted else None
    recall = len(correct)/len(actual) if actual else None
    f1 = (2*precision*recall/(precision+recall) if precision+recall else 0) if precision is not None and recall is not None else None
    return dict(precision=precision, recall=recall, f1=f1,
                candidate_recall=len(actual & available)/len(actual) if actual else None,
                true_pairs=len(actual), predicted_pairs=len(predicted),
                incorrect_merges=sorted(predicted-actual), missed_connections=sorted(actual-predicted))


def financial_reference(claims, groups, truth, confirmed_duplicates=None):
    """Compare operational duplicate choices with the labelled canonical reference."""
    from .core import total
    rows = []
    for group_id, members in groups:
        observed = total(claims,members,confirmed_duplicates or {})
        reference = total(claims,members,truth.get('duplicates',{}))
        rows.append(dict(cluster_id=group_id,reported=observed,hidden_canonical_reference=reference,
                         matches_reference=observed==reference))
    return rows
