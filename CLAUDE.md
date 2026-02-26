# Enterprise AI Pipeline — Project Context

## Overview

Production-grade RAG pipeline built in 3 phases across 8 waves. Python + FastAPI, Qdrant vector store, Docker Compose + GitHub Actions CI.

- **PRD:** `docs/02-prd.md`
- **Implementation plan:** `docs/03-implementation-plan.md`
- **Tech spec:** `docs/04-technical-specs.md`

## Current Status

- **Wave 1 (Retrieval Quality Foundation):** Complete. Tag: `wave-1-complete`.
- **Wave 2 (Input Safety & Query Intelligence):** Complete. Tag: `wave-2-complete`. Verification follow-up complete.
- **Wave 3 (Output Quality & Tracing):** Complete. Tag: `wave-3-complete`. 175 tests passing, 1 skipped (empty context edge case). Lint and typecheck clean (0 new errors).
- **Wave 4 (Compliance & Data Governance):** Complete. Tag: `wave-4-complete`. 239 tests passing, 21 skipped (DeepEval API key tests). Lint clean, 0 new mypy errors. HHEM restored (transformers 5.2.0 → 4.57.6). Lockfile + version guard added.

### Wave 4 Deliverables

| # | Deliverable | Status | Tests |
|---|-------------|--------|-------|
| 4.1 | Metadata schema enforcement | `validate_vector_metadata()` at upsert — rejects missing user_id/doc_id/tenant_id | 6 tests |
| 4.2 | Right-to-deletion API | Full DELETE + GET endpoints with per-step tracking (vectors/traces/feedback) | 14 tests |
| 4.3 | Immutable audit log | AuditLogService with local JSON WORM — no delete/update methods | 8+4 tests |
| 4.4 | Trace export | Local traces exportable with schema validation | 2 tests |
| 4.5 | Data retention | RetentionChecker with configurable TTLs + purge | 6 tests |
| 4.6 | RBAC + Auth | 5 roles, 13 permissions, API key auth, `require_permission()` dependency | 7+8 tests |
| 4.7 | Feedback API | FeedbackService with audit trail, feedback deletion for right-to-erasure | 5 tests |

### Wave 3 Deliverables

| # | Deliverable | Status | Tests |
|---|-------------|--------|-------|
| 3.1 | HHEM Hallucination Detection | Real CPU inference, `vectara/hallucination_evaluation_model` | 7 tests, real model |
| 3.2 | DeepEval Faithfulness CI | 20 golden dataset cases, CI wired | 20 pass, 1 skip (empty context) via OpenRouter |
| 3.3 | Langfuse Tracing | Local JSON fallback matching tech spec Section 2.2 | 6 tests |
| 3.4 | Output Schema Enforcement | Per-route JSON schema validation with jsonschema | 10 tests |
| 3.5 | Structured Logging | structlog JSON, auto trace_id binding, 8 pipeline events | 4 tests |

## Project Structure

```
src/
├── main.py                         # FastAPI app factory
├── config/                         # Pydantic settings + YAML config loader
├── models/
│   ├── schemas.py                  # API request/response models
│   ├── audit.py                    # AuditEvent, AuditActor, AuditResource models
│   ├── rbac.py                     # Role, Permission, ROLE_PERMISSIONS, PermissionChecker
│   └── metadata.py                 # ChunkMetadata, DocType
├── api/
│   ├── auth.py                     # API key → Role auth + require_permission() dependency
│   ├── deps.py                     # DI wiring for all services
│   └── v1/                         # FastAPI routes (query, ingest, deletion, feedback)
├── pipeline/
│   ├── orchestrator.py             # Central pipeline coordinator (12 stages)
│   ├── safety/                     # L1 regex injection + PII detection
│   ├── routing/                    # Semantic query router (cosine sim + YAML routes)
│   ├── retrieval/                  # Qdrant client, embeddings, query expander, metadata_validator
│   ├── reranking/                  # Cohere reranker
│   ├── compression/                # BM25 sub-scoring + token budget
│   ├── generation/                 # LLM client (OpenRouter — OpenAI-compatible API)
│   ├── quality/                    # HHEM hallucination check (REAL — vectara model on CPU)
│   └── output_schema.py            # Per-route JSON schema enforcement
├── observability/
│   ├── tracing.py                  # Langfuse SDK + local JSON fallback
│   ├── audit_log.py                # Immutable audit log (WORM — no delete/update)
│   └── logging.py                  # structlog JSON/console config with trace context
├── services/
│   ├── deletion_service.py         # Right-to-deletion orchestrator (vectors + traces + feedback)
│   ├── feedback_service.py         # Feedback storage with audit trail
│   └── retention_checker.py        # TTL-based data retention enforcement
└── utils/tokens.py                 # tiktoken helpers
tests/
├── unit/                           # 30 test files (~210 tests)
├── eval/                           # DeepEval faithfulness + exit criteria
└── integration/                    # E2E pipeline + Cohere/Lakera stubs
```

