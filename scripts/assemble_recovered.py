"""Offline assembly and evaluation of linked synthetic checkpoints; never invokes models."""
import argparse
import hashlib
import json
from pathlib import Path

from claimcascade.core import baseline, candidates
from claimcascade.evaluation import evaluate, financial_reference
from claimcascade.schemas import Report, Settings
from claimcascade.synthetic import generate
from scripts.diagnose_reporter import prepare


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assemble(source, challenger_source, reporter_source):
    prepared = prepare(source, challenger_source)
    reporter = json.loads(reporter_source.read_text(encoding='utf-8'))
    expected = dict(status='complete', stage='reporter', seed=42, held_out=False,
                    claim_count=50, model='gemini-3.5-flash')
    if any(reporter.get(k) != v for k, v in expected.items()):
        raise ValueError('Reporter checkpoint identity or status differs')
    if (reporter.get('source_sha256') != digest(source) or
        reporter.get('challenger_source_sha256') != digest(challenger_source) or
        reporter.get('payload_sha256') != hashlib.sha256(json.dumps(prepared[3]).encode()).hexdigest()):
        raise ValueError('Reporter checkpoint is not linked to these sources')
    if any(reporter.get('request_policy', {}).get(k) != v for k, v in
           [('temperature', 1.0), ('thinking_level', 'LOW')]):
        raise ValueError('Reporter generation settings differ')
    report = reporter['schema_validated_outputs']['reporter']
    prepared[4](Report.model_validate(report))
    # Hidden labels are loaded for evaluation only after all output validation.
    claims, _, truth = generate(42, False)
    edges = candidates(claims, Settings())
    proposals = prepared[3]['proposals']
    groups = [(c['cluster_id'], c['members']) for c in proposals['clusters']]
    known_ids = [c.claim_id for c in claims]
    return dict(status='recovered_complete', origin='linked checkpoints; not a fresh end-to-end run',
        reviewer_approved=False, seed=42, held_out=False, claim_count=50,
        model='gemini-3.5-flash', proposals=proposals, challenge=prepared[3]['challenge'],
        report=report, totals=prepared[3]['totals'],
        sources={role:dict(file=str(path), sha256=digest(path)) for role, path in
                 [('investigation', source), ('challenger', challenger_source), ('reporter', reporter_source)]},
        evaluation=dict(agent=evaluate([members for _, members in groups], edges, truth, known_ids),
            baseline=evaluate(baseline(claims, edges), edges, truth, known_ids),
            financial_reference=financial_reference(claims, groups, truth)))


def markdown(result):
    lines = ['# ClaimCascade recovered synthetic investigation', '',
        'Recovered checkpoints, not a fresh end-to-end run. Pending human review; no proposals are approved.', '',
        'Development seed 42, 50 notifications. Labels were used only for offline evaluation.', '',
        '| Pair metric | Rules baseline | Recovered agents |', '|---|---:|---:|']
    for key in ('precision', 'recall', 'f1', 'candidate_recall'):
        values = [result['evaluation'][name][key] for name in ('baseline', 'agent')]
        lines.append('| '+key+' | '+' | '.join('N/A' if v is None else f'{v:.3f}' for v in values)+' |')
    lines += ['', 'This reused development fixture is not a blind benchmark or evidence of real-world accuracy.', '',
              '## Unassigned notifications', '', ', '.join(result['proposals']['unassigned'])]
    reports = {e['cluster_id']:e for e in result['report']['explanations']}
    for cluster in result['proposals']['clusters']:
        cid = cluster['cluster_id']
        amount = result['totals'][cid]
        lines += ['', f'## {cid} — pending review', '', 'Members: '+', '.join(cluster['members']), '',
            f"Reported claim amount: GBP {amount['known_amount_gbp']}; missing amounts: {amount['missing_amount_count']}.",
            'Suspected duplicates have not been confirmed or deducted.', '', '### Source observations', '']
        explanation = reports[cid]
        for fact in explanation['observed_facts']:
            lines.append(f"- {fact['claim_id']}: {fact['excerpt']}")
        for label, key in [('Hypotheses (unproven)', 'hypotheses'), ('Missing information', 'missing_information')]:
            lines += ['', '### '+label, '']
            lines += [f"- {', '.join(s['claim_ids'])}: {s['text']}" for s in explanation[key]]
        lines += ['', '### Unresolved challenger objections', '']
        for objection in result['challenge']['objections']:
            if objection['cluster_id'] == cid:
                lines.append('- '+objection['concern'])
                lines.append('  Suggested removals (not applied): '+', '.join(objection['suggested_removals']))
                lines.append('  Suggested splits (not applied): '+json.dumps(objection['suggested_splits']))
    lines += ['', '## Evaluation-only duplicate reference', '',
        'Hidden duplicate labels are for evaluation only and do not modify the reported totals.', '']
    for row in result['evaluation']['financial_reference']:
        lines.append(f"- {row['cluster_id']}: reported GBP {row['reported']['known_amount_gbp']}; hidden canonical reference GBP {row['hidden_canonical_reference']['known_amount_gbp']}.")
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('challenger_source', type=Path)
    parser.add_argument('reporter_source', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/live-tests/recovered-50.json'))
    args = parser.parse_args()
    result = assemble(args.source, args.challenger_source, args.reporter_source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    review_path = args.output.with_suffix('.md')
    review_path.write_text(markdown(result), encoding='utf-8')
    print(json.dumps(dict(result_file=str(args.output), review_file=str(review_path),
        metrics={name:result['evaluation'][name] for name in ('agent', 'baseline')}), indent=2))


if __name__ == '__main__':
    main()
