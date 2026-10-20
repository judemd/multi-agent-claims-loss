# Local validation — 19 October 2026

Latest reliability follow-up: **44 offline tests passed** and all four agents
completed on a 10-claim live synthetic sample. A recovered 50-claim run validated
all extraction batches and the investigator, then timed out in the challenger.
An isolated challenger diagnostic subsequently passed in 8.92 seconds. The isolated
reporter returned in 21.53 seconds and passed schema checks, but failed manual
factual review because its prose includes unassigned claims in membership ranges;
see [the detailed Vertex validation](vertex-validation.md) for limits and exact
results. An offline correction now validates explicit member references and source
quotations. The revised reporter subsequently passed one isolated live test in
27.70 seconds with 30 exact source quotations and valid member references. A fresh
reliable full workflow remains unverified. Public paid calls remain disabled.
Offline linked-checkpoint assembly now produces a pending-review Markdown and
JSON artifact. Recovered development-fixture pair F1 is 0.929 versus baseline 0.760;
this reused fixture is not a blind benchmark. The 44-test suite also checks
assembly provenance and rejects invalid reporter references.

## Deployment verification — 20 October 2026

- Latest offline suite: **13 passed** (`--basetemp .test-tmp7`), including public-mode
  refusal of paid calls even when the paid-call environment flag is true.
- Cloud Build produced the Linux Docker image successfully. The manifest pins
  `sha256:f2a072148bb0325bfe0968079d02443956e5e88b37b2177da4b8bb71029b7ae9`.
- Cloud SQL PostgreSQL 16: created, written, reopened through a fresh connection;
  saved run and review found. Application role's administrative privileges checked
  and absent. Secret URL created without printing or writing credentials locally.
- Private Cloud Run Chrome test: Streamlit WebSocket UI loaded, existing snapshot
  reused, review saved, charts rendered, uploader buttons disabled, history reopened.
- New Cloud Run revision `claimcascade-00002-5q5`: a new browser session reopened
  the same persisted run and review after container replacement.
- Anonymous Chrome test passed after publication, including generating synthetic
  data, reusing its snapshot, saving a review and reopening history after reload.
- Anonymous `/_stcore/health`: HTTP 200, body `ok`.
- No model calls were triggered by the hosted browser checks.

Live Vertex test: first extraction batch completed; the second returned
`429 RESOURCE_EXHAUSTED`. Two logical stages started, one completed. Full live
clustering and accuracy evaluation were not reached; the full run was not replayed.
There were no application retries; provider SDK transport retries may have occurred.
The public service keeps paid calls disabled.

Public URL: https://claimcascade-qbfmgrh25a-nw.a.run.app

The remaining section records the earlier local-only validation state.

## Earlier local checks

Environment: Windows PowerShell, project-local CPython 3.11.16, dependencies
installed into `.venv`. Exact resolved dependency versions are in `requirements.lock`.

Completed checks:

- `python -m pytest -q --basetemp .test-tmp5`: **12 passed**.
- Actual ADK 2.12 graph executed all eight logical model stages against an offline
  deterministic model double, with validated output and no network inference.
- Streamlit AppTest generated data, analysed it, reran the UI and repeated Analyse;
  only one completed snapshot was stored.
- Review revision checks confirmed edited approvals reset to pending while the
  previous approved revision remains unchanged.
- Model request inspection confirmed hidden label payloads are absent.
- `uv pip check`: all installed packages compatible.
- Six fixture datasets generated reproducibly and CSV round-trip tested.
- Five held-out baseline seeds evaluated: pairwise precision 0.977–1.000,
  recall 0.622, F1 0.760–0.767, candidate recall 0.822. This is a small synthetic
  benchmark, not a real-world performance estimate or a live agent comparison.
- Python compilation check passed.
- Streamlit started on `http://127.0.0.1:8501`; `/_stcore/health` returned HTTP 200.
- Git staged whitespace check passed after correcting CSV line endings.

One third-party OpenTelemetry deprecation warning remains during the ADK test.

Not verified:

- Paid Vertex inference, model availability in the selected project, ADC refresh
  and runtime IAM permissions.
- PostgreSQL/Cloud SQL connection and persistence. Local tests use SQLite.
- Docker image build: Docker's engine is not running.
- Cloud Run deployment, public URL, restart durability and cloud billing settings.
- GitHub Actions execution on its hosted Linux runner.

Proposed separately approved live test: generate the default 50-claim fixture,
run one live investigation locally using Gemini 3.5 Flash, and inspect the eight
logical calls, token usage, latency, validated evidence, objections and pairwise
metrics. No application retries. Actual transport requests can exceed logical
calls if the provider SDK retries. Do not infer spending from call count alone.
