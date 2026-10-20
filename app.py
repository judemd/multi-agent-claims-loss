import json
import os

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from claimcascade.agents import analyse_live
from claimcascade.core import baseline, candidates, dump_claims_csv, load_csv, snapshot, suspected_duplicates, total
from claimcascade.evaluation import evaluate, financial_reference
from claimcascade.persistence import Store
from claimcascade.schemas import Bulletin, Claim, Settings, Proposals
from claimcascade.reporting import validate_report
from claimcascade.services import offline_analysis, review_revision
from claimcascade.synthetic import generate
from claimcascade.presentation import amount_row, group_rows, duplicate_rows, parse_duplicates, parse_dismissed, money

load_dotenv()
public_demo = os.getenv('CLAIMCASCADE_PUBLIC_DEMO','false').lower() == 'true'
st.set_page_config(page_title='ClaimCascade', layout='wide')
st.title('ClaimCascade')
st.caption('Shared loss event investigation · fictional region · human decisions required')
st.info('Investigation aid. Shared-event groups do not determine coverage, liability, reserves, fraud or contractual reinsurance aggregation.')


@st.cache_resource
def database():
    return Store()


def readable_table(rows, empty='None recorded.'):
    if rows:
        st.dataframe(rows, hide_index=True, width='stretch')
    else:
        st.caption(empty)


def readable_pairs(pairs):
    readable_table([{'First notification':a, 'Second notification':b} for a,b in pairs])


def readable_duplicates(mapping):
    readable_table([{'Duplicate notification':a, 'Canonical notification':b} for a,b in mapping.items()])


def claim_text(label, ids):
    st.write(f"{label} {', '.join(ids) if ids else 'None'}")


store = database()
data_tab, investigate_tab, review_tab, evaluation_tab = st.tabs(['Data','Event investigation','Review','Evaluation'])

