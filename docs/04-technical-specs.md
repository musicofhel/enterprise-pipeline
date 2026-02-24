# Enterprise AI Pipeline — Technical Specifications

**Version:** 1.0
**Date:** February 24, 2026

---

## 1. Infrastructure Requirements

### 1.1 Compute

| Component | Instance Type | Count | Purpose |
|-----------|--------------|-------|---------|
| Pipeline Workers | c6i.2xlarge (8 vCPU, 16 GB) | 3–6 (auto-scaling) | Request processing, retrieval, routing |
| HHEM Inference | g4dn.xlarge (T4 GPU, 16 GB) | 1–2 | Hallucination detection model serving |
| Temporal Server | m6i.large (2 vCPU, 8 GB) | 2 (HA) | Workflow orchestration, shadow mode |
| Langfuse | m6i.xlarge (4 vCPU, 16 GB) | 1 | Tracing and observability (self-hosted) |
| Arize Phoenix | m6i.large | 1 | Embedding drift monitoring |

### 1.2 Storage

| Component | Service | Sizing | Purpose |
|-----------|---------|--------|---------|
| Vector Store | pgvector on RDS (or Qdrant) | db.r6g.xlarge, 500 GB | Embedding storage and similarity search |
| Document Store | S3 Standard | 1 TB initial | Raw documents and chunk metadata |
| Audit Logs | S3 Object Lock (Compliance) | 100 GB/year | Immutable compliance archive |
| Operational Logs | Langfuse Postgres | 200 GB | Queryable LLM traces |
| Golden Dataset | S3 + DVC versioning | 10 GB | Evaluation datasets |

### 1.3 External Services

| Service | Plan | Monthly Cost Estimate | Purpose |
|---------|------|----------------------|---------|
| Lakera Guard | Production | ~$500–2,000 | Injection detection, PII |
| Cohere Rerank | Pay-per-use | ~$200–800 | Result reranking |
| LaunchDarkly | Pro | ~$400 | Feature flags |
| Statsig | Pro | ~$500 | Experiment analysis |
| Portkey | Team | ~$300 | LLM gateway, rate limiting |

### 1.4 Networking

```
┌─────────────────────────────────────────────┐
│                    VPC                       │
│                                             │
│  ┌─────────┐     ┌──────────────────────┐  │
│  │ ALB     │────→│ Pipeline Workers     │  │
│  │ (HTTPS) │     │ (Private Subnet)     │  │
│  └─────────┘     └──────────┬───────────┘  │
│                              │              │
│              ┌───────────────┼───────────┐  │
│              │               │           │  │
│         ┌────▼────┐   ┌─────▼────┐ ┌────▼──┐
│         │pgvector │   │ Langfuse │ │ HHEM  │
│         │(Private)│   │(Private) │ │(GPU)  │
│         └─────────┘   └──────────┘ └───────┘
│                                             │
│  Outbound (NAT Gateway):                   │
│    - Lakera Guard API                       │
│    - Cohere Rerank API                      │
│    - LLM Provider APIs (OpenAI/Anthropic)   │
│    - Portkey Gateway                        │
└─────────────────────────────────────────────┘
```

---

## 2. Data Schemas

### 2.1 Vector Metadata Schema

Every vector in the store MUST include these fields. Absence of any required field is a deployment blocker.

```json
{
  "vector_id": "uuid-v4",
  "embedding": [0.123, -0.456, ...],
  "text_content": "The chunk text...",
  "metadata": {
    "user_id": "string (required)",
    "tenant_id": "string (required)",
    "doc_id": "string (required)",
    "chunk_id": "string (required)",
    "doc_type": "enum: pdf|docx|html|markdown|csv",
    "section_header": "string (nullable)",
    "page_number": "int (nullable)",
    "chunk_index": "int — position within document",
    "created_at": "ISO 8601 timestamp",
    "updated_at": "ISO 8601 timestamp",
    "embedding_model": "string — model used to generate embedding",
    "embedding_model_version": "string",
    "source_url": "string (nullable)",
    "access_level": "enum: public|internal|confidential|restricted"
  }
}
```

### 2.2 Langfuse Trace Schema

