# Deploying RevenueGuard to Cloud Run

The public hosted URL the hackathon requires. Two paths — `adk deploy` (simplest)
or the Dockerfile (more control). Both assume Phase 0 is done: GCP project created,
Vertex AI + BigQuery enabled, demo data seeded, Fivetran MCP cloned into `vendor/`.

## Prerequisites

```bash
gcloud auth login
gcloud config set project "$GOOGLE_CLOUD_PROJECT"
gcloud services enable run.googleapis.com aiplatform.googleapis.com bigquery.googleapis.com
```

The Cloud Run service account needs **Vertex AI User** and **BigQuery Data Viewer +
Job User** on the project. No keys in the repo — auth is via the service account.

## Path A — `adk deploy cloud_run` (recommended)

```bash
adk deploy cloud_run \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$GOOGLE_CLOUD_LOCATION" \
  --service_name revenueguard \
  --with_ui \
  revenueguard
```

## Path B — Dockerfile

```bash
# Build from the REPO ROOT so vendor/ and revenueguard/ are in the context.
gcloud builds submit --tag "gcr.io/$GOOGLE_CLOUD_PROJECT/revenueguard" \
  --config /dev/stdin <<'YAML'
steps:
  - name: gcr.io/cloud-builders/docker
    args: ['build', '-f', 'deploy/Dockerfile', '-t', 'gcr.io/$PROJECT_ID/revenueguard', '.']
images: ['gcr.io/$PROJECT_ID/revenueguard']
YAML

gcloud run deploy revenueguard \
  --image "gcr.io/$GOOGLE_CLOUD_PROJECT/revenueguard" \
  --region "$GOOGLE_CLOUD_LOCATION" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT,GOOGLE_GENAI_USE_VERTEXAI=true,RG_DATASET=revenueguard_demo,RG_AS_OF_DATE=2026-06-08,FIVETRAN_ALLOW_WRITES=true" \
  --set-secrets "FIVETRAN_API_KEY=fivetran-api-key:latest,FIVETRAN_API_SECRET=fivetran-api-secret:latest"
```

Store the Fivetran credentials in Secret Manager first:

```bash
printf '%s' "$FIVETRAN_API_KEY"    | gcloud secrets create fivetran-api-key    --data-file=-
printf '%s' "$FIVETRAN_API_SECRET" | gcloud secrets create fivetran-api-secret --data-file=-
```

## Notes

- The Fivetran MCP server runs as a **stdio child process** inside the container, so
  `vendor/fivetran-mcp/` must be present at build time (it's gitignored — copy it in
  locally before building, or add a clone step to the Dockerfile).
- If `gemini-3.0-pro-preview` 404s in your region, set `RG_MODEL=gemini-2.5-pro`.
- Verify the model resolves and the region is correct **before** demo day.
