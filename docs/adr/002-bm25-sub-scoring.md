# ADR-002: BM25 Sub-Scoring over Extractive Compression

**Status:** Accepted
**Date:** Wave 1 completion
**Wave:** 1
**Deciders:** AI Platform Engineering

## Context

After vector retrieval returns candidate chunks, we need to compress the context before sending it to the LLM to reduce token costs and improve response quality. Sending all retrieved chunks verbatim often exceeds token budgets and dilutes relevant information with noise. We needed a strategy that preserves coherence while fitting within configurable token limits.

## Decision

We implemented BM25 sub-scoring within retrieved chunks, followed by token budget enforcement. Each sentence within a chunk is scored against the original query using BM25, and sentences are ranked and selected up to the configured token budget. Full sentences are always preserved -- we never truncate mid-sentence.

## Alternatives Considered

- **LLMLingua-2:** Neural compression that achieves aggressive compression ratios (up to 20x). Requires an additional model and GPU resources, adds latency, and can produce incoherent output at high compression ratios.
- **Extractive summarization:** Uses a summarization model to extract key sentences. Adds model inference latency and may miss query-specific relevance (optimizes for general importance, not query relevance).
- **Naive truncation:** Simply cut chunks at the token limit. Fast but destroys coherence, may cut mid-sentence, and has no relevance awareness.

## Rationale

BM25 sub-scoring provides query-aware compression without requiring an additional ML model. By scoring individual sentences against the query terms, we retain the most relevant content while maintaining sentence-level coherence. The approach is computationally cheap (pure lexical matching), deterministic, and configurable via threshold and budget parameters.

Compared to LLMLingua-2, we sacrifice maximum compression ratio but gain predictability and coherence. The token budget is enforced greedily by adding sentences in descending BM25 score order until the budget is exhausted, ensuring we always include the most relevant content first.

## Consequences

### Positive
- No additional model inference required -- pure lexical computation
- Preserves full sentences, maintaining readability and coherence
- Query-aware: ranks content by relevance to the actual user query
- Configurable token budget and minimum relevance thresholds
- Deterministic output for the same query and retrieval results

### Negative
- Less aggressive compression than neural methods like LLMLingua-2
- BM25 is lexical-only -- may miss semantic relevance that embedding-based compression would catch
- Sentence boundary detection adds a preprocessing step

### Risks
- For very long chunks with many sentences, BM25 scoring could become a bottleneck; mitigated by limiting chunk size at ingestion time
- Lexical mismatch (synonyms, paraphrases) may cause relevant sentences to score low; mitigated by upstream semantic retrieval already filtering for relevance
