# Google Cloud deployment

Deployed and verified on **20 October 2026**.

Public demo: https://claimcascade-qbfmgrh25a-nw.a.run.app

Ready revision: `claimcascade-00002-5q5`. The pinned image digest is recorded in
[`deploy/cloudrun.yaml`](../deploy/cloudrun.yaml). Private and anonymous Chrome
checks passed, including a saved review, reload, and reopening history on a new
Cloud Run revision. Anonymous health endpoint returned HTTP 200.

Target repository: https://github.com/judemd/multi-agent-claims-loss

Target project discovered locally: `project-d4ec743e-de8a-4ed5-b45`.
The approved hosting region is `europe-west2`.
The model location is configured separately and initially uses `global`.

Provisioned resources:

| Resource | Proposed configuration |
|---|---|
| Artifact Registry | Regional Docker repository `claimcascade` |
| Cloud Run | Service `claimcascade`, 1 CPU, 1 GiB RAM, min 0 / max 1 instance, concurrency 10, session affinity, 3600-second request timeout |
| Cloud SQL | PostgreSQL 16, single-zone development instance, smallest suitable shared-core configuration, 10 GB SSD, automatic backups |
| Secret Manager | Database connection URL, available only to the runtime identity |
| Service account | `claimcascade-runtime`, Cloud SQL Client and access to its one database secret; no model permission needed for the rules-only public release |
| Public access | Anonymous access for synthetic-data demo only |

Cloud SQL incurs continuing charges even with no visitors. Cloud Run, image storage,
builds, secrets, network traffic and later Vertex calls may also incur charges.
The SQL Admin and Secret Manager APIs were enabled. The resources and scoped IAM
grants above were created under the user's deployment approval. Existing services
were preserved. Project billing was already enabled and was not changed.

The first public revision uses `CLAIMCASCADE_PUBLIC_DEMO=true` and
`CLAIMCASCADE_ALLOW_PAID_CALLS=false`. It permits synthetic generation and shared,
unauthenticated demonstration reviews. It is not a private claims system. Anyone
with the URL can view the demo history and edit demonstration reviews. Use a
dedicated empty demo database; never reuse a local claims database.

Live agent testing should happen locally or on a private Cloud Run revision first.
Before public paid analysis is enabled, add an approved access/budget policy. A
maximum-instance setting alone does not cap model spending.

## Build and deployment record

Cloud Build `20ea215f-79ba-4f9b-a9a2-d93c34f90705` succeeded in `europe-west2`,
building the Linux image from application commit `4aa5c8b`. The local Docker engine
was unavailable, so the build used the approved Cloud Build path.

The first revision was tested privately. The second revision added release metadata
to start a fresh container; existing runs and review history remained available.
Only after those checks did the service receive `allUsers` / `roles/run.invoker`.

The database uses a dedicated `claimcascade_app` role with no superuser,
create-database, create-role or replication privileges. Passwords were generated
in memory. The application URL is held in Secret Manager, version 1, and is never
stored in the repository or supplied as a plaintext deployment argument.

For future rebuilds:

Build locally with Docker when its engine is running, or approve a Cloud Build job.
Use the committed Dockerfile and a Git commit SHA as the image tag. Do not upload
`.env`, local databases, runtime caches, credentials or ground-truth fixtures.
`.dockerignore` and `.gcloudignore` define these exclusions.

## Runtime settings

```text
GOOGLE_CLOUD_PROJECT=<approved project>
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_ENTERPRISE=true
GEMINI_MODEL=gemini-3.5-flash
CLAIMCASCADE_PUBLIC_DEMO=true
CLAIMCASCADE_ALLOW_PAID_CALLS=false
DATABASE_URL=<Secret Manager reference, not a plaintext deployment argument>
```

Attach the Cloud SQL instance to Cloud Run. The database URL uses:
`postgresql+psycopg://USER:URL_ENCODED_PASSWORD@/DATABASE?host=/cloudsql/PROJECT:REGION:INSTANCE`.
Never commit the actual URL. Use a database-specific user, not the PostgreSQL admin.
The runtime automatically creates the initial tables; this POC has no migration
framework. For a future schema change, add reviewed migrations before updating a
database with existing reviews.

Cloud Run supplies `PORT`; the Docker entrypoint binds Streamlit to that port.
WebSocket reconnects can lose unsaved browser state, while committed runs and
reviews remain in Cloud SQL. Session affinity is best effort, not durability.

## Verification procedure

1. Test the container against PostgreSQL, including saving and reopening reviews.
2. Verify no uploads or model calls are enabled in public mode.
3. Deploy and inspect the generated Cloud Run URL and application health.
4. Generate synthetic claims, run rules analysis, save a review, restart an instance,
   and verify history survives.
5. Confirm runtime identity, secret access, logs and billing configuration.

Operator scripts:

- `scripts/bootstrap_cloud_database.py`: initialise this dedicated database and
  secret, or reuse the existing secret; verify role privileges and reopened state.
  Requires `GOOGLE_CLOUD_PROJECT` and administrative ADC. Uses an official local
  Cloud SQL Auth Proxy, bound only to loopback, and stops it after testing.
- `scripts/browser_smoke.py URL`: synthetic browser workflow, disabled uploader
  checks and reopened history. Requires Playwright and installed Chrome. Use
  `--private` before anonymous publication and `--verify-only` to avoid edits.
- `scripts/live_test.py`: explicitly gated operator-only Vertex test; writes local
  evidence under ignored `data/live-tests`. No automatic application retry.

## Live inference limitation

The approved live test reached Vertex successfully and completed `extractor_0`.
`extractor_1` returned `429 RESOURCE_EXHAUSTED`, stopping the test before any event
proposals or live evaluation were produced. Two logical stages were started; one
completed. No full test was replayed. Provider SDK transport retries may have
occurred. Do not interpret this as a successful end-to-end live agent run.

Public paid calls remain disabled. A later live test needs available model capacity
and a separately agreed retry/call budget; no quota or billing limits were changed.

## References

- [Cloud Run WebSockets](https://docs.cloud.google.com/run/docs/triggering/websockets)
- [Cloud Run to Cloud SQL PostgreSQL](https://docs.cloud.google.com/sql/docs/postgres/connect-run)
- [Public access](https://docs.cloud.google.com/run/docs/authenticating/public)
- [Runtime environment variables](https://docs.cloud.google.com/run/docs/configuring/services/environment-variables)
