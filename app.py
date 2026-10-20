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

load_dotenv()
public_demo = os.getenv('CLAIMCASCADE_PUBLIC_DEMO','false').lower() == 'true'
st.set_page_config(page_title='ClaimCascade', layout='wide')
st.title('ClaimCascade')
st.caption('Shared loss event investigation · fictional region · human decisions required')
st.info('Investigation aid. Shared-event groups do not determine coverage, liability, reserves, fraud or contractual reinsurance aggregation.')


@st.cache_resource
def database():
    return Store()


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
        st.dataframe(st.session_state.dataset, hide_index=True)
        with st.expander('Bulletin evidence (unconfirmed)'):
            st.json(st.session_state.bulletins)
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
    st.write('Unassigned claims:',result['proposals']['unassigned'])
    for cluster in proposals:
        with st.expander(f"{cluster['cluster_id']} · {cluster['description']}"):
            st.write('Proposed membership:',cluster['members'])
            st.json(result['totals'][cluster['cluster_id']])
            st.write('Ambiguities:',cluster['ambiguities'])
            for e in cluster['evidence']:
                st.write(f"{e['claim_id']}: {e['excerpt']}")
            st.write('Challenger objections:',[o for o in result['challenge']['objections'] if o['cluster_id']==cluster['cluster_id']])
            if checked_report:
                explanation = next(e for e in checked_report.explanations if e.cluster_id == cluster['cluster_id'])
                st.write('Source observations:')
                for fact in explanation.observed_facts:
                    st.write(f'{fact.claim_id}: {fact.excerpt}')
                for label, statements in [('Hypotheses (unproven)', explanation.hypotheses),
                                          ('Missing information', explanation.missing_information)]:
                    st.write(label)
                    for statement in statements:
                        st.write('Referenced claims:', statement.claim_ids)
                        st.write(statement.text)

with review_tab:
    st.caption('Edit rows to add/remove claims or split a group into new rows. Claim IDs are comma-separated. Review the evidence and objections in Event investigation before approval. Editing a saved revision resets decisions to pending.')
    rows = [dict(cluster_id=g['cluster_id'],claim_ids=','.join(g['members']),decision=g['decision'],note=g.get('note','')) for g in review['groups']]
    if not rows:
        rows = [dict(cluster_id='',claim_ids='',decision='pending',note='')]
    with st.form(f'review-{selected}-{len(revisions)}'):
        edited = st.data_editor(rows,num_rows='dynamic',key=f'members-{selected}-{len(revisions)}',use_container_width=True,
            column_config={'decision':st.column_config.SelectboxColumn(options=['pending','approved','rejected'],required=True)})
        st.write('Suspected duplicates (not automatically excluded):',suspected_duplicates(claims))
        dup_text = st.text_area('Confirmed duplicates JSON: duplicate notification → canonical notification. The selected canonical amount is used.',value=json.dumps(review['duplicates']))
        dismissed = st.text_area('Dismissed duplicate pairs JSON',value=json.dumps(review.get('dismissed_duplicates',[])))
        save = st.form_submit_button('Save review revision')
    if save:
        try:
            payload = {'groups':[dict(cluster_id=r['cluster_id'],members=[m.strip() for m in r['claim_ids'].split(',') if m.strip()],decision=r['decision'],note=r.get('note','')) for r in edited if r.get('cluster_id') or r.get('claim_ids')],
                       'duplicates':json.loads(dup_text),'dismissed_duplicates':json.loads(dismissed)}
            payload = review_revision(payload,review if revisions else None,claims)
            store.save_review(selected,payload)
            st.success('Revision saved. Reopen or rerun to display the latest totals.')
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    for group in review['groups']:
        st.write(f"{group['cluster_id']} · {group['decision']}",total(claims,group['members'],review['duplicates']))
    st.caption('Proposed totals appear in Event investigation. Only groups marked approved constitute reviewer-approved totals. Agent explanations remain attached to original proposals.')
    with st.expander('Immutable review history'):
        st.json(revisions)

with evaluation_tab:
    truth = result.get('evaluation_truth')
    if truth and st.checkbox('Reveal hidden ground truth for this completed run',key=f'reveal-{selected}'):
        st.warning('Ground truth is revealed. Do not use this fixture as an unseen benchmark after tuning against it.')
        st.json(truth)
        methods = {'Rules baseline':result['baseline'], 'Original analysis':[c['members'] for c in proposals],
                   'After review (excluding rejected)':[g['members'] for g in review['groups'] if g['decision']!='rejected'],
                   'Approved only':[g['members'] for g in review['groups'] if g['decision']=='approved']}
        for name, groups in methods.items():
            st.write(name,evaluate(groups,result['edges'],truth,lookup))
        st.write('Financial canonicalisation check',financial_reference(claims,
            [(g['cluster_id'],g['members']) for g in review['groups']],truth,review['duplicates']))
        st.caption('The financial reference uses hidden canonical notification labels. Differences may reflect unresolved duplicate decisions; they do not imply coverage or payout errors.')
        st.caption('Unassigned claims predict no pairs. Hidden duplicate labels canonicalise notifications only during evaluation. N/A means an empty metric denominator. Pending groups are included only in the explicitly labelled after-review view.')
    elif not truth:
        st.info('No matching ground truth is attached to this uploaded dataset. Accuracy metrics are unavailable.')
    st.write('Model telemetry:',result['telemetry'])
    if 'request_attempts' in result:
        st.write('Provider attempts (including bounded retries):',result['request_attempts'])
        st.write('Execution policy:',result['request_policy'])
    export = dict(run_id=selected,snapshot_hash=run['snapshot_hash'],mode=run['snapshot']['mode'],proposals=result['proposals'],review=review,telemetry=result['telemetry'],request_attempts=result.get('request_attempts',[]))
    st.download_button('Download sanitised investigation JSON',json.dumps(export,indent=2),'claimcascade-report.json','application/json')
    st.download_button('Download snapshot claims CSV',dump_claims_csv(claims),'claimcascade-claims.csv','text/csv')
