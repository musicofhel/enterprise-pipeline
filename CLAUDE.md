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
- **Wave 5 (Deployment & Experimentation):** Complete. Tag: `wave-5-complete`. 283 tests passing, 21 skipped. Lint clean, 0 new mypy errors. All local implementations (no Temporal, no LaunchDarkly).
- **Wave 6 (Observability & Monitoring):** Complete. Tag: `wave-6-complete`. 318 tests passing, 21 skipped. Lint clean, 0 new mypy errors. All local and free (Prometheus + Grafana + Arize Phoenix).
- **Wave 7 (Data Flywheel & Continuous Improvement):** Complete. Tag: `wave-7-complete`. 352 tests passing, 21 skipped. Lint clean, 0 new mypy errors. Full feedback → triage → annotation → dataset expansion → eval expansion cycle.

### Wave 7 Deliverables

| # | Deliverable | Status | Tests |
|---|-------------|--------|-------|
| 7.1 | User feedback collection | `FeedbackService` extended — stats endpoint, Prometheus metrics (feedback_received_total, feedback_rate), Grafana panels | 7 tests |
| 7.2 | Failure triage workflow | `FailureTriageService` — scan traces, classify 6 failure types, cluster by embedding similarity, triage report | 5 tests |
| 7.3 | Annotation pipeline | `AnnotationService` — generate tasks from triage, submit annotations, export to golden dataset JSONL, audit trail | 7 tests |
| 7.4 | Golden dataset expansion | `GoldenDatasetManager` — import annotations, embedding dedup (0.95 cosine), validation, versioning (metadata.json) | 6 tests |
| 7.5 | Regression eval suite expansion | `EvalSuiteExpander` — auto-generate eval tests from annotations, coverage report, gap detection | 5 tests |
| 7.6 | Weekly flywheel automation | `run_weekly_flywheel.py` — full cycle: triage → annotate → import → expand → report (two-phase with human-in-the-loop) | 4 tests |

### Wave 6 Deliverables

| # | Deliverable | Status | Tests |
|---|-------------|--------|-------|
| 6.1 | Embedding drift monitoring | `EmbeddingMonitor` — cosine centroid shift + spread change, Prometheus gauges, Phoenix launcher | 8 tests |
| 6.2 | Retrieval quality canary | `RetrievalQualityCanary` — rolling window, p50/p95/mean, WARN/CRITICAL alerts, empty result rate | 7 tests |
| 6.3 | Daily Ragas eval | `DailyEvalRunner` — OpenRouter (claude-haiku-4-5), faithfulness/precision/relevancy, graceful skip | 7 tests |
| 6.4 | Unified quality dashboard | `metrics.py` — 28 Prometheus metrics, `/metrics` endpoint, Grafana dashboard (5 rows, 17 panels) | 9 tests |
| 6.5 | Alert playbooks | `docs/runbooks/alerting-playbooks.md` — 11 alerts (7 CRITICAL, 4 WARN), Trigger/Investigation/Remediation | 4 tests |

### Wave 5 Deliverables

