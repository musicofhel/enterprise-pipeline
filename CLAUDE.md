# Enterprise AI Pipeline — Project Context

## Overview

Production-grade RAG pipeline built in 3 phases across 8 waves. Python + FastAPI, Qdrant vector store, Docker Compose + GitHub Actions CI.

- **PRD:** `docs/02-prd.md`
- **Implementation plan:** `docs/03-implementation-plan.md`
- **Tech spec:** `docs/04-technical-specs.md`

## Current Status

- **Wave 1 (Retrieval Quality Foundation):** Complete. Tag: `wave-1-complete`.
- **Wave 2 (Input Safety & Query Intelligence):** Complete. Tag: `wave-2-complete`. Verification follow-up complete. Routing now branches on route result. Injection regex fixed for hyphen-separated evasion. 128 tests passing. Lint and typecheck clean.
- **Wave 3 (Output Quality & Tracing):** Not started.

## Project Structure

```
src/
├── main.py                         # FastAPI app factory
├── config/                         # Pydantic settings + YAML config loader
├── models/schemas.py               # API request/response models
├── api/                            # FastAPI routes + DI wiring (deps.py)
├── pipeline/
│   ├── orchestrator.py             # Central pipeline coordinator (8 stages)
│   ├── safety/                     # L1 regex injection + PII detection
│   ├── routing/                    # Semantic query router (cosine sim + YAML routes)
│   ├── retrieval/                  # Qdrant client, embeddings, query expander, RRF
│   ├── reranking/                  # Cohere reranker
│   ├── compression/                # BM25 sub-scoring + token budget
│   ├── generation/                 # LLM client (OpenAI/Anthropic)
│   └── quality/                    # Hallucination check (stub — Wave 3)
├── observability/                  # Langfuse tracing + structlog
└── utils/tokens.py                 # tiktoken helpers
tests/
├── unit/                           # 18 test files
├── eval/                           # Exit criteria tests
└── integration/                    # E2E pipeline test
```

## Open Issues

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| 001 | Validate EC-4 Cohere Rerank in staging | P0 | Open — blocks Wave 3 |
| 002 | Backfill null baselines (Wave 1 layers) | P1 | Open — needs live services |
| 003 | Compression sentence logging | P1 | Fixed |
| 004 | Routing accuracy with real OpenAI embeddings | P1 | Open — needs OPENAI_API_KEY |
| 005 | Multi-query recall with live Qdrant retrieval | P1 | Open — needs Qdrant + OPENAI_API_KEY |
| 006 | Backfill null latency baselines (Wave 2 layers) | P2 | Open — needs API keys |
| 007 | Missing PII pattern types (addresses, IBANs, API tokens, MRNs) | P2 | Open |
| 008 | Passport number triggers SSN false positive | P3 | Open |
| 009 | FR-202 routing deferral was undocumented (now fixed) | P3 | Open — process gap |
| 010 | Lakera L2 social engineering validation | P1 | Open — needs LAKERA_API_KEY |
| 011 | Natural language PII beyond regex scope | P3 | Open — documentation |

## Known Technical Debt

### Injection Defense
- L1 regex blocks 15/20 adversarial payloads (was 14/20 before hyphen evasion fix).
- A3 hyphen-separated evasion fixed (commit `0fe2b46`).
- 5 remaining bypasses are social engineering attacks requiring Lakera L2 (ISSUE-010).
- L2 Lakera Guard has never been tested — no LAKERA_API_KEY provisioned.

### Routing
- Routing branching implemented (commit `0fe2b46`). PipelineOrchestrator dispatches on route result.
- `rag_knowledge_base` → full RAG, `direct_llm` → skip retrieval, `escalate_human` → handoff.
- `sql_structured_data` and `api_lookup` raise `NotImplementedError` (Wave 3+).
- With deterministic embeddings, all queries default to `rag_knowledge_base` (confidence < threshold). Needs real OpenAI embeddings (ISSUE-004).

### PII Detection
- Detector missing 4 pattern types: addresses, IBANs, API tokens, MRNs (ISSUE-007).
- Passport number false-positives as SSN on 9-digit values (ISSUE-008).
- Natural-language numbers ("oh seven eight...") beyond regex scope (ISSUE-011).

### Pipeline Stage Reality
- **6/12 stages run real logic:** L1 regex, PII detection, routing algorithm, dedup, BM25 compression, token budget.
- **6/12 stages are mocked/stubbed/skipped:** Lakera L2 (skipped — no API key), Qdrant (mocked), Cohere rerank (mocked), LLM generation (mocked), HHEM hallucination check (stub — Wave 3), Langfuse tracing (no server).

### Compression
- BM25 sub-scoring achieves 55.5% token reduction on realistic 216-242 token chunks (target ≥40% met).
- `sentences_per_chunk=5` default. Compression ratio depends on sentence count per chunk.

## Decisions Made

- **Qdrant over pgvector** (Wave 1): Async client, filter DSL, good ergonomics.
- **Lightweight semantic router over `semantic-router` package** (Wave 2): numpy cosine sim + YAML routes, ~240 lines, no heavy ML deps.
- **Constructor DI, not globals**: Every component takes deps as constructor args, wired in `deps.py`.
- **Stubs are functional**: Routing returns default, hallucination returns pass, so pipeline works E2E from day one.
- **FR-202 routing dispatch** (Wave 2 verification follow-up): Implemented routing branching that was missing from Wave 2 deliverables in implementation plan. Was a spec gap between PRD (FR-202 P0) and implementation plan (Wave 2 only listed classification).

## Key Configuration

- `pipeline_config.yaml` — master config (safety, routing, query expansion, etc.)
- `.env.example` — required API keys: OPENAI_API_KEY, COHERE_API_KEY, LAKERA_API_KEY
- `src/pipeline/routing/routes.yaml` — 5 routes with 12-13 utterances each

## Running Tests

```bash
# All unit + eval tests (128 tests)
python3 -m pytest tests/ --ignore=tests/integration -q

# Integration tests (requires Docker services)
python3 -m pytest tests/integration -m integration

# Lint
python3 -m ruff check src/ tests/

# Typecheck
python3 -m mypy src/ --ignore-missing-imports
```