```json
{
  "trace_id": "uuid-v4",
  "timestamp": "ISO 8601",
  "user_id": "string",
  "session_id": "string",
  "pipeline_version": "string (git sha or semver)",
  "config_hash": "sha256 of pipeline config",
  "feature_flags": {
    "pipeline_variant": "control|treatment_a|shadow"
  },
  "spans": [
    {
      "name": "input_safety",
      "start_time": "ISO 8601",
      "end_time": "ISO 8601",
      "attributes": {
        "layer_1_result": "pass|block",
        "layer_2_result": "pass|block",
        "layer_2_confidence": 0.97,
        "pii_detected": false,
        "pii_types": []
      }
    },
    {
      "name": "query_routing",
      "attributes": {
        "route_selected": "rag_knowledge_base",
        "confidence": 0.89,
        "all_route_scores": {"rag": 0.89, "sql": 0.12, "direct": 0.05}
      }
    },
    {
      "name": "retrieval",
      "attributes": {
        "num_results_raw": 20,
        "num_results_after_dedup": 14,
        "num_results_after_rerank": 5,
        "top_cosine_sim": 0.87,
        "mean_cosine_sim": 0.72
      }
    },
    {
      "name": "compression",
      "attributes": {
        "tokens_before": 6200,
        "tokens_after": 2400,
        "compression_ratio": 0.61,
        "method": "bm25_subscoring"
      }
    },
    {
      "name": "generation",
      "attributes": {
        "model": "gpt-4o",
        "tokens_in": 2800,
        "tokens_out": 350,
        "cost_usd": 0.032,
        "latency_ms": 1200
      }
    },
    {
      "name": "hallucination_check",
      "attributes": {
        "model": "vectara/hhem-2.1",
        "score": 0.94,
        "passed": true,
        "latency_ms": 85
      }
    }
  ],
  "scores": {
    "faithfulness": 0.94,
    "user_feedback": null
  },
  "total_latency_ms": 2100,
  "total_cost_usd": 0.035
}
```

### 2.3 Audit Log Event Schema

```json
{
  "event_id": "uuid-v4",
  "event_type": "enum: llm_call|safety_block|deletion_request|config_change|feedback|experiment_assignment",
  "timestamp": "ISO 8601",
  "actor": {
    "type": "enum: user|system|admin",
    "id": "string"
  },
  "resource": {
    "type": "enum: trace|vector|document|prompt|model_config",
    "id": "string"
  },
  "action": "string — what happened",
  "details": {},
  "pipeline_version": "string",
  "environment": "enum: production|staging|shadow"
}
```

---

## 3. API Contracts

### 3.1 Pipeline Query API

```
POST /api/v1/query

Request:
{
  "query": "string (required, max 10,000 chars)",
  "user_id": "string (required)",
  "session_id": "string (optional)",
  "tenant_id": "string (required)",
  "options": {
    "max_tokens": "int (default 4000)",
    "temperature": "float (default 0.1)",
    "include_sources": "bool (default true)",
    "force_route": "string (optional — override routing)"
  }
}

Response (200):
{
  "answer": "string",
  "trace_id": "uuid",
  "sources": [
    {
      "doc_id": "string",
      "chunk_id": "string",
      "text_snippet": "string (first 200 chars)",
      "relevance_score": 0.87,
      "source_url": "string (nullable)"
    }
  ],
  "metadata": {
    "route_used": "rag_knowledge_base",
    "faithfulness_score": 0.94,
    "model": "gpt-4o",
    "latency_ms": 2100,
    "tokens_used": 3150
  }
}

Response (422 — Blocked by Safety):
{
  "error": "input_blocked",
  "reason": "prompt_injection_detected",
  "trace_id": "uuid"
}

Response (200 — Low Confidence Fallback):
{
  "answer": null,
  "fallback": true,
  "message": "I found relevant documents but I'm not confident in generating an answer.",
  "sources": [...],
  "trace_id": "uuid"
}
```

### 3.2 Feedback API

```
POST /api/v1/feedback

Request:
{
  "trace_id": "uuid (required)",
  "user_id": "string (required)",
  "rating": "enum: positive|negative (required)",
  "correction": "string (optional — user's expected answer)",
  "comment": "string (optional)"
}

Response (200):
{
  "feedback_id": "uuid",
  "status": "recorded"
}
```

### 3.3 Deletion API

