import os
import json
import urllib.parse
from datetime import date, timedelta
from typing import List, Dict, Any

import requests
from fastapi import FastAPI, HTTPException, Query
from google.cloud import bigquery


app = FastAPI(title="Ingest Service", version="0.1.0")


def get_env_variable(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Required environment variable '{name}' is not set")
    return value


def get_previous_day() -> date:
    return date.today() - timedelta(days=1)


def build_wikimedia_url(project: str, article: str, target_day: date) -> str:
    # API doc: https://wikimedia.org/api/rest_v1/#/Pageviews%20data/get_metrics_pageviews_per_article__project___access___agent___article___granularity___start___end_
    encoded_article = urllib.parse.quote(article, safe="")
    day_str = target_day.strftime("%Y%m%d")
    return (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"{project}/all-access/user/{encoded_article}/daily/{day_str}/{day_str}"
    )


def get_request_headers() -> Dict[str, str]:
    user_agent = (
        "gcp-poc-ingest/0.1 (https://github.com/rafaelschmidl/gcp-poc; "
        "mailto:ralfarino@gmail.com)"
    )
    return {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }


def fetch_views_for_articles(project: str, articles: List[str], target_day: date) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for article in articles:
        url = build_wikimedia_url(project=project, article=article, target_day=target_day)
        resp = requests.get(url, headers=get_request_headers(), timeout=30)
        if resp.status_code == 404:
            # Missing page or no data for that day — skip gracefully
            continue
        if not resp.ok:
            raise HTTPException(status_code=502, detail=f"Upstream error for {article}: {resp.text}")
        payload = resp.json()
        for item in payload.get("items", []):
            # Schema alignment: view_date: DATE, project: STRING, article: STRING, views: INT64
            year = int(item["timestamp"][0:4])
            month = int(item["timestamp"][4:6])
            day = int(item["timestamp"][6:8])
            rows.append(
                {
                    "view_date": date(year, month, day).isoformat(),
                    "project": item.get("project", project),
                    "article": item.get("article", article),
                    "views": int(item.get("views", 0)),
                }
            )
    return rows


def insert_rows_to_bigquery(full_table_id: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"inserted": 0, "errors": []}
    client = bigquery.Client()
    errors = client.insert_rows_json(full_table_id, rows)
    if errors:
        # errors is a list of row-level errors
        raise HTTPException(status_code=500, detail={"message": "BigQuery insert errors", "errors": errors})
    return {"inserted": len(rows), "errors": []}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/ingest")
def ingest(
    pages: str = Query(
        default="Stockholm,Sweden",
        description="Comma-separated list of Wikipedia page titles (case-sensitive)",
    ),
    project: str = Query(
        default="en.wikipedia.org",
        description="Wikimedia project (e.g. en.wikipedia.org, sv.wikipedia.org)",
    ),
) -> Dict[str, Any]:
    project_id = get_env_variable("PROJECT_ID")
    bq_table = get_env_variable("BQ_TABLE")  # e.g. raw.wikipedia_pageviews

    target_day = get_previous_day()
    articles = [p.strip() for p in pages.split(",") if p.strip()]
    if not articles:
        raise HTTPException(status_code=400, detail="No pages provided")

    rows = fetch_views_for_articles(project=project, articles=articles, target_day=target_day)
    full_table_id = f"{project_id}.{bq_table}"
    result = insert_rows_to_bigquery(full_table_id, rows)

    # Structured JSON log for observability
    log_obj = {
        "event": "ingest_done",
        "day": target_day.isoformat(),
        "articles": articles,
        "inserted": result["inserted"],
        "table": bq_table,
    }
    print(json.dumps(log_obj, ensure_ascii=False))

    return {
        "project_id": project_id,
        "table": bq_table,
        "day": target_day.isoformat(),
        "articles": articles,
        "inserted": result["inserted"],
    }


if __name__ == "__main__":
    # For local debugging only; in production run via uvicorn in Dockerfile
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))