with data_tab:
    left, right = st.columns(2)
    with left:
        seed = st.number_input('Synthetic seed', min_value=0, value=42, step=1)
        held = st.checkbox('Held-out narrative templates')
        if st.button('Generate 50 synthetic notifications'):
            claims, bulletins, truth = generate(int(seed),held)
            st.session_state.dataset = [c.model_dump(mode='json') for c in claims]
            st.session_state.bulletins = [b.model_dump(mode='json') for b in bulletins]
            # Evaluation-only state; never passed to matching, agents, or previews.
            st.session_state.evaluation_truth = truth
    with right:
        upload = st.file_uploader('Claim notifications CSV',type=['csv'],disabled=public_demo)
        bulletin_upload = st.file_uploader('Optional bulletins JSON',type=['json'],disabled=public_demo)
        if public_demo:
            st.caption('Public demo: synthetic data only; uploads and paid model calls are disabled.')
        if st.button('Validate uploaded data',disabled=public_demo) and not public_demo:
            try:
                if upload is None or upload.size > 2_000_000:
                    raise ValueError('Select a CSV smaller than 2 MB')
                claims = load_csv(upload.getvalue().decode('utf-8-sig'))
                if bulletin_upload and bulletin_upload.size > 200_000:
                    raise ValueError('Bulletins must be smaller than 200 KB')
                bulletins = [Bulletin.model_validate(b) for b in json.loads(bulletin_upload.getvalue())] if bulletin_upload else []
                if len(bulletins)>20 or len({b.bulletin_id for b in bulletins}) != len(bulletins):
                    raise ValueError('Supply at most 20 bulletins with unique IDs')
                st.session_state.dataset = [c.model_dump(mode='json') for c in claims]
                st.session_state.bulletins = [b.model_dump(mode='json') for b in bulletins]
                st.session_state.evaluation_truth = None
                st.success('Data validated')
            except Exception as exc:
                st.error(str(exc))
    if 'dataset' in st.session_state:
        readable_table([{k.replace('_',' ').capitalize():(money(v) if v is not None else 'Unknown')
                         if k == 'reported_amount_gbp' else v for k,v in row.items()}
                        for row in st.session_state.dataset])
        with st.expander('Bulletin evidence (unconfirmed)'):
            readable_table([{k.replace('_',' ').capitalize():v for k,v in b.items()} for b in st.session_state.bulletins], 'No bulletins supplied.')
        with st.form('analysis'):
            distance = st.number_input('Candidate distance (km)',value=10.0,min_value=0.1,max_value=150.0)
            hours = st.number_input('Incident interval gap (hours)',value=24.0,min_value=0.0,max_value=720.0)
            mode = st.selectbox('Analysis mode',['Rules only — no model calls'] if public_demo else ['Rules only — no model calls','Live Vertex AI agents'])
            use_bulletins = st.checkbox('Include bulletin evidence',value=True)
            submitted = st.form_submit_button('Analyse')
        if submitted:
            claims = [Claim.model_validate(c) for c in st.session_state.dataset]
            bulletins = [Bulletin.model_validate(b) for b in st.session_state.bulletins] if use_bulletins else []
            settings = Settings(distance_km=distance,time_gap_hours=hours)
            model = os.getenv('GEMINI_MODEL','gemini-3.5-flash')
            digest, content = snapshot(claims,bulletins,settings,model,mode)
            previous = next((r for r in store.list_runs() if r['snapshot_hash']==digest and r['status'] in ['running','complete']),None)
            if previous:
                st.session_state.active_run = previous['id']
                st.info('Using the existing run for this snapshot. Reruns do not issue new model calls.')
            else:
                run_id = store.start(digest,content)
                st.session_state.active_run = run_id
                try:
                    edges = candidates(claims,settings)
                    with st.spinner('Analysing frozen snapshot…'):
                        result = offline_analysis(claims,edges) if mode.startswith('Rules') else analyse_live(claims,bulletins,edges,model)
                    result['edges'] = edges
                    result['baseline'] = baseline(claims,edges)
                    # Labels are attached only after all analysis has completed.
                    result['evaluation_truth'] = st.session_state.get('evaluation_truth')
                    store.finish(run_id,result=result)
                    st.success('Analysis complete')
                except Exception as exc:
                    store.finish(run_id,error=type(exc).__name__)
                    st.error(f'Analysis failed ({type(exc).__name__}). No scripted fallback was used. Check configuration and local logs.')

history = store.list_runs()
if not history:
    st.caption('Generate or upload notifications, then select Analyse.')
    st.stop()
ids = [r['id'] for r in history]
selected = st.sidebar.selectbox('Historical snapshot',ids,
    index=ids.index(st.session_state.get('active_run')) if st.session_state.get('active_run') in ids else 0,
    format_func=lambda rid: next(f"{r['created_at'][:19]} · {r['status']} · {r['snapshot']['mode']}" for r in history if r['id']==rid))
run = next(r for r in history if r['id']==selected)
st.sidebar.caption(f"Snapshot {run['snapshot_hash'][:12]}")
if run['status'] != 'complete':
    st.warning(f"This historical run is {run['status']}. It is not automatically resumed or replayed.")
    st.stop()
claims = [Claim.model_validate(c) for c in run['snapshot']['claims']]
result = run['result']
if result.get('origin'):
    st.info('Recovered investigation assembled from validated checkpoints. This is not a fresh end-to-end run; proposals and suggested edits require review.')
proposals = result['proposals']['clusters']
revisions = store.history(selected)
review = revisions[-1]['payload'] if revisions else {'groups':[dict(cluster_id=c['cluster_id'],members=c['members'],decision='pending',note='') for c in proposals],'duplicates':{},'dismissed_duplicates':[]}
lookup = {c.claim_id:c for c in claims}