```
DELETE /api/v1/users/{user_id}/data

Request Headers:
  Authorization: Bearer {admin_token}
  X-Deletion-Reason: "string (required for audit)"

Response (202 — Accepted):
{
  "deletion_id": "uuid",
  "status": "processing",
  "estimated_completion": "ISO 8601 (within 72 hours)"
}

GET /api/v1/deletions/{deletion_id}

Response (200):
{
  "deletion_id": "uuid",
  "status": "enum: processing|completed|failed",
  "user_id": "string",
  "summary": {
    "vectors_deleted": 142,
    "documents_deleted": 23,
    "traces_redacted": 87
  },
  "completed_at": "ISO 8601 (nullable)",
  "receipt_url": "S3 presigned URL to deletion receipt"
}
```

---

## 4. Configuration Management

### 4.1 Pipeline Configuration

All pipeline behavior is driven by a single versioned config file. Every config change is a Git commit.

```yaml
# pipeline_config.yaml
version: "1.2.0"

chunking:
  strategy: by_title
  max_characters: 1500
  overlap: 200
  provider: unstructured

retrieval:
  top_k: 20
  dedup_threshold: 0.95
  rerank_provider: cohere
  rerank_top_n: 5

compression:
  method: bm25_subscoring
  sentences_per_chunk: 5
  max_total_tokens: 4000

routing:
  provider: semantic_router
  default_route: rag_knowledge_base
  confidence_threshold: 0.7
  routes_file: routes.yaml

query_expansion:
  enabled: true
  method: multi_query
  num_queries: 3

safety:
  injection_detection:
    layer_1: guardrails_ai
    layer_2: lakera_guard
    layer_3_enabled: false
  pii_detection: true
  pii_action: redact

generation:
  model: gpt-4o
  temperature: 0.1
  max_output_tokens: 1000
  fallback_model: claude-sonnet-4-5-20250929

hallucination:
  model: vectara/hhem-2.1
  threshold_pass: 0.85
  threshold_warn: 0.70
  fallback_on_fail: true

observability:
  langfuse_enabled: true
  langfuse_sample_rate: 1.0
  export_to_s3: true
  export_schedule: daily

experimentation:
  shadow_mode_enabled: false
  shadow_pipeline_version: null
  feature_flag_provider: launchdarkly
```

### 4.2 Environment Overrides

```yaml
# environments/production.yaml (overrides base config)
generation:
  temperature: 0.05

observability:
  langfuse_sample_rate: 1.0

# environments/staging.yaml
generation:
  temperature: 0.1

experimentation:
  shadow_mode_enabled: true
  shadow_pipeline_version: "candidate-v1.3.0"
```

---

## 5. Evaluation Framework

### 5.1 Metrics

| Metric | Tool | Target | Frequency |
|--------|------|--------|-----------|
| Faithfulness | HHEM + DeepEval | ≥0.92 | Every response (HHEM), CI (DeepEval) |
| Context Precision | Ragas | ≥0.85 | Daily sample |
| Context Recall | Ragas | ≥0.80 | Daily sample |
| Answer Relevancy | Ragas | ≥0.90 | Daily sample |
| Injection Block Rate | Custom benchmark | ≥99% | Weekly |
| Retrieval MRR@10 | Custom | ≥0.65 | CI on every change |
| Latency p95 | Langfuse | <3000ms | Continuous |
| Cost per query | Langfuse | <$0.05 | Continuous |

### 5.2 Golden Dataset Structure

```
golden_dataset/
├── README.md              # Dataset documentation
├── metadata.json          # Version, creation date, stats
├── queries/
│   ├── rag_general.jsonl       # 200+ RAG queries with expected answers
│   ├── rag_edge_cases.jsonl    # 100+ tricky/adversarial RAG queries
│   ├── injection_attacks.jsonl # 100+ injection attempts (should block)
│   ├── routing_test.jsonl      # 100+ queries with expected route labels
│   └── regression.jsonl        # Queries from production failures (grows)
└── annotations/
    └── argilla_exports/        # Weekly exports from Argilla
```

### 5.3 CI Eval Pipeline

