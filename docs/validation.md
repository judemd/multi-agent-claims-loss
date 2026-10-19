# Local validation — 19 October 2026

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
