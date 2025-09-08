FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (if needed for bigquery libs)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY app/ingest/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

# Copy application code
COPY app /app/app

EXPOSE 8080
CMD ["uvicorn", "app.ingest.main:app", "--host", "0.0.0.0", "--port", "8080"]