with investigate_tab:
    checked_report = None
    if result['report']['explanations']:
        try:
            checked_report = validate_report(result['report'], Proposals.model_validate(result['proposals']), claims)
        except ValueError:
            st.warning('This historical report does not pass current source-reference checks. Use the original evidence and structured membership for review.')
    st.caption('Results belong to the selected historical snapshot. Excerpts support investigation; hypotheses remain unproven.')
    colours = ['#2563eb','#d97706','#059669','#9333ea','#db2777','#0891b2']
    membership = {m:i for i,c in enumerate(proposals) for m in c['members']}
    fig = go.Figure()
    for i, label in [(-1,'Unassigned')] + [(i,c['cluster_id']) for i,c in enumerate(proposals)]:
        subset = [c for c in claims if membership.get(c.claim_id,-1)==i and c.x is not None]
        fig.add_trace(go.Scatter(x=[c.x for c in subset],y=[c.y for c in subset],mode='markers',name=label,
            text=[c.claim_id for c in subset],marker={'color':'#9ca3af' if i<0 else colours[i%len(colours)],'size':11},hovertemplate='%{text}<extra>%{fullData.name}</extra>'))
    fig.update_layout(title='Fictional region',xaxis_title='x (km)',yaxis_title='y (km)',yaxis_scaleanchor='x')
    st.plotly_chart(fig,use_container_width=True)
    timeline = go.Figure()
    for c in claims:
        if c.incident_start:
            i = membership.get(c.claim_id,-1)
            timeline.add_trace(go.Scatter(x=[c.incident_start,c.incident_end or c.incident_start],y=[c.claim_id]*2,mode='lines+markers',showlegend=False,
                line={'color':'#9ca3af' if i<0 else colours[i%len(colours)]}))
    timeline.update_layout(title='Reported incident timeline',height=500)
    st.plotly_chart(timeline,use_container_width=True)
    st.caption(f"{sum(c.incident_start is None for c in claims)} notifications have unknown incident times; notification times are not substituted.")
    claim_text(f"Unassigned claims ({len(result['proposals']['unassigned'])}):",result['proposals']['unassigned'])
    for cluster in proposals:
        with st.expander(f"{cluster['cluster_id']} · {cluster['description']}"):
            claim_text('Proposed membership:',cluster['members'])
            readable_table([amount_row(cluster['cluster_id'], result['totals'][cluster['cluster_id']])])
            st.write('Ambiguities')
            for ambiguity in cluster['ambiguities']:
                st.write('• '+ambiguity)
            if not cluster['ambiguities']:
                st.caption('None recorded.')
            for e in cluster['evidence']:
                st.write(f"{e['claim_id']}: {e['excerpt']}")
            st.write('Challenger objections')
            objections = [o for o in result['challenge']['objections'] if o['cluster_id']==cluster['cluster_id']]
            for objection in objections:
                st.write(objection['concern'])
                claim_text('Suggested removals (not applied):', objection['suggested_removals'])
                for number, split in enumerate(objection['suggested_splits'], 1):
                    claim_text(f'Suggested split {number} (not applied):', split)
            if not objections:
                st.caption('None recorded.')
            if checked_report:
                explanation = next(e for e in checked_report.explanations if e.cluster_id == cluster['cluster_id'])
                st.write('Source observations:')
                for fact in explanation.observed_facts:
                    st.write(f'{fact.claim_id}: {fact.excerpt}')
                for label, statements in [('Hypotheses (unproven)', explanation.hypotheses),
                                          ('Missing information', explanation.missing_information)]:
                    st.write(label)
                    for statement in statements:
                        claim_text('Referenced claims:', statement.claim_ids)
                        st.write(statement.text)