```yaml
# .github/workflows/eval.yaml
name: Pipeline Eval

on:
  pull_request:
    paths:
      - 'prompts/**'
      - 'pipeline_config.yaml'
      - 'src/pipeline/**'

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Promptfoo Eval
        run: |
          npx promptfoo eval \
            --config promptfoo.config.yaml \
            --output results.json

      - name: Run DeepEval Regression
        run: |
          pytest tests/eval/ \
            --deepeval \
            -k "test_faithfulness or test_relevancy"

      - name: Check Regression
        run: |
          python scripts/check_regression.py results.json \
            --max-regression-pct 2 \
            --fail-on-regression

      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: results.json
```

---

## 6. Security Specifications

### 6.1 Secret Management

| Secret | Storage | Rotation |
|--------|---------|----------|
| LLM API keys | AWS Secrets Manager | 90-day auto-rotation |
| Lakera Guard API key | AWS Secrets Manager | 90-day auto-rotation |
| Cohere API key | AWS Secrets Manager | 90-day auto-rotation |
| Database credentials | AWS Secrets Manager | 30-day auto-rotation |
| Langfuse API keys | AWS Secrets Manager | 90-day auto-rotation |
| LaunchDarkly SDK key | AWS Secrets Manager | On demand |

### 6.2 Access Control

```
Roles:
  pipeline_worker:
    - Read: vector store, document store
    - Write: Langfuse traces, audit logs
    - Call: LLM APIs, Lakera, Cohere
    - No access: deletion API, config changes

  ml_engineer:
    - All of pipeline_worker
    - Read/Write: golden dataset, eval configs
    - Execute: Promptfoo evals, Arize Phoenix
    - No access: deletion API, production config direct edit

  platform_engineer:
    - All of ml_engineer
    - Write: pipeline config (via Git PR)
    - Manage: LaunchDarkly flags, Temporal workflows
    - No access: audit log deletion (impossible by design)

  security_admin:
    - Read: audit logs, safety metrics
    - Execute: deletion API
    - Manage: Lakera Guard config, Guardrails validators
    - No access: LLM API keys directly

  compliance_officer:
    - Read: audit logs, deletion receipts
    - No write access to any system
```

---

## 7. Dependency Matrix

Which waves depend on which:

```
Wave 1 (Retrieval)     ─── standalone
Wave 2 (Input Safety)  ─── depends on Wave 1 (needs retrieval to route to)
Wave 3 (Output Quality)─── depends on Wave 1 + Wave 2
Wave 4 (Compliance)    ─── depends on Wave 3 (needs Langfuse)
Wave 5 (Deployment)    ─── depends on Wave 3 + Wave 4
Wave 6 (Observability) ─── depends on Wave 3 + Wave 5
Wave 7 (Flywheel)      ─── depends on Wave 3 + Wave 6
Wave 8 (Optimization)  ─── depends on Wave 7
```

Critical path: **Wave 1 → Wave 3 → Wave 5 → Wave 7**

---

## 8. Runbook: Common Operations

### 8.1 Deploy a Prompt Change

```
1. Create PR with prompt change in prompts/ directory
2. CI runs Promptfoo eval automatically
3. Review eval results — must not regress >2%
4. Merge PR
5. CD deploys to staging
6. Enable shadow mode: update pipeline_config.yaml
7. Run shadow for 24-48 hours
8. Compare shadow vs. primary in Langfuse
9. If improved: promote to primary via feature flag
10. Monitor Grafana dashboard for 24 hours post-deploy
```

### 8.2 Handle a GDPR Deletion Request

```
1. Receive deletion request
2. Call DELETE /api/v1/users/{user_id}/data
3. Monitor GET /api/v1/deletions/{deletion_id} until completed
4. Download deletion receipt from S3
5. Verify: query vector store for user_id — must return 0 results
6. File receipt with compliance team
```

### 8.3 Investigate a Quality Alert

```
1. Check Grafana alert — identify which metric degraded
2. Open Arize Phoenix — check for embedding drift
3. Open Langfuse — filter traces by time window of degradation
4. Identify pattern:
   a. Retrieval quality dropped → check vector store, embedding model
   b. Faithfulness dropped → check prompt, model version
   c. Latency spiked → check LLM provider status, request volume
5. If root cause is data: check recent ingestion jobs
6. If root cause is model: check for provider-side changes
7. Document findings and remediation in incident log
```
