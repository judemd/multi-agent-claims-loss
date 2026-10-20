# ClaimCascade

**Public demo:** https://claimcascade-qbfmgrh25a-nw.a.run.app

The hosted demo uses synthetic data and rules-only analysis. Uploads and paid model
calls are disabled; demonstration history and reviews are shared publicly.

A small commercial-property insurance investigation POC. It helps a reviewer
connect notifications that may share an initiating incident, inspect evidence and
contradictions, and record membership and duplicate decisions. Shared-event
clustering does not determine coverage, liability, reserves, fraud or contractual
reinsurance aggregation.

The region is fictional, using Cartesian x/y coordinates in kilometres (0–100).
All generated businesses are fictional. Amounts are GBP and always labelled
**Reported claim amount**. Missing amounts remain unknown.

## Quick start (Windows PowerShell)

From the repository root with Python 3.11 installed:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m streamlit run app.py
```

This workspace already contains a project-local Python 3.11 runtime and `.venv`.
Neither belongs in Git. Configuration loads from `.env` without overriding
environment variables. Default persistence is `data/claimcascade.db`.

## Five-minute walkthrough

1. In Data, generate the default 50 synthetic notifications. Inspect source data
   and incomplete bulletin evidence. Ground-truth labels are absent from previews.
2. Keep **Rules only — no model calls**, distance 10 km, interval gap 24 hours.
   Select **Analyse**.
3. Explore the fictional spatial plot, incident timeline, proposed groups and
   unassigned notifications. The rules-only mode has no agent explanations.
4. In Review, edit comma-separated member IDs, add rows to split a cluster, and
   approve/reject/leave pending. Remove a claim from a row to leave it unassigned.
   Each group needs at least two underlying claims. Inspect original evidence and
   challenger objections before approving a live agent proposal.
5. Confirm duplicates by mapping a duplicate notification ID to the chosen
   canonical notification. That notification's reported amount is the explicit
   canonical amount choice; inspect conflicting amounts before confirming.
6. Save the revision, inspect updated totals and history, then reveal ground truth
   in Evaluation. Download JSON and CSV reports without hidden labels.

The application does not provide an agent simulation in its normal UI. Rules-only
analysis is a real deterministic baseline. Tests use deterministic model doubles;
those outputs are **scripted simulation**, not live model results.

## Architecture

Streamlit calls deterministic validation/matching services, followed in live mode
by a Google ADK graph of four ordered stages. Each stage invokes an ADK LlmAgent;
Python validates outputs before the next stage. SQLite is local persistence;
SQLAlchemy also supports Cloud SQL PostgreSQL using `DATABASE_URL`.

| Agent | Role |
|---|---|
| Claim extractor | Batched cause, timing, assets, wider-event indicators, conflicts and exact source excerpts |
| Event investigator | Evidence-supported memberships, ambiguities and explicit unassigned claims |
| Challenger | Suggested removals/splits and objections, without silently changing proposals |
| Reporter | Facts, hypotheses and missing information using Python-provided financial totals |

Challenger objections stay attached for human resolution. Structural validation
does not establish a common cause. Narratives and bulletins are untrusted evidence;
agents have no arbitrary filesystem, ground-truth or financial calculation tools.
Exact excerpt validation verifies provenance, not the semantic truth of a claim.

`claimcascade/core.py` contains matching, validation and money calculations;
`agents.py` contains live ADK integration; `services.py` handles rules and reviews;
`persistence.py`, `synthetic.py`, `evaluation.py` cover their respective functions.
`app.py` supplies the four UI panels. No separate backend, vector database, RAG
framework, weather feed or production claims integration is used.

## Vertex AI configuration

Authenticate locally without service-account key files:

```powershell
gcloud config get-value project
gcloud auth application-default login
```

Set `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` and `GEMINI_MODEL` in `.env`.
ADK 2.12 uses `GOOGLE_GENAI_USE_ENTERPRISE=true` for the Google Cloud provider;
the older Vertex switch is retained in the example for compatibility.
The authenticated identity needs permission to use the configured model.

Paid calls are disabled by default. After explicit approval, set
`CLAIMCASCADE_ALLOW_PAID_CALLS=true`, then choose Live Vertex AI agents. Normal live
mode never substitutes mocked responses. For 50 claims it makes five extractor
calls and one each for investigation, challenge and reporting: eight logical calls.
Each attempt allows one model call, 8,192 output tokens and 90 seconds; the full
run has a ten-minute timeout. Request starts are spaced by at least 30 seconds.
SDK transport retries and automatic generation continuations are explicitly disabled. The application permits one retry
per stage only for structured provider errors 429 or 503, using capped backoff and
jitter, and respects numeric Retry-After headers. The whole run stops after at
most 12 provider attempts. Authentication, schema/evidence errors, cancellation
and timeouts with uncertain completion are not retried. Invalid outputs fail
visibly. Live snapshots include this execution policy and pipeline version.
The default Gemini 3.5 configuration uses `LOW` thinking to reduce latency; it
does not request internal thought text. This is a reasoning level, not a guaranteed
token cap or response-time guarantee. For models without thinking-level support,
configure `RequestPolicy(thinking_level=None)` instead.
Temperature defaults to `1.0`, following Google's Gemini 3 guidance; lower values
can cause looping or degraded performance. This configuration is included in the
frozen live-run policy. Exact excerpts and memberships remain deterministically
validated regardless of sampling temperature.

The extractor receives only claim IDs and narratives. Its generated schema limits
IDs and verbatim quotes to that batch's sources, preventing structured-field text
from being presented as a narrative quote. The investigator receives the original
structured fields alongside extracted narrative facts and records contradictions.
ADK requests use SSE streaming. Operator diagnostics can record the first ADK
content event without logging response text. This helps distinguish missing output
from later stream/validation delays; it does not guarantee provider latency.

The operator test accepts `--min-interval`, `--max-attempts` (hard maximum 12),
`--retries-per-stage` (0 or 1), `--seed`, `--held-out` and `--claim-count` (1–50),
and saves attempt events, usage and schema-validated stage outputs locally as it
runs. Schema validation alone does not establish evidence or membership validity;
the pipeline still checks those before subsequent stages. Partial output files
are diagnostic evidence and never silently resumed. An operator may explicitly
pass `--reuse-extractions FILE` for source-validated extraction outputs only.
Dataset identity and generation settings must match, each batch is revalidated
before any request, and file/output hashes record lineage. Proposals and reviewer
approvals are never recovered this way. Older files without model metadata are
marked in provenance and require the operator to establish their model externally.

## Matching and financial rules

A shared event is one initiating incident with a coherent time interval and area.
Separate local incidents during one storm need not be one event. Multi-incident
claims are unresolved under the one-cluster-per-notification restriction.

Candidates require distance at or below the configured limit. Incident intervals
overlap or have a gap no larger than the configured limit. Missing incident time
does not become notification time: a spatial candidate is retained with timing
unknown. Missing coordinates cannot support spatial matching. Different loss types
remain eligible. A graph path does not prove shared-event membership.

The rules baseline sorts claim IDs and uses complete-link grouping: every pair
inside a group must satisfy both time and distance limits with known timing.
It is order-sensitive and ignores narrative compatibility. Candidate generation
uses structured incident times; narrative conflicts remain evidence rather than
silently changing those supplied fields.

Currency uses Decimal calculations without binary floating-point arithmetic.
Suspected duplicates remain counted. Confirmed duplicates count the canonical
notification once and retain all source records. No duplicate chains or cycles are
accepted. Conflicting canonical amounts require a reviewer choice; unknown stays
unknown. Proposed and reviewed totals are shown separately. Only explicitly
approved groups constitute reviewer-approved totals.

## Persistence and review

Runs freeze input content, bulletins, settings, mode, model and pipeline version.
An identical completed/running snapshot is reused; ordinary Streamlit reruns do
not trigger another model call. Failed runs remain historical records; an explicit
Analyse can retry a failed snapshot. A process killed mid-run can leave a `running`
record requiring operator investigation; there is no automatic paid replay.

Reviews append immutable revisions with membership, decisions, notes, duplicate
decisions and UTC timestamps. Membership/duplicate changes after a saved review
reset affected decisions to pending. Approve the saved revision again to confirm.
Changes to input or settings produce a different snapshot and do not reuse approvals.
Original proposals and agent reports remain tied to their original memberships.
Human-edited summaries/totals are deterministic; edits do not trigger paid reporting.

This is a single-reviewer POC. Concurrent editing, automatic run recovery,
production migrations and private multi-user permissions are outside scope.

## Synthetic fixtures and evaluation

```powershell
.\.venv\Scripts\python.exe -m claimcascade.synthetic
.\.venv\Scripts\python.exe -m pytest -q --basetemp .test-tmp
```

Fixtures include one development seed and five held-out seeds with different
narrative templates. Each has three shared events, unrelated incidents, similar
descriptions of different incidents, missing/inconsistent times and two duplicate
notifications. Bulletins cover only part of the events and are unconfirmed.
Hidden event IDs and duplicate mappings live in `fixtures/ground_truth`, separately
from operational CSV and JSON. UI generation retains labels in evaluation-only
state, attaching them only after analysis finishes. They never enter matching or
agent inputs. After labels are revealed, do not tune and call the same seed unseen.

Pairwise precision is correct predicted same-event pairs / predicted pairs; recall
is correct predicted pairs / true pairs; F1 is their harmonic mean. Unassigned
claims contribute no predicted pairs. Empty denominators are N/A. Candidate recall
is true pairs present among candidate edges / true pairs. Hidden duplicate labels
canonicalise notification IDs only during evaluation so repeats do not inflate
event-pair scores. Incorrect merges and missed connections are listed explicitly.
Baseline and agent analysis use the same frozen data. After-review results include
pending groups and exclude rejected groups, with approved-only results shown
separately. These are distinct comparison stages.

Financial calculation correctness is covered by hand-checked tests for decimal
amounts, missing values and canonical duplicates. Model call count, latency and
token usage (when returned by the provider) are recorded. No time-saving claim is
made. Fifty synthetic notifications demonstrate behaviour, not real-world accuracy.

## GitHub and hosting

Target repository: https://github.com/judemd/multi-agent-claims-loss.
GitHub Actions runs offline tests, with no cloud secrets or paid calls.
See [the proposed deployment](docs/deployment.md) for the public Cloud Run service,
Artifact Registry, Cloud SQL and runtime identity. Cloud creation/deployment are
separately approved steps. The initial deployment was approved and verified on
20 October 2026; its exact image and runtime settings are recorded in
[`deploy/cloudrun.yaml`](deploy/cloudrun.yaml).

```powershell
docker build -t claimcascade .
docker run --rm -p 8080:8080 -v claimcascade-data:/app/data claimcascade
```

Public demo mode disables uploads and paid calls and must use a fresh, synthetic
demo database. Public reviews/history are shared and unauthenticated. Live public
analysis needs a separately approved access and spending policy. Do not enter real
claims, personal information or confidential business data into the public demo.

## Limitations and next improvements

The container build, PostgreSQL connectivity, Cloud Run deployment and anonymous
browser workflow have passed external integration checks. A 10-claim live Vertex
run completed all four agents and passed evidence/membership checks after adding
pacing and lower thinking. A recovered 50-claim run validated all extraction
batches and the investigator, then timed out in the challenger after 90 seconds.
An isolated challenger diagnostic subsequently completed in 8.92 seconds with
validated objections, without reproducing the timeout. The isolated reporter
returned in 21.53 seconds and passed schema checks, but manual review found
inaccurate membership ranges in its prose. Its output is not approved; the full
workflow remains unvalidated.
The reporter now uses exact source quotations and explicit member references,
validated before display. ID ranges in hypothesis prose are rejected, and older
reports that fail the new checks show a warning. This correction passes offline
tests and passed an isolated live test in 27.70 seconds with 30 exact source
quotations and valid member references. References establish source
and membership fidelity; they do not establish semantic truth or common cause.
See [the live validation record](docs/vertex-validation.md).
Validated checkpoints can now be assembled offline into a review Markdown and JSON
using `python -m scripts.assemble_recovered INVESTIGATION CHALLENGER REPORTER`.
The recovered development fixture scored pair F1 0.929 versus baseline 0.760;
it is a reused synthetic example, not a blind accuracy estimate. Groups remain
pending review and duplicate candidates remain included in reported totals.
The [source-review draft](docs/synthetic-review.md) records timing holds, duplicate
candidates and conditional amounts for human review; no decisions are approved.
The public container remains pinned to the earlier rules-only release; these new
live controls have not been deployed there. Model behaviour is not deterministic even at zero
temperature. Exact excerpts do not guarantee sound causality; the human reviewer
remains responsible. Missing coordinates reduce candidate recall, duplicate
detection initially flags only identical narratives, and the benchmark is small.
Future work could add measured reviewer comparisons, more varied blind benchmarks,
transaction-safe multi-reviewer editing, migrations and controlled private access.