with review_tab:
    st.caption('Edit rows to add/remove claims or split a group into new rows. Claim IDs are comma-separated. Review the evidence and objections in Event investigation before approval. Editing a saved revision resets decisions to pending.')
    rows = [dict(cluster_id=g['cluster_id'],claim_ids=','.join(g['members']),decision=g['decision'],note=g.get('note','')) for g in review['groups']]
    if not rows:
        rows = [dict(cluster_id='',claim_ids='',decision='pending',note='')]
    with st.form(f'review-{selected}-{len(revisions)}'):
        edited = st.data_editor(rows,num_rows='dynamic',key=f'members-{selected}-{len(revisions)}',use_container_width=True,
            column_config={'cluster_id':st.column_config.TextColumn('Group'),
                           'claim_ids':st.column_config.TextColumn('Notifications',width='large'),
                           'note':st.column_config.TextColumn('Review note',width='large'),
                           'decision':st.column_config.SelectboxColumn('Decision',options=['pending','approved','rejected'],required=True)})
        st.write('Suspected duplicates (not automatically excluded)')
        readable_pairs(suspected_duplicates(claims))
        st.write('Confirmed duplicates')
        st.caption('Add one row per duplicate. The canonical notification supplies the amount; delete the row to undo confirmation.')
        duplicate_edits = st.data_editor(duplicate_rows(review['duplicates']) or [{'duplicate':'','canonical':''}],
            num_rows='dynamic', key=f'duplicates-{selected}-{len(revisions)}', width='stretch',
            column_config={'duplicate':st.column_config.TextColumn('Duplicate notification'),
                           'canonical':st.column_config.TextColumn('Canonical notification')})
        st.write('Dismissed duplicate pairs')
        dismissed_edits = st.data_editor([{'claim_a':a,'claim_b':b} for a,b in review.get('dismissed_duplicates',[])] or [{'claim_a':'','claim_b':''}],
            num_rows='dynamic', key=f'dismissed-{selected}-{len(revisions)}', width='stretch',
            column_config={'claim_a':st.column_config.TextColumn('First notification'),
                           'claim_b':st.column_config.TextColumn('Second notification')})
        save = st.form_submit_button('Save review revision')
    if save:
        try:
            payload = {'groups':[dict(cluster_id=r['cluster_id'],members=[m.strip() for m in r['claim_ids'].split(',') if m.strip()],decision=r['decision'],note=r.get('note','')) for r in edited if r.get('cluster_id') or r.get('claim_ids')],
                       'duplicates':parse_duplicates(duplicate_edits),'dismissed_duplicates':parse_dismissed(dismissed_edits)}
            payload = review_revision(payload,review if revisions else None,claims)
            store.save_review(selected,payload)
            st.success('Revision saved. Reopen or rerun to display the latest totals.')
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    st.subheader('Review totals')
    readable_table([amount_row(g['cluster_id'], total(claims,g['members'],review['duplicates']),g['decision']) for g in review['groups']])
    st.caption('Proposed totals appear in Event investigation. Only groups marked approved constitute reviewer-approved totals. Agent explanations remain attached to original proposals.')
    with st.expander('Immutable review history'):
        for revision in revisions:
            st.write(f"Revision {revision['revision']} · {revision['created_at']}")
            readable_table(group_rows(revision['payload']['groups']))
            st.write('Confirmed duplicates')
            readable_duplicates(revision['payload']['duplicates'])
            st.write('Dismissed duplicate pairs')
            readable_pairs(revision['payload'].get('dismissed_duplicates',[]))
        if not revisions:
            st.caption('No saved revisions yet.')

