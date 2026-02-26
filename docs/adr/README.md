# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Enterprise AI Pipeline.

| ADR | Decision | Wave | Status |
|-----|----------|------|--------|
| 001 | Qdrant over pgvector for vector storage | 1 | Accepted |
| 002 | BM25 sub-scoring over extractive compression | 1 | Accepted |
| 003 | Local sentence-transformers for embeddings | 2 | Accepted |
| 004 | Dual-layer injection defense (Guardrails AI + Lakera) | 2 | Accepted |
| 005 | Semantic Router for query classification | 2 | Accepted |
| 006 | HHEM over NLI/LLM-as-judge for hallucination | 3 | Accepted |
| 007 | OpenRouter as unified LLM gateway | 3 | Accepted |
| 008 | File-based WORM audit log | 4 | Accepted |
| 009 | Hash-based feature flags over LaunchDarkly | 5 | Accepted |
| 010 | asyncio shadow mode over Temporal | 5 | Accepted |
| 011 | scipy for experiment analysis over Statsig | 5 | Accepted |
| 012 | Prometheus + Grafana over Datadog | 6 | Accepted |
| 013 | File-based annotation over Argilla | 7 | Accepted |