## Open Issues

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| 001 | Validate EC-4 Cohere Rerank in staging | P0 | Open — needs COHERE_API_KEY |
| 002 | Backfill null baselines (Wave 1 layers) | P1 | Open — needs live services |
| 003 | Compression sentence logging | P1 | Fixed |
| 004 | Routing accuracy with real local embeddings | P1 | Partial — 4/5 (80%) at threshold=0.15. Needs routes.yaml tuning for >95%. |
| 005 | Multi-query recall with live Qdrant retrieval | P1 | Open — needs Qdrant + OPENROUTER_API_KEY |
| 006 | Backfill null latency baselines (Wave 2 layers) | P2 | Open — needs API keys |
| 007 | Missing PII pattern types (addresses, IBANs, API tokens, MRNs) | P2 | Open |
| 008 | Passport number triggers SSN false positive | P3 | Open |
| 009 | FR-202 routing deferral was undocumented (now fixed) | P3 | Open — process gap |
| 010 | Lakera L2 social engineering validation | P1 | Open — needs LAKERA_API_KEY |
| 011 | Natural language PII beyond regex scope | P3 | Open — documentation |
| 012 | Generate HHEM 500-query eval set for EC-1 | P1 | Open — needs OPENROUTER_API_KEY |
| 013 | Wire OutputSchemaEnforcer into orchestrator | P2 | Open — Wave 3 follow-up |

## Known Technical Debt

### HHEM Hallucination Detection
- Model: `vectara/hallucination_evaluation_model` with `trust_remote_code=True`.
- **HARD CONSTRAINT:** `transformers>=4.40,<5` — v5.x breaks HHEM's custom model code (`all_tied_weights_keys` rename).
- Aggregation: `max` (best-chunk) is default for RAG. `mean` and `min` configurable.
- Pair ordering: `(context_chunk, answer)` — reversing drops scores from ~0.92 to ~0.13.
- Cold start: ~900ms (model load from cache). Warm inference: ~150ms per 3 chunks on CPU.
- EC-1 (>=0.92 on 500 queries) needs eval set generation (ISSUE-012).

### Output Schema Enforcement
- `OutputSchemaEnforcer` built and tested but NOT wired into orchestrator pipeline (ISSUE-013).
- Per-route schemas: `rag_knowledge_base` (requires `answer`), `direct_llm` (requires `answer`).
- Validates structure only, NOT content. Content safety is a separate concern.

### Tracing
- Local JSON fallback writes to `traces/local/{trace_id}.json`.
- Schema matches tech spec Section 2.2: trace_id, timestamp, user_id, session_id, pipeline_version, config_hash, feature_flags, spans, scores.
- `pipeline_version` from `git rev-parse --short HEAD`, `config_hash` from SHA256 of `pipeline_config.yaml`.

### Injection Defense
- L1 regex blocks 15/20 adversarial payloads.
- 5 remaining bypasses are social engineering attacks requiring Lakera L2 (ISSUE-010).

### Routing
- Routing branching implemented. `rag_knowledge_base` → full RAG, `direct_llm` → skip retrieval, `escalate_human` → handoff.
- `sql_structured_data` and `api_lookup` raise `NotImplementedError` (Wave 4+).
- **Local embeddings:** `all-MiniLM-L6-v2` via sentence-transformers (384-dim, CPU, no API key). Confidence threshold lowered to 0.15 for local model.

### Pipeline Stage Reality
- **7/12 stages run real logic:** L1 regex, PII detection, routing algorithm, dedup, BM25 compression, token budget, HHEM hallucination check.
- **4/12 stages are mocked:** Qdrant (needs server), Cohere rerank (needs API key), LLM generation (needs API key), embeddings (needs API key).
- **1/12 skipped:** Lakera L2 (needs API key).

