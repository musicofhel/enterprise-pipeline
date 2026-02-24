# Enterprise AI Pipeline

Production-grade RAG pipeline with end-to-end safety, observability, compliance, and continuous improvement.

---

## Documentation

| Doc | Description | Status |
|-----|-------------|--------|
| [01 — Tool Gap Fixes](docs/01-tool-gap-fixes.md) | Concrete tool selections for every architectural gap | ✅ Complete |
| [02 — PRD](docs/02-prd.md) | Product requirements, functional specs, success criteria | ✅ Complete |
| [03 — Implementation Plan](docs/03-implementation-plan.md) | 3 phases, 8 waves, 24-week rollout with exit criteria | ✅ Complete |
| [04 — Technical Specs](docs/04-technical-specs.md) | Infrastructure, schemas, APIs, config, security, runbooks | ✅ Complete |

## Architecture at a Glance

```
User Request
  → Input Safety (Guardrails AI → Lakera Guard)
  → Query Routing (Semantic Router)
  → Query Expansion (MultiQueryRetriever)
  → Retrieval (pgvector + dedup + Cohere rerank)
  → Context Compression (BM25 sub-scoring)
  → Generation (LLM + schema enforcement)
  → Output Quality (HHEM hallucination check)
  → Observability (Langfuse + S3 audit + Arize Phoenix)
User Response
```

## Phases

- **Phase 1 (Weeks 1–10):** Core pipeline — retrieval, safety, quality, tracing
- **Phase 2 (Weeks 8–18):** Production hardening — compliance, experimentation, monitoring
- **Phase 3 (Weeks 16–24):** Continuous improvement — data flywheel, optimization

## Quick Start

```bash
# Read the docs in order
cat docs/01-tool-gap-fixes.md    # What tools and why
cat docs/02-prd.md               # What we're building and success metrics
cat docs/03-implementation-plan.md # How we're building it (phases/waves)
cat docs/04-technical-specs.md    # The technical details
```
