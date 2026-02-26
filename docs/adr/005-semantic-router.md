# ADR-005: Semantic Router for Query Classification

**Status:** Accepted
**Date:** Wave 2 completion
**Wave:** 2
**Deciders:** AI Platform Engineering

## Context

The pipeline needs to classify incoming queries into different handling strategies: RAG retrieval for knowledge-grounded answers, direct LLM pass-through for general questions, and escalation for out-of-scope or sensitive topics. This classification must happen before retrieval to avoid unnecessary vector lookups and LLM calls for queries that should be handled differently.

## Decision

We built a lightweight semantic router using cosine similarity between the query embedding and pre-defined route exemplar embeddings. Routes are defined in YAML configuration files, each with a set of exemplar phrases and a similarity threshold. The router uses the same local `all-MiniLM-L6-v2` embeddings from ADR-003.

## Alternatives Considered

- **LLM-based classification:** Use the LLM itself to classify the query intent. Most accurate, but adds a full LLM round-trip (1-3s) before retrieval even begins, and incurs per-query cost.
- **Keyword matching:** Simple regex or keyword rules. Fast and free, but brittle -- minor rephrasing bypasses rules, and maintaining keyword lists does not scale.
- **SetFit classifier:** Few-shot fine-tuned classifier. Better accuracy than cosine similarity, but requires training data collection, a training pipeline, and model management overhead.

## Rationale

The semantic router provides a good balance of accuracy, speed, and maintainability. At ~240 lines of code, it is simple to understand and debug. By reusing the local embedding model already loaded for retrieval, it adds no new dependencies or model loading overhead. Route definitions in YAML make it easy for non-engineers to add or modify routes without code changes.

Cosine similarity against exemplar embeddings captures semantic intent better than keyword matching while avoiding the latency and cost of an LLM call. For our route taxonomy (RAG, direct, escalation), the accuracy is sufficient -- the routes are semantically distinct enough that embedding similarity reliably separates them with proper threshold tuning.

## Consequences

### Positive
- No additional LLM call -- classification happens in <10ms using local embeddings
- YAML-based route definitions are easy to add, modify, and review
- Reuses the existing embedding model (no new dependencies)
- Simple codebase (~240 lines) is easy to maintain and debug
- Deterministic: same query always routes to the same strategy

### Negative
- Lower classification accuracy than LLM-based or fine-tuned classifiers
- Similarity thresholds require manual tuning per embedding model and per route
- Ambiguous queries near threshold boundaries may misroute

### Risks
- If the route taxonomy becomes more granular (e.g., 10+ routes with overlapping semantics), cosine similarity may not provide sufficient discrimination; would need to upgrade to a trained classifier
- Changing the embedding model (ADR-003) requires re-tuning all route thresholds
