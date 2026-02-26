# ADR-003: Local sentence-transformers for Embeddings

**Status:** Accepted
**Date:** Wave 2 completion
**Wave:** 2
**Deciders:** AI Platform Engineering

## Context

Multiple components of the pipeline require text embeddings: the semantic router for query classification, the retrieval layer for document search, and the injection defense layer for input analysis. We needed an embedding solution that works without external API dependencies, runs on CPU, and provides consistent results across environments.

## Decision

We chose the `all-MiniLM-L6-v2` model from the sentence-transformers library, producing 384-dimensional embeddings with CPU inference. The model is loaded once at startup and shared across all components that need embeddings.

## Alternatives Considered

- **OpenAI text-embedding-3-small:** Higher quality (1536 dimensions), but requires an API key, incurs per-token cost, adds network latency, and creates a hard dependency on OpenAI's availability.
- **Cohere embed-v3:** Competitive quality with search-optimized variants, but same API dependency and cost concerns as OpenAI.
- **Larger local models (e.g., all-mpnet-base-v2):** Better quality (768 dimensions) but ~400MB model size and slower inference. Overkill for our routing and retrieval tasks.

## Rationale

`all-MiniLM-L6-v2` provides the best tradeoff for our requirements. At ~80MB, it loads quickly and runs efficiently on CPU. The 384-dimensional output is sufficient for our semantic routing (cosine similarity thresholds) and retrieval (Qdrant HNSW indexing). By running locally, we eliminate API costs, network latency, and external service dependencies. Embeddings are deterministic across runs, which simplifies testing and debugging.

The model's quality is adequate for our use cases: routing queries to the correct strategy (where we control the threshold tuning) and retrieving relevant document chunks (where we combine with BM25 reranking). We do not need the marginal quality improvement of larger models for these tasks.

## Consequences

### Positive
- Zero API cost for embeddings across all pipeline components
- No external dependency -- works offline, in CI, and in air-gapped environments
- Deterministic embeddings enable reproducible tests
- Fast CPU inference (~5ms per embedding) suitable for real-time queries
- Small model footprint (~80MB) with quick cold start

### Negative
- Lower embedding quality than OpenAI/Cohere (384 vs 1536 dimensions)
- Confidence thresholds for routing need careful tuning per model -- cannot reuse thresholds from papers using OpenAI embeddings
- CPU-only inference limits throughput for batch embedding of large document corpora

### Risks
- If retrieval quality proves insufficient, upgrading to a larger local model or API-based embeddings would require re-indexing all vectors in Qdrant and re-tuning router thresholds
- The sentence-transformers library pins specific PyTorch versions, which can conflict with other ML dependencies