| # | Deliverable | Status | Tests |
|---|-------------|--------|-------|
| 5.1 | Promptfoo eval config | `promptfoo.config.yaml` — OpenRouter provider, 2 prompts, 20 golden dataset cases, custom assertion | 4 tests |
| 5.2 | Shadow mode pipeline | `ShadowRunner` — `asyncio.create_task()` fire-and-forget, budget tracking, circuit breaker, <0.01ms overhead | 14 tests |
| 5.3 | Feature flags | `FeatureFlagService` — MD5 hash deterministic routing, tenant/user overrides, audit logging | 10 tests |
| 5.4 | Experiment analyzer | `ExperimentAnalyzer` — Welch's t-test, Mann-Whitney U, Cohen's d, auto-recommendation | 7 tests |
| 5.5 | CI eval gate | `check_regression.py --promptfoo-results` — blocks on >2% regression, promptfoo-eval CI job | 2 tests + 8 exit criteria |

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
│   ├── logging.py                  # structlog JSON/console config with trace context
│   ├── metrics.py                  # Central Prometheus metrics registry (34 metrics)
│   ├── embedding_monitor.py        # Embedding drift detection (cosine centroid shift)
│   ├── retrieval_canary.py         # Retrieval quality canary (rolling window alerts)
│   ├── daily_eval.py               # Daily Ragas eval runner (OpenRouter)
│   └── instrumentation.py          # Pipeline instrumentation (Prometheus metric updates)
├── experimentation/
│   ├── __init__.py                 # Package exports
│   ├── feature_flags.py            # FeatureFlagService (local YAML, hash-based)
│   ├── shadow_mode.py              # ShadowRunner + ShadowComparison
│   └── analysis.py                 # ExperimentAnalyzer (scipy stats)
├── flywheel/
│   ├── __init__.py                 # Package exports
│   ├── failure_triage.py           # FailureTriageService (scan, classify, cluster, triage)
│   ├── annotation.py               # AnnotationService (generate, submit, export)
│   ├── dataset_manager.py          # GoldenDatasetManager (import, dedup, versioning)
│   └── eval_expansion.py           # EvalSuiteExpander (coverage report, auto-expansion)
├── services/
│   ├── deletion_service.py         # Right-to-deletion orchestrator (vectors + traces + feedback)
│   ├── feedback_service.py         # Feedback collection + stats + Prometheus metrics
│   └── retention_checker.py        # TTL-based data retention enforcement
└── utils/tokens.py                 # tiktoken helpers
tests/
├── unit/                           # 47 test files (~303 tests)
├── eval/                           # DeepEval faithfulness + exit criteria (~49 tests)
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

### Experimentation (Wave 5)
- **Feature flags**: Local YAML config loaded at startup. No hot-reload — service restart required for config changes.
- **Shadow mode**: Budget tracked in-memory per process. Multi-worker deployments need Redis counter.
- **Experiment analysis**: Reads individual JSON trace files via glob. JSONL per-day would be faster at scale.
- **Promptfoo**: Config ready but CI job needs `OPENROUTER_API_KEY` in GitHub secrets to actually run.
- **Config models**: `ShadowModeConfig` and `FeatureFlagConfig` nested under `ExperimentationConfig` in `pipeline_config.py`.

### Observability (Wave 6)
- **Prometheus metrics**: Dedicated `CollectorRegistry` in `src/observability/metrics.py`. 34 metrics across 8 groups (pipeline, safety, hallucination, LLM, retrieval, experimentation, feedback, annotations). `/metrics` endpoint on health router.
- **Embedding drift**: Cosine centroid shift + spread change detection. Reference embeddings set once, current embeddings buffered in deque. Min 10 samples for drift check.
- **Retrieval canary**: Rolling window (default 1000) + baseline window (default 7000). p50 drop >10% = CRITICAL. Empty result rate >5% = CRITICAL. Wired into orchestrator after retrieval stage.
- **Daily Ragas eval**: Uses OpenRouter (claude-haiku-4-5) for LLM judge. Faithfulness, ContextPrecision, AnswerRelevancy. Graceful skip without API key. Reports saved to `eval_reports/`.
- **Grafana dashboard**: Auto-provisioned via `docker-compose.monitoring.yaml`. 5 rows, 17 panels. Port 3001 (Grafana), 9090 (Prometheus).
- **Alert playbooks**: 11 alerts documented in `docs/runbooks/alerting-playbooks.md`. Each has Trigger/Investigation/Remediation/Escalation.
- **openai SDK**: Pin updated from `<2` to `<3` for Ragas compatibility. All existing tests pass with openai 2.x.

