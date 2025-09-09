## GCP POC – Serverless Data Platform (Wikipedia)

This PoC deploys a serverless ingestion service on Google Cloud that fetches Wikipedia pageviews and writes to BigQuery. It includes CI/CD (Cloud Build → Artifact Registry → Cloud Run), scheduling (Cloud Scheduler → OIDC to Cloud Run), basic observability (structured logs, log-based metrics, alert), and a minimal BQML model.

### Architecture
- Cloud Run: FastAPI service `/health`, `/ingest`
- Artifact Registry: container images
- Cloud Build: tests → build → push → deploy via `cloudbuild.yaml`
- Cloud Scheduler: daily trigger (OIDC) → Cloud Run
- BigQuery: datasets `raw`, `staging`, `mart`, `models`
- BQML: simple k-means model `models.article_kmeans`
- Logging/Monitoring: structured logs, log-based metrics, alert policy

### Prerequisites
- gcloud CLI, Python 3.11+, Docker (optional, Cloud Build is used)
- GCP project with Owner access for initial setup
- GitHub repo connected to Cloud Build (optional for trigger)

### One-time Setup (already executed in this project)
```bash
export PROJECT_ID=gcp-poc-471514
export REGION=europe-north1
export BQ_LOC=EU
export AR_REPO=containers
export SERVICE=ingest
export RUNTIME_SA=run-svc@$PROJECT_ID.iam.gserviceaccount.com
export SCHED_SA=scheduler-invoker@$PROJECT_ID.iam.gserviceaccount.com

gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com bigquery.googleapis.com logging.googleapis.com monitoring.googleapis.com \
  iamcredentials.googleapis.com

gcloud artifacts repositories create $AR_REPO --repository-format=docker --location=$REGION || true
gcloud iam service-accounts create run-svc --display-name="Cloud Run runtime SA" || true
gcloud iam service-accounts create scheduler-invoker --display-name="Scheduler OIDC invoker" || true
```

### Build and Deploy (Cloud Build)
```bash
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions=_REGION=$REGION,_AR_REPO=$AR_REPO,_SERVICE=$SERVICE,_TAG=manual
```

### Cloud Run URL
```bash
gcloud run services describe $SERVICE --region $REGION --format='value(status.url)'
```

### Manual Smoke Tests
```bash
SERVICE_URL=$(gcloud run services describe $SERVICE --region $REGION --format='value(status.url)')
TOKEN=$(gcloud auth print-identity-token)
curl -s -H "Authorization: Bearer $TOKEN" "$SERVICE_URL/health"
curl -s -H "Authorization: Bearer $TOKEN" "$SERVICE_URL/ingest?pages=Stockholm,Sweden"
```

### Scheduler (created in europe-west1)
```bash
SERVICE_URL=$(gcloud run services describe $SERVICE --region $REGION --format='value(status.url)')
gcloud scheduler jobs create http wiki-ingest-daily \
  --location=europe-west1 \
  --schedule="0 6 * * *" --time-zone="Europe/Stockholm" \
  --uri="$SERVICE_URL/ingest?pages=Stockholm,Sweden" \
  --http-method=GET \
  --oidc-service-account-email=$SCHED_SA \
  --oidc-token-audience="$SERVICE_URL"
```

### BigQuery
- Table: `raw.wikipedia_pageviews`
- View: `mart.article_daily` (see `bq/sql/mart_article_daily.sql`)
- Model: `models.article_kmeans` (see `bq/bqml/*`)

### Observability
- Structured logs with event `ingest_done`
- Log-based metrics: `ingest_success`, `ingest_errors`
- Simple alert policy on errors

### Local Development
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/ingest/requirements.txt -r requirements-dev.txt
export PYTHONPATH=.
pytest -q
uvicorn app.ingest.main:app --reload --port 8080
```

### Repository Structure
```
/app
  /ingest
    main.py
    requirements.txt
/bq
  /sql
    mart_article_daily.sql
  /bqml
    create_model.sql
    evaluate_model.sql
cloudbuild.yaml
Dockerfile
requirements-dev.txt
```

### Notes
- GitHub trigger: connect the repo to Cloud Build in Console, then create a branch trigger on `main` using `cloudbuild.yaml`.
- This PoC grants broad IAM for speed; tighten roles for production.