### Compliance (Wave 4)
- **RBAC**: `src/api/auth.py` — API key → Role mapping from `API_KEY_ROLES` env var. `require_permission()` enforces DELETE_USER_DATA, WRITE_FEEDBACK, etc.
- **Deletion**: `src/services/deletion_service.py` — orchestrates vector deletion (Qdrant), trace redaction (local JSON), feedback deletion. Per-step tracking with `DeletionStepResult`. Trace redaction runs in `asyncio.to_thread()` to avoid blocking.
- **Audit**: `src/observability/audit_log.py` — WORM (no delete/update). Path configurable via `compliance.audit_log_path`. Every deletion request creates an audit event with tenant_id.
- **Metadata**: `src/pipeline/retrieval/metadata_validator.py` — blocks upsert if user_id, doc_id, or tenant_id missing/empty.
- **Retention**: `src/services/retention_checker.py` — finds and purges expired traces/feedback based on TTL config.
- **Qdrant**: Running in Docker on port 6333. `VectorStore.delete_by_user()` counts vectors before deletion, returns actual count.

## Decisions Made

- **Qdrant over pgvector** (Wave 1): Async client, filter DSL, good ergonomics.
- **Lightweight semantic router over `semantic-router` package** (Wave 2): numpy cosine sim + YAML routes, ~240 lines.
- **Constructor DI, not globals**: Every component takes deps as constructor args, wired in `deps.py`.
- **`max` aggregation for HHEM** (Wave 3): Best-chunk approach for RAG where retrieval returns mixed-relevance chunks.
- **Local JSON trace fallback** (Wave 3): Same schema as Langfuse, no server required for CI.
- **Post-hoc schema enforcement over constrained decoding** (Wave 3): jsonschema validation is simpler, more testable, and independent of the LLM provider.
- **OpenRouter over direct OpenAI** (post-Wave 3): Single LLM gateway for all models. `AsyncOpenAI` SDK with `base_url="https://openrouter.ai/api/v1"`. Default model: `anthropic/claude-sonnet-4-5`, fallback: `anthropic/claude-haiku-4-5`. Query expansion uses cheaper `anthropic/claude-haiku-4-5`.
- **Local sentence-transformers for routing** (post-Wave 3): `all-MiniLM-L6-v2` (384-dim, ~80MB, CPU). No API key needed. Confidence threshold adjusted from 0.7 to 0.15 for local model's lower average similarities.
- **API key → Role RBAC** (Wave 4): Static env-var registry (`API_KEY_ROLES`), 5 roles, 13 permissions. `require_permission()` FastAPI dependency. Only `security_admin` and `compliance_officer` can delete user data.
- **Per-step deletion tracking** (Wave 4): Each deletion step (vectors, traces, feedback) tracked independently with status/count/error. Overall status: `completed` (all pass), `partial` (some fail), `failed` (all fail).
- **Configurable audit log path** (Wave 4): `compliance.audit_log_path` in `pipeline_config.yaml`, defaults to `audit_logs/local`.

## Key Configuration

- `pipeline_config.yaml` — master config (safety, routing, query expansion, hallucination, compliance, etc.)
- `.env.example` — required API keys: OPENROUTER_API_KEY, COHERE_API_KEY, LAKERA_API_KEY
- `API_KEY_ROLES` env var — semicolon-separated `key=role` pairs for RBAC (e.g. `sk-admin=security_admin;sk-worker=pipeline_worker`)
- `src/pipeline/routing/routes.yaml` — 5 routes with 12-13 utterances each

## Running Tests

```bash
# All unit + eval tests (239 pass, 21 skip — DeepEval needs API key)
# conftest.py auto-bridges OPENROUTER_API_KEY → OPENAI_API_KEY + OPENAI_BASE_URL for DeepEval
.venv/bin/python -m pytest tests/ --ignore=tests/integration -q

# Integration tests (requires Docker services + API keys)
python3 -m pytest tests/integration -m integration

# Lint
python3 -m ruff check src/ tests/

# Typecheck
python3 -m mypy src/ --ignore-missing-imports

# E2E trace (mocked external deps, real local components)
python3 -m scripts.run_e2e_trace
```
