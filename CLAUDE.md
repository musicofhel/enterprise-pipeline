# Enterprise AI Pipeline — Project Context

## Overview

Production-grade RAG pipeline built in 3 phases across 8 waves. Python + FastAPI, Qdrant vector store, Docker Compose + GitHub Actions CI.

- **PRD:** `docs/02-prd.md`
- **Implementation plan:** `docs/03-implementation-plan.md`
- **Tech spec:** `docs/04-technical-specs.md`

## Current Status

- **Wave 1 (Retrieval Quality Foundation):** Complete. Tag: `wave-1-complete`.
- **Wave 2 (Input Safety & Query Intelligence):** Complete. Tag: `wave-2-complete`. Verification follow-up complete.
- **Wave 3 (Output Quality & Tracing):** Complete. Tag: `wave-3-complete`. 155 tests passing (21 skipped — need OPENROUTER_API_KEY). Lint and typecheck clean (0 new errors).

### Wave 3 Deliverables

| # | Deliverable | Status | Tests |
|---|-------------|--------|-------|
| 3.1 | HHEM Hallucination Detection | Real CPU inference, `vectara/hallucination_evaluation_model` | 7 tests, real model |
| 3.2 | DeepEval Faithfulness CI | 20 golden dataset cases, CI wired | 21 tests (skipped without OPENROUTER_API_KEY) |
| 3.3 | Langfuse Tracing | Local JSON fallback matching tech spec Section 2.2 | 6 tests |
| 3.4 | Output Schema Enforcement | Per-route JSON schema validation with jsonschema | 10 tests |
| 3.5 | Structured Logging | structlog JSON, auto trace_id binding, 8 pipeline events | 4 tests |

## Project Structure

```
src/
├── main.py                         # FastAPI app factory
├── config/                         # Pydantic settings + YAML config loader
├── models/schemas.py               # API request/response models
├── api/                            # FastAPI routes + DI wiring (deps.py)
├── pipeline/
│   ├── orchestrator.py             # Central pipeline coordinator (12 stages)
│   ├── safety/                     # L1 regex injection + PII detection
│   ├── routing/                    # Semantic query router (cosine sim + YAML routes)
│   ├── retrieval/                  # Qdrant client, embeddings, query expander, local embeddings, RRF
│   ├── reranking/                  # Cohere reranker
│   ├── compression/                # BM25 sub-scoring + token budget
│   ├── generation/                 # LLM client (OpenRouter — OpenAI-compatible API)
│   ├── quality/                    # HHEM hallucination check (REAL — vectara model on CPU)
│   └── output_schema.py            # Per-route JSON schema enforcement
├── observability/
│   ├── tracing.py                  # Langfuse SDK + local JSON fallback
│   └── logging.py                  # structlog JSON/console config with trace context
└── utils/tokens.py                 # tiktoken helpers
tests/
├── unit/                           # 22 test files (155 tests)
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

## Decisions Made

- **Qdrant over pgvector** (Wave 1): Async client, filter DSL, good ergonomics.
- **Lightweight semantic router over `semantic-router` package** (Wave 2): numpy cosine sim + YAML routes, ~240 lines.
- **Constructor DI, not globals**: Every component takes deps as constructor args, wired in `deps.py`.
- **`max` aggregation for HHEM** (Wave 3): Best-chunk approach for RAG where retrieval returns mixed-relevance chunks.
- **Local JSON trace fallback** (Wave 3): Same schema as Langfuse, no server required for CI.
- **Post-hoc schema enforcement over constrained decoding** (Wave 3): jsonschema validation is simpler, more testable, and independent of the LLM provider.
- **OpenRouter over direct OpenAI** (post-Wave 3): Single LLM gateway for all models. `AsyncOpenAI` SDK with `base_url="https://openrouter.ai/api/v1"`. Default model: `anthropic/claude-sonnet-4-5`, fallback: `anthropic/claude-haiku-4-5`. Query expansion uses cheaper `anthropic/claude-haiku-4-5`.
- **Local sentence-transformers for routing** (post-Wave 3): `all-MiniLM-L6-v2` (384-dim, ~80MB, CPU). No API key needed. Confidence threshold adjusted from 0.7 to 0.15 for local model's lower average similarities.

## Key Configuration

- `pipeline_config.yaml` — master config (safety, routing, query expansion, hallucination, etc.)
- `.env.example` — required API keys: OPENROUTER_API_KEY, COHERE_API_KEY, LAKERA_API_KEY
- `src/pipeline/routing/routes.yaml` — 5 routes with 12-13 utterances each

## Running Tests

```bash
# All unit + eval tests (155 tests, 21 skipped without OPENROUTER_API_KEY)
python3 -m pytest tests/ --ignore=tests/integration -q

# Integration tests (requires Docker services + API keys)
python3 -m pytest tests/integration -m integration

# Lint
python3 -m ruff check src/ tests/

# Typecheck
python3 -m mypy src/ --ignore-missing-imports

# E2E trace (mocked external deps, real local components)
python3 -m scripts.run_e2e_trace
```
