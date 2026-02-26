# Deployment Guide

## Prerequisites

- **Docker** + Docker Compose v2
- **Python 3.11+** (3.12 tested)
- **4 GB+ RAM** (HHEM model + sentence-transformers + Qdrant)
- **2 GB+ disk** for vector storage and model caches
- **API keys:**
  - `OPENROUTER_API_KEY` (required) -- LLM generation and query expansion
  - `COHERE_API_KEY` (recommended) -- reranking stage; passthrough fallback without it
  - `LAKERA_API_KEY` (recommended) -- L2 ML-based injection detection; L1 regex still active without it

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url> enterprise-pipeline
cd enterprise-pipeline

# 2. Create environment file
cp .env.example .env
# Edit .env and fill in API keys

# 3. Start all services (Qdrant, Langfuse, Redis, Pipeline)
docker compose up -d

# 4. Verify environment
pip install -e ".[dev]"
python scripts/validate_environment.py

# 5. Ingest sample corpus
python scripts/ingest_documents.py \
  --input-dir docs/sample_corpus/ \
  --user-id system \
  --tenant-id default

# 6. Health check
curl http://localhost:8000/health
```

## Service Ports

| Service       | Port  | Purpose                                |
|---------------|-------|----------------------------------------|
| Pipeline API  | 8000  | FastAPI application (`/query`, `/health`, `/metrics`) |
| Qdrant HTTP   | 6333  | Vector store REST API                  |
| Qdrant gRPC   | 6334  | Vector store gRPC (internal)           |
| Langfuse      | 3100  | Trace viewer UI                        |
| Langfuse DB   | 5433  | PostgreSQL for Langfuse (internal)     |
| Redis         | 6379  | Caching layer                          |
| Prometheus    | 9090  | Metrics scraper (monitoring stack)     |
| Grafana       | 3001  | Dashboard UI (monitoring stack)        |

## Environment Variables

| Variable               | Required | Default           | Description                              |
|------------------------|----------|-------------------|------------------------------------------|
| `OPENROUTER_API_KEY`   | Yes      | --                | OpenRouter API key for LLM calls         |
| `COHERE_API_KEY`       | No       | --                | Cohere API key for reranking             |
| `LAKERA_API_KEY`       | No       | --                | Lakera Guard key for L2 injection detect |
| `QDRANT_HOST`          | No       | `localhost`       | Qdrant hostname                          |
| `QDRANT_PORT`          | No       | `6333`            | Qdrant HTTP port                         |
| `QDRANT_API_KEY`       | No       | --                | Qdrant API key (if auth enabled)         |
| `LANGFUSE_PUBLIC_KEY`  | No       | --                | Langfuse public key                      |
| `LANGFUSE_SECRET_KEY`  | No       | --                | Langfuse secret key                      |
| `LANGFUSE_HOST`        | No       | `http://localhost:3100` | Langfuse server URL               |
| `PIPELINE_ENV`         | No       | `development`     | Environment: `development`, `production` |
| `LOG_LEVEL`            | No       | `INFO`            | Logging level                            |
| `LOG_FORMAT`           | No       | `console`         | `console` or `json`                      |
| `API_KEY_ROLES`        | No       | --                | RBAC key-role mappings (`;`-separated)   |

## Configuration

### Pipeline Config

The master configuration file is `pipeline_config.yaml`. It controls:

- Safety thresholds (injection detection, PII patterns)
- Query routing (confidence threshold, route definitions)
- Query expansion (enable/disable, model selection)
- Hallucination detection (HHEM threshold, aggregation method)
- Generation (model selection, fallback model, temperature)
- Compliance (audit log path, retention TTLs)
- Experimentation (feature flags, shadow mode budget)

### Environment Overlays

Environment-specific overrides live in `environments/`:

- `environments/base.yaml` -- shared defaults
- `environments/development.yaml` -- development settings
- `environments/production.yaml` -- production settings (JSON logging, stricter thresholds)

The active overlay is selected by `PIPELINE_ENV`.

### Route Configuration

Query routing rules are in `src/pipeline/routing/routes.yaml`. Each route has:
- A name (e.g., `rag_knowledge_base`, `direct_llm`, `escalate_human`)
- A list of example utterances for semantic matching
- The embedding model compares incoming queries against these utterances