### Flywheel (Wave 7)
- **Feedback service**: Rolling window rate tracking (response vs feedback timestamps) in-memory deques — doesn't survive process restarts. Redis/file counter would be more robust.
- **Failure triage**: Clustering uses greedy cosine similarity (threshold 0.7). DBSCAN/HDBSCAN would handle variable-density clusters better.
- **Annotation pipeline**: File-based JSON (pending/completed dirs). Functional but minimal — team workflows would benefit from web UI or Argilla integration.
- **Dataset dedup**: Embedding similarity (0.95 cosine) requires caller-supplied `embed_fn`. No built-in embedding model.
- **Eval expansion**: Auto-generates Promptfoo and DeepEval test entries from annotations. Coverage report tracks per-category gaps.
- **Weekly flywheel**: Two-phase (triage+annotate → import+expand+report). Phase 2 requires `--continue` flag after human annotation.
- **Prometheus metrics**: 6 new metrics (feedback_received_total, feedback_correction_received_total, feedback_rate, annotations_pending/completed/exported).
- **Grafana**: 2 new panels (User Feedback Rate gauge, Feedback by Rating timeseries). Dashboard now 5 rows, 19 panels.

### Injection Defense
- L1 regex blocks 15/20 adversarial payloads.
- 5 remaining bypasses are social engineering attacks requiring Lakera L2 (ISSUE-010).

### Routing
- Routing branching implemented. `rag_knowledge_base` → full RAG, `direct_llm` → skip retrieval, `escalate_human` → handoff.
- `sql_structured_data` and `api_lookup` raise `NotImplementedError` (Wave 4+).
- **Local embeddings:** `all-MiniLM-L6-v2` via sentence-transformers (384-dim, CPU, no API key). Confidence threshold lowered to 0.15 for local model.

### Pipeline Stage Reality
- **7/12 core stages run real logic:** L1 regex, PII detection, routing algorithm, dedup, BM25 compression, token budget, HHEM hallucination check.
- **4/12 core stages are mocked:** Qdrant (needs server), Cohere rerank (needs API key), LLM generation (needs API key), embeddings (needs API key).
- **1/12 skipped:** Lakera L2 (needs API key).
- **Observability layer (4 REAL):** Prometheus metrics, retrieval canary, embedding drift, pipeline instrumentation.
- **Additional observability (needs runtime deps):** Ragas eval (needs OPENROUTER_API_KEY), Grafana dashboard (needs Docker).
- **Flywheel layer (5 REAL):** Failure triage, annotation pipeline, golden dataset manager, eval expansion, weekly automation script.

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
- **`asyncio.create_task()` for shadow mode** (Wave 5): Fire-and-forget pattern, <0.01ms overhead on primary path. Reuses retrieval results — only re-runs generation step. No Temporal needed.
- **MD5 hash-based feature flags** (Wave 5): `hashlib.md5(user_id)[:8]` → int mod 10000 → [0,1) bucket. Deterministic assignment, tenant/user overrides, audit trail. No LaunchDarkly needed.
- **scipy for experiment analysis** (Wave 5): Welch's t-test + Mann-Whitney U + Cohen's d. Min 30 traces per variant. Auto-generates recommendation (promote/regress/continue).
- **Promptfoo via OpenRouter** (Wave 5): `openai:anthropic/claude-sonnet-4-5` with `apiBaseUrl`. Custom Python assertion for eval quality checks.
- **API key → Role RBAC** (Wave 4): Static env-var registry (`API_KEY_ROLES`), 5 roles, 13 permissions. `require_permission()` FastAPI dependency. Only `security_admin` and `compliance_officer` can delete user data.
- **Per-step deletion tracking** (Wave 4): Each deletion step (vectors, traces, feedback) tracked independently with status/count/error. Overall status: `completed` (all pass), `partial` (some fail), `failed` (all fail).
- **Configurable audit log path** (Wave 4): `compliance.audit_log_path` in `pipeline_config.yaml`, defaults to `audit_logs/local`.
- **Dedicated Prometheus CollectorRegistry** (Wave 6): Avoids collision with prometheus_client internal metrics. `get_metrics_text()` returns bytes from our registry only.
- **Cosine centroid shift for drift** (Wave 6): Measures directional change in embedding space (not magnitude). More semantically meaningful than Euclidean distance.
- **Rolling window + baseline window for canary** (Wave 6): Recent window for current state, larger baseline window for comparison. Adapts as system operating point shifts.
- **PipelineInstrumentation middleware** (Wave 6): Static methods for all Prometheus updates. Keeps orchestrator clean — one-line calls instead of inline counter/histogram updates.
- **Grafana port 3001** (Wave 6): Avoids conflict with any backend on port 3000. Prometheus on 9090 (default).
- **openai <3 pin** (Wave 6): Ragas requires openai>=2. Verified all existing tests pass with openai 2.x. Updated from `<2` to `<3`.
- **Local file-based annotation over Argilla** (Wave 7): JSON files in `annotations/pending/` and `annotations/completed/`. Simpler, testable, no external dependency. Interface designed for Argilla plug-in later.
- **Greedy cosine clustering for triage** (Wave 7): Threshold 0.7 for grouping similar failure queries. Simpler than DBSCAN but sufficient for triage reports.
- **Embedding dedup at 0.95 cosine threshold** (Wave 7): Prevents near-duplicate pollution in golden dataset. Caller supplies `embed_fn` — no built-in model dependency.
- **Semver versioning for golden dataset** (Wave 7): `metadata.json` with version, created_at, last_updated, history entries. Minor bump on each import (1.0.0 → 1.1.0).
- **Two-phase flywheel with human-in-the-loop** (Wave 7): Phase 1 (triage + generate tasks) runs automatically. Human annotation between phases. Phase 2 (import + expand + report) requires `--continue` flag.

