# Proposed Google Cloud deployment — not executed

Target repository: https://github.com/judemd/multi-agent-claims-loss

Target project discovered locally: `project-d4ec743e-de8a-4ed5-b45`.
Confirm this project before resource creation. Proposed region: `europe-west2`.
The model location is configured separately and initially uses `global`.

Resources to approve:

| Resource | Proposed configuration |
|---|---|
| Artifact Registry | Regional Docker repository `claimcascade` |
| Cloud Run | Service `claimcascade`, 1 CPU, 1 GiB RAM, min 0 / max 1 instance, concurrency 10, session affinity, 3600-second request timeout |
| Cloud SQL | PostgreSQL 16, single-zone development instance, smallest suitable shared-core configuration, 10 GB SSD, automatic backups |
| Secret Manager | Database connection URL, available only to the runtime identity |
| Service account | `claimcascade-runtime`, Cloud SQL Client; Vertex AI User only when live use is approved |
| Public access | Anonymous access for synthetic-data demo only |

Cloud SQL incurs continuing charges even with no visitors. Cloud Run, image storage,
builds, secrets, network traffic and later Vertex calls may also incur charges.
No resources, APIs, IAM grants or billing settings have been changed.

The first public revision uses `CLAIMCASCADE_PUBLIC_DEMO=true` and
`CLAIMCASCADE_ALLOW_PAID_CALLS=false`. It permits synthetic generation and shared,
unauthenticated demonstration reviews. It is not a private claims system. Anyone
with the URL can view the demo history and edit demonstration reviews. Use a
dedicated empty demo database; never reuse a local claims database.

Live agent testing should happen locally or on a private Cloud Run revision first.
Before public paid analysis is enabled, add an approved access/budget policy. A
maximum-instance setting alone does not cap model spending.

## Build after approval

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

## Verification before publication

1. Test the container against PostgreSQL, including saving and reopening reviews.
2. Verify no uploads or model calls are enabled in public mode.
3. Deploy and inspect the generated Cloud Run URL and application health.
4. Generate synthetic claims, run rules analysis, save a review, restart an instance,
   and verify history survives.
5. Confirm runtime identity, secret access, logs and billing configuration.

## References

- [Cloud Run WebSockets](https://docs.cloud.google.com/run/docs/triggering/websockets)
- [Cloud Run to Cloud SQL PostgreSQL](https://docs.cloud.google.com/sql/docs/postgres/connect-run)
- [Public access](https://docs.cloud.google.com/run/docs/authenticating/public)
- [Runtime environment variables](https://docs.cloud.google.com/run/docs/configuring/services/environment-variables)
