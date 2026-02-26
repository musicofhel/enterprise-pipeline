# Enterprise AI Pipeline

Production-grade RAG pipeline built in 3 phases across 8 waves. Python + FastAPI, Qdrant vector store, OpenRouter LLM gateway, Docker Compose + GitHub Actions CI.

## Architecture

```
User Request
  → Input Safety (L1 regex injection + PII detection; optional Lakera Guard L2)
  → Query Routing (local sentence-transformers, all-MiniLM-L6-v2, YAML routes)
  → Query Expansion (optional — multi-query via OpenRouter Claude Haiku)
  → Retrieval (Qdrant + cosine dedup + Cohere rerank + RRF)
  → Context Compression (BM25 sub-scoring + token budget enforcement)
  → Generation (OpenRouter — Claude Sonnet 4.5 default, Haiku fallback)
  → Output Quality (HHEM hallucination check — real CPU inference, no API key)
  → Observability (Langfuse tracing + structlog JSON logging)
User Response
```

## Current Status — Wave 3 Complete

| Wave | Focus | Status | Tests |
|------|-------|--------|-------|
| 1 | Retrieval Quality Foundation | Complete | 31 unit tests |
| 2 | Input Safety & Query Intelligence | Complete | 45+ unit tests |
| 3 | Output Quality & Tracing | Complete | 175 pass, 1 skip |

**7/12 pipeline stages run real logic.** 4 are mocked (Qdrant, Cohere rerank, LLM generation, embeddings — all require API keys or services). 1 skipped (Lakera L2 — needs API key).

## Quick Start

```bash
# Install
pip install -e ".[dev,eval]"
python -m spacy download en_core_web_sm

# Run tests (no API keys needed)
make test                    # unit tests only
make lint                    # ruff check
make typecheck               # mypy

# Run eval tests (needs OPENROUTER_API_KEY)
OPENROUTER_API_KEY=sk-or-... make test-eval

# Start infrastructure (Docker)
make infra                   # Qdrant, Langfuse, Redis, Postgres

# Start the API server
make dev                     # uvicorn on port 8000

# E2E trace (mocked external deps, real local components)
python3 -m scripts.run_e2e_trace
```

## Configuration

| File | Purpose |
|------|---------|
| `pipeline_config.yaml` | Master config — safety, routing, query expansion, hallucination, generation |
| `.env` / `.env.example` | API keys: `OPENROUTER_API_KEY`, `COHERE_API_KEY`, `LAKERA_API_KEY` |
| `src/pipeline/routing/routes.yaml` | 5 routes with 12-13 utterances each |
| `environments/{base,development,production}.yaml` | Environment-specific config overlays |

## Key Dependencies

| Purpose | Package |
|---------|---------|
| LLM Gateway | `openai` SDK → OpenRouter (`https://openrouter.ai/api/v1`) |
| Routing Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim, CPU, no API key) |
| Hallucination Check | `transformers` (`vectara/hallucination_evaluation_model`, CPU) |
| Vector Store | `qdrant-client` |
| Reranking | `cohere` |
| BM25 Compression | `rank-bm25` + `spacy` |
| Tracing | `langfuse` (local JSON fallback when no server) |
| Eval | `deepeval` (faithfulness via OpenRouter) |

## Documentation

| Doc | Description |
|-----|-------------|
| [CLAUDE.md](CLAUDE.md) | Project context, structure, decisions, open issues |
| [01 — Tool Gap Fixes](docs/01-tool-gap-fixes.md) | Tool selections for architectural gaps |
| [02 — PRD](docs/02-prd.md) | Product requirements and success criteria |
| [03 — Implementation Plan](docs/03-implementation-plan.md) | 3 phases, 8 waves, 24-week rollout |
| [04 — Technical Specs](docs/04-technical-specs.md) | Infrastructure, schemas, APIs, config, security |

## Phases

- **Phase 1 (Weeks 1–10):** Core pipeline — retrieval, safety, quality, tracing *(Waves 1-3 complete)*
- **Phase 2 (Weeks 8–18):** Production hardening — compliance, experimentation, monitoring
- **Phase 3 (Weeks 16–24):** Continuous improvement — data flywheel, optimization