with evaluation_tab:
    truth = result.get('evaluation_truth')
    if truth and st.checkbox('Reveal hidden ground truth for this completed run',key=f'reveal-{selected}'):
        st.warning('Ground truth is revealed. Do not use this fixture as an unseen benchmark after tuning against it.')
        st.subheader('Hidden event labels')
        readable_table([{'Notification':claim_id, 'Hidden event':event} for claim_id,event in sorted(truth['events'].items())])
        st.write('Hidden duplicate reference')
        readable_duplicates(truth.get('duplicates',{}))
        st.caption(f"Synthetic seed: {truth.get('seed','Unknown')} · Held-out templates: {'Yes' if truth.get('held_out') else 'No'}")
        methods = {'Rules baseline':result['baseline'], 'Original analysis':[c['members'] for c in proposals],
                   'After review (excluding rejected)':[g['members'] for g in review['groups'] if g['decision']!='rejected'],
                   'Approved only':[g['members'] for g in review['groups'] if g['decision']=='approved']}
        comparisons = {name:evaluate(groups,result['edges'],truth,lookup) for name,groups in methods.items()}
        readable_table([{'Method':name, 'Precision':'N/A' if m['precision'] is None else f"{m['precision']:.3f}",
            'Recall':'N/A' if m['recall'] is None else f"{m['recall']:.3f}",
            'F1':'N/A' if m['f1'] is None else f"{m['f1']:.3f}",
            'Candidate recall':'N/A' if m['candidate_recall'] is None else f"{m['candidate_recall']:.3f}",
            'True pairs':m['true_pairs'], 'Predicted pairs':m['predicted_pairs'],
            'Incorrect merges':len(m['incorrect_merges']), 'Missed pairs':len(m['missed_connections'])} for name,m in comparisons.items()])
        for name, metrics in comparisons.items():
            with st.expander(f'{name}: pair details'):
                st.write('Incorrectly merged pairs')
                readable_pairs(metrics['incorrect_merges'])
                st.write('Missed connections')
                readable_pairs(metrics['missed_connections'])
        st.subheader('Financial canonicalisation check')
        references = financial_reference(claims,[(g['cluster_id'],g['members']) for g in review['groups']],truth,review['duplicates'])
        readable_table([{'Group':r['cluster_id'], 'Review amount':money(r['reported']['known_amount_gbp']),
            'Canonical reference':money(r['hidden_canonical_reference']['known_amount_gbp']),
            'Review missing amounts':r['reported']['missing_amount_count'],
            'Reference missing amounts':r['hidden_canonical_reference']['missing_amount_count'],
            'Review underlying claims':r['reported']['underlying_claim_count'],
            'Reference underlying claims':r['hidden_canonical_reference']['underlying_claim_count'],
            'Matches reference':'Yes' if r['matches_reference'] else 'No'} for r in references])
        st.caption('The financial reference uses hidden canonical notification labels. Differences may reflect unresolved duplicate decisions; they do not imply coverage or payout errors.')
        st.caption('Unassigned claims predict no pairs. Hidden duplicate labels canonicalise notifications only during evaluation. N/A means an empty metric denominator. Pending groups are included only in the explicitly labelled after-review view.')
    elif not truth:
        st.info('No matching ground truth is attached to this uploaded dataset. Accuracy metrics are unavailable.')
    st.subheader('Model activity')
    activity = []
    for stage in result['telemetry']:
        usage = next((u for u in reversed(stage.get('usage',[])) if u.get('total_token_count') is not None),{})
        activity.append({'Stage':stage['stage'], 'Seconds':stage['latency_seconds'],
            'Prompt tokens':usage.get('prompt_token_count'), 'Answer tokens':usage.get('candidates_token_count'),
            'Thinking tokens':usage.get('thoughts_token_count'), 'Total tokens':usage.get('total_token_count')})
    readable_table(activity, 'No model activity is recorded for this snapshot. Recovered checkpoints do not represent a single continuous run.')
    if 'request_attempts' in result:
        st.write('Provider attempts (including bounded retries)')
        readable_table([{k.replace('_',' ').capitalize():v for k,v in a.items()} for a in result['request_attempts']])
        with st.expander('Execution settings'):
            readable_table([{'Setting':k.replace('_',' ').capitalize(), 'Value':str(v) if v is not None else 'Not set'} for k,v in result['request_policy'].items()])
    export = dict(run_id=selected,snapshot_hash=run['snapshot_hash'],mode=run['snapshot']['mode'],proposals=result['proposals'],review=review,telemetry=result['telemetry'],request_attempts=result.get('request_attempts',[]))
    st.download_button('Download sanitised investigation JSON',json.dumps(export,indent=2),'claimcascade-report.json','application/json')
    st.download_button('Download snapshot claims CSV',dump_claims_csv(claims),'claimcascade-claims.csv','text/csv')
