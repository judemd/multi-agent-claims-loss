"""Source and membership checks for generated reports; free text remains unproven."""
import re

from .core import validate_evidence
from .schemas import Report

REPORT_INSTRUCTION = '''Explain each proposal separating source quotations, hypotheses and missing information.
For observed_facts return claim_id and an exact narrative excerpt; do not paraphrase observations.
For each hypothesis or missing-information statement return text and explicit claim_ids from that cluster.
Never put claim identifiers or identifier ranges in text; identifiers belong only in structured references.
Do not describe or enumerate cluster membership in text. Membership and reported amounts are rendered by Python.
Do not calculate, repeat or invent monetary amounts. Objections remain unresolved for the reviewer.'''


def validate_report(report, proposals, claims):
    report = Report.model_validate(report)
    lookup = {c.cluster_id:c for c in proposals.clusters}
    if {e.cluster_id for e in report.explanations} != set(lookup) or len(report.explanations) != len(lookup):
        raise ValueError('Reporter must explain exactly the proposed clusters')
    # Match the fixture's ID format even when the ID is unknown; also cover arbitrary supplied IDs.
    known_ids = {c.claim_id for c in claims}
    identifiers = re.compile(r'(?<!\w)(?:'+ '|'.join(re.escape(c) for c in sorted(known_ids, key=len, reverse=True)) + r'|C\d+)(?!\w)', re.IGNORECASE)
    for explanation in report.explanations:
        members = set(lookup[explanation.cluster_id].members)
        if any(f.claim_id not in members for f in explanation.observed_facts):
            raise ValueError('Report observation references a nonmember')
        validate_evidence(explanation.observed_facts, claims)
        for statement in explanation.hypotheses + explanation.missing_information:
            if len(statement.claim_ids) != len(set(statement.claim_ids)) or not set(statement.claim_ids) <= members:
                raise ValueError('Report statement references invalid membership')
            if identifiers.search(statement.text):
                raise ValueError('Claim identifiers belong in structured references, not prose')
    return report
