# ADR-006: HHEM over NLI/LLM-as-Judge for Hallucination Detection

**Status:** Accepted
**Date:** Wave 3 completion
**Wave:** 3
**Deciders:** AI Platform Engineering

## Context

RAG pipelines are susceptible to hallucination -- the LLM generating statements not supported by the retrieved context. We needed a mechanism to verify that generated responses are grounded in the source documents before returning them to users. The verification must run inline (blocking the response) or as a post-generation check, and should not require additional LLM API calls for cost reasons.

## Decision

We adopted the `vectara/hallucination_evaluation_model` (HHEM) via the Hugging Face transformers library. HHEM takes a premise (retrieved context) and hypothesis (generated response) and returns a single grounding score between 0 and 1. Responses below a configurable threshold are flagged as potentially hallucinated.

## Alternatives Considered

- **NLI with DeBERTa-v3:** Natural Language Inference model for entailment checking. Requires sentence-level decomposition of the response, making it more complex to implement and slower (multiple inference passes per response).
- **LLM-as-judge:** Use a second LLM call to evaluate faithfulness. Most flexible but doubles LLM cost per query and adds 1-3s latency. Also subject to its own hallucination.
- **DeepEval FaithfulnessMetric:** Higher-level abstraction, but opaque scoring methodology and adds a framework dependency for a single metric.

## Rationale

HHEM provides the simplest integration path: one model, one forward pass, one score. The model runs locally on CPU, eliminating API costs and external dependencies. Warm inference takes approximately 150ms, which is acceptable for inline verification. The single-score output is easy to threshold and log, unlike NLI which requires aggregating entailment scores across decomposed sentences.

HHEM was specifically trained for the hallucination detection task (premise-hypothesis grounding), making it more suitable than general-purpose NLI models. The model is well-documented and has been validated in published benchmarks for RAG faithfulness evaluation.

## Consequences

### Positive
- Single model, single score -- simple to integrate, interpret, and threshold
- Local inference with no API cost (runs on CPU)
- ~150ms warm inference latency is acceptable for inline response verification
- Purpose-built for hallucination detection, not repurposed from a general NLI task
- Deterministic scores enable reproducible testing

### Negative
- Pinned to `transformers<5` due to breaking API changes in transformers v5 that affect HHEM's model loading
- ~900ms cold start on first inference (model loading)
- Single-score output provides less granularity than sentence-level NLI decomposition

### Risks
- HHEM model could be deprecated or removed from Hugging Face Hub; mitigated by planning an NLI-based fallback using DeBERTa-v3 that can be activated if HHEM becomes unavailable
- The `transformers<5` pin may conflict with other dependencies that require transformers v5+; mitigated by isolating HHEM in a separate virtual environment if needed