## Key Configuration

- `pipeline_config.yaml` — master config (safety, routing, query expansion, hallucination, compliance, etc.)
- `.env.example` — required API keys: OPENROUTER_API_KEY, COHERE_API_KEY, LAKERA_API_KEY
- `API_KEY_ROLES` env var — semicolon-separated `key=role` pairs for RBAC (e.g. `sk-admin=security_admin;sk-worker=pipeline_worker`)
- `src/pipeline/routing/routes.yaml` — 5 routes with 12-13 utterances each
- `experiment_configs/flags.yaml` — Feature flag variant weights + user/tenant overrides
- `promptfoo.config.yaml` — Promptfoo eval configuration (OpenRouter provider)
- `docker-compose.monitoring.yaml` — Prometheus (9090) + Grafana (3001) monitoring stack
- `monitoring/prometheus.yml` — Prometheus scrape config
- `monitoring/grafana/dashboards/pipeline-health.json` — Grafana dashboard (5 rows, 19 panels)
- `annotations/` — Annotation task storage (pending/ and completed/ subdirs)
- `reports/` — Weekly flywheel triage reports

## Running Tests

```bash
# All unit + eval tests (352 pass, 21 skip — DeepEval needs API key)
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

# Monitoring stack (Prometheus + Grafana)
docker compose -f docker-compose.monitoring.yaml up -d
# Grafana: http://localhost:3001 (admin/admin)
# Prometheus: http://localhost:9090

# Daily Ragas eval (needs OPENROUTER_API_KEY)
python3 scripts/run_daily_eval.py --traces-dir traces/local --output-dir eval_reports

# Arize Phoenix embedding viewer
python3 scripts/launch_phoenix.py

# Failure triage (scan recent traces, classify failures, cluster)
python3 scripts/run_failure_triage.py --days 7 --traces-dir traces/local --output reports/

# Annotation workflow
python3 scripts/annotate.py next                    # Get next pending task
python3 scripts/annotate.py submit <trace_id> ...   # Submit annotation
python3 scripts/annotate.py export --output-dir golden_dataset/

# Golden dataset management
python3 scripts/expand_golden_dataset.py import --source annotations/completed --label manual
python3 scripts/expand_golden_dataset.py stats
python3 scripts/expand_golden_dataset.py coverage

# Weekly flywheel (two-phase)
python3 scripts/run_weekly_flywheel.py --week 2026-W09        # Phase 1: triage + annotate
python3 scripts/run_weekly_flywheel.py --week 2026-W09 --continue  # Phase 2: import + expand
```