## Docker Deployment

### Full Stack

```bash
# Start everything (Qdrant, Langfuse, Redis, Pipeline)
docker compose up -d

# Check all services are healthy
docker compose ps
curl http://localhost:8000/health
```

### Infrastructure Only (Development)

```bash
# Start just the backing services
make infra

# Run the pipeline locally
make dev
```

### With Monitoring

```bash
# Start core services
docker compose up -d

# Start Prometheus + Grafana
docker compose -f docker-compose.monitoring.yaml up -d

# Access dashboards
# Grafana: http://localhost:3001 (admin/admin)
# Prometheus: http://localhost:9090
```

### Docker Build

The Dockerfile uses a multi-stage build:
1. **Builder stage**: installs Python dependencies and spaCy model
2. **Runtime stage**: copies installed packages and application code

```bash
docker build -t enterprise-pipeline:latest .
```

## Monitoring

### Grafana Dashboard

Access at `http://localhost:3001` (default credentials: `admin` / `admin`).

The pre-provisioned dashboard has 5 rows and 19 panels:
- **Row 1**: Pipeline overview (request rate, latency histograms, error rate)
- **Row 2**: Safety (injection blocks, PII detections)
- **Row 3**: Retrieval health (cosine similarity p50/p95, empty result rate)
- **Row 4**: Quality (HHEM scores, hallucination rate, LLM cost)
- **Row 5**: Feedback & flywheel (feedback rate, annotations pending/completed)

### Prometheus Metrics

The `/metrics` endpoint exposes 34 Prometheus metrics. Prometheus scrapes at 15-second intervals by default.

### Langfuse Tracing

Access the trace viewer at `http://localhost:3100`. Every pipeline execution creates a trace with:
- Full span tree (each pipeline stage is a span)
- Input/output data per stage
- Latency measurements
- HHEM hallucination scores

When Langfuse is unavailable, traces fall back to local JSON files in `traces/local/`.

## RBAC Setup

Set the `API_KEY_ROLES` environment variable to map API keys to roles:

```bash
API_KEY_ROLES="sk-admin-key=security_admin;sk-worker-key=pipeline_worker;sk-viewer-key=viewer"
```

Roles and permissions:
- `security_admin` -- full access including user deletion and audit log read
- `compliance_officer` -- deletion, feedback, audit access
- `pipeline_worker` -- query, ingest, feedback
- `viewer` -- read-only query access
- `annotator` -- feedback submission

## Data Ingestion

```bash
# Ingest documents from a directory
python scripts/ingest_documents.py \
  --input-dir /path/to/documents/ \
  --user-id system \
  --tenant-id default

# Verify ingestion
curl http://localhost:6333/collections/documents | python -m json.tool
```

Supported document formats depend on the ingestion script's parsers. Documents are chunked, embedded with `all-MiniLM-L6-v2`, and stored in Qdrant with metadata (user_id, doc_id, tenant_id).

## Troubleshooting

### Pipeline won't start

1. Check Docker services: `docker compose ps`
2. Verify Qdrant is reachable: `curl http://localhost:6333/healthz`
3. Verify `.env` has `OPENROUTER_API_KEY` set
4. Check logs: `docker compose logs pipeline`

### HHEM model fails to load

- Requires `transformers>=4.40,<5` (v5.x breaks the custom model code)
- First load downloads ~500 MB; subsequent loads use the cache
- Cold start takes ~900ms; warm inference ~150ms per 3 chunks

### High latency

- HHEM accounts for ~344ms of non-LLM overhead -- this is expected (CPU inference)
- LLM generation via OpenRouter typically adds 1-3 seconds
- Check `/metrics` for per-stage latency breakdown
- If token budget enforcement is slow, reduce `max_context_tokens` in config

### Langfuse connection errors

- Traces fall back to local JSON (`traces/local/`) automatically
- Verify Langfuse is running: `curl http://localhost:3100`
- Check `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` in `.env`

### Qdrant out of memory

- Default Qdrant has no memory limit in Docker
- For large collections, add `QDRANT__STORAGE__MMAP_THRESHOLD_KB: 20480` to enable mmap
- Monitor collection size: `curl http://localhost:6333/collections/documents`
