# Enterprise AI Pipeline — Product Requirements Document (PRD)

**Version:** 1.0
**Date:** February 24, 2026
**Status:** Draft
**Owner:** AI Platform Engineering

---

## 1. Executive Summary

This document defines the requirements for building a production-grade Enterprise AI Pipeline that closes every tool gap identified in our architecture review. The pipeline is a RAG-based (Retrieval-Augmented Generation) system with end-to-end safety, observability, compliance, and continuous improvement mechanisms.

The goal is not to ship a monolithic system all at once. The pipeline will be built in **3 phases across 8 waves**, each delivering independently valuable capabilities that compound over time.

---

## 2. Problem Statement

Our current AI pipeline has documented architectural patterns but lacks concrete tooling for critical capabilities. Specifically:

- **Hallucination detection** is described conceptually but not implemented.
- **Retrieval quality** suffers from duplicate results, oversized contexts, and no monitoring.
- **Security** relies on ad-hoc regex patterns with no layered defense.
- **Compliance** (GDPR right-to-deletion, audit logging) is aspirational, not operational.
- **Deployment** has no shadow mode, canary, or A/B testing infrastructure.
- **Continuous improvement** lacks a structured data flywheel from production feedback to prompt optimization.

Without closing these gaps, the pipeline cannot serve regulated industries, will degrade silently in production, and has no systematic path to improve over time.

---

## 3. Goals and Non-Goals

### Goals

| ID | Goal | Success Metric |
|----|------|----------------|
| G1 | Reduce hallucination rate in production responses | Faithfulness score ≥ 0.92 (measured by HHEM + DeepEval) |
| G2 | Eliminate duplicate/near-duplicate retrieval results | <5% of query results contain >0.95 cosine similarity pairs |
| G3 | Reduce average context size sent to LLM by 40%+ | Token count per request drops from baseline by ≥40% |
| G4 | Block 99%+ of prompt injection attempts | Injection pass-through rate <1% on adversarial benchmark |
| G5 | Achieve GDPR-compliant right-to-deletion | User data deletable within 72 hours, verified by audit |
| G6 | Full observability across every pipeline stage | 100% of LLM calls traced in Langfuse with <5 min alert latency |
| G7 | Enable safe production experimentation | Shadow mode and A/B testing operational for every prompt/model change |
| G8 | Establish a working data flywheel | ≥1 prompt optimization cycle completed per month using production feedback |

### Non-Goals

- Building a custom LLM or foundation model.
- Replacing the existing orchestration framework (LangChain/LlamaIndex) — we augment it.
- Multi-modal pipelines (image, audio) — text-only for v1.
- Real-time streaming responses — batch and request-response only.
- Building custom UIs for annotation — we use off-the-shelf tools (Argilla, Langfuse).

---

## 4. User Personas

| Persona | Role | Needs |
|---------|------|-------|
| **Pipeline Engineer** | Builds and maintains the RAG pipeline | Clear tool choices, easy integration, CI/CD-friendly evals |
| **ML/Eval Engineer** | Owns quality metrics and model evaluation | Eval frameworks, golden datasets, regression testing |
| **Security Engineer** | Owns input/output safety and compliance | Injection detection, audit logs, PII filtering |
| **Compliance Officer** | Ensures GDPR/SOC2/HIPAA adherence | Deletion capability, immutable logs, data lineage |
| **Product Manager** | Ships features, tracks quality | A/B testing, experiment analysis, quality dashboards |
| **Data Annotator** | Labels production failures for improvement | Annotation UI, clear failure triage workflows |

---

## 5. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER REQUEST                              │
└───────────────┬─────────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────┐
│   LAYER 1: INPUT SAFETY    │  Guardrails AI → Lakera Guard → LLM detector
│   - Prompt injection       │
│   - PII detection          │
│   - Input sanitization     │
└───────────────┬───────────┘
                │
                ▼
┌───────────────────────────┐
│   LAYER 2: QUERY ROUTING   │  Semantic Router / SetFit classifier
│   - Intent classification  │     → LangChain RunnableBranch
│   - Strategy selection     │
└───────────────┬───────────┘
                │
                ▼
┌───────────────────────────┐
│   LAYER 3: QUERY EXPANSION │  MultiQueryRetriever / RAG-Fusion
│   - Multi-query generation │
│   - HyDE (when applicable) │
│   - Step-back prompting    │
└───────────────┬───────────┘
                │
                ▼
┌───────────────────────────┐
│   LAYER 4: RETRIEVAL       │  Vector DB (pgvector / Qdrant)
│   - Embedding search       │     + metadata filtering
│   - Semantic dedup         │     + cosine sim threshold
│   - Reranking              │     + Cohere reranker
└───────────────┬───────────┘
                │
                ▼
┌───────────────────────────┐
│   LAYER 5: CONTEXT PREP    │  BM25 sub-scoring / LLMLingua-2
│   - Compression            │
│   - Snippet extraction     │
│   - Token budgeting        │
└───────────────┬───────────┘
                │
                ▼
┌───────────────────────────┐
│   LAYER 6: GENERATION      │  LLM call (OpenAI / Anthropic / self-hosted)
│   - Prompt assembly        │     + lm-format-enforcer (schema)
│   - Schema enforcement     │
└───────────────┬───────────┘
                │
                ▼
┌───────────────────────────┐
│   LAYER 7: OUTPUT SAFETY   │  HHEM / DeepEval FaithfulnessMetric
│   - Hallucination check    │     + NLI (DeBERTa)
│   - Groundedness scoring   │     + Arthur Shield (output filter)
│   - Fact verification      │
└───────────────┬───────────┘
                │
                ▼
┌───────────────────────────┐
│   LAYER 8: OBSERVABILITY   │  Langfuse (tracing) + S3 Object Lock (audit)
│   - Full call tracing      │     + Arize Phoenix (drift monitoring)
│   - Audit logging          │     + Grafana (alerting)
│   - Quality monitoring     │
└───────────────┬───────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        USER RESPONSE                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Functional Requirements

### 6.1 Input Safety (FR-100 series)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-101 | System SHALL run all user inputs through a regex/heuristic validator (Guardrails AI) before any LLM call | P0 |
| FR-102 | System SHALL run inputs passing FR-101 through ML-based injection detection (Lakera Guard) | P0 |
| FR-103 | System SHALL detect and redact PII in inputs before logging (Lakera Guard PII module) | P0 |
| FR-104 | System SHALL support a configurable allowlist/blocklist for input patterns | P1 |
| FR-105 | System SHALL log all blocked inputs with classification reason to audit store | P0 |
| FR-106 | System SHALL enforce output schema via lm-format-enforcer to limit blast radius | P1 |

### 6.2 Query Processing (FR-200 series)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-201 | System SHALL classify incoming queries by intent using Semantic Router | P0 |
| FR-202 | System SHALL route classified queries to appropriate retrieval strategies via RunnableBranch | P0 |
| FR-203 | System SHALL support ≥3 routing destinations (e.g., RAG, direct LLM, SQL, API lookup) | P1 |
| FR-204 | System SHALL expand queries using MultiQueryRetriever (3-5 rephrasings) | P0 |
| FR-205 | System SHALL support RAG-Fusion merge with Reciprocal Rank Fusion | P1 |
| FR-206 | System SHALL support HyDE for document-style queries | P2 |
| FR-207 | System SHALL support step-back prompting for abstract queries | P2 |

### 6.3 Retrieval Quality (FR-300 series)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-301 | System SHALL deduplicate retrieval results using cosine similarity threshold (>0.95 = duplicate) | P0 |
| FR-302 | System SHALL rerank results using Cohere reranker (or equivalent) | P0 |
| FR-303 | System SHALL support document-aware chunking via Unstructured.io | P0 |
| FR-304 | System SHALL compress context using BM25 sub-scoring within chunks | P0 |
| FR-305 | System SHALL support LLMLingua-2 compression as configurable option | P1 |
| FR-306 | System SHALL enforce a configurable token budget per LLM call | P0 |
| FR-307 | System SHALL support late chunking via Jina embeddings as experimental option | P2 |

### 6.4 Output Quality (FR-400 series)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-401 | System SHALL score every LLM response for groundedness using Vectara HHEM | P0 |
| FR-402 | System SHALL flag responses with faithfulness score below configurable threshold | P0 |
| FR-403 | System SHALL support per-claim fact checking via DeepEval FaithfulnessMetric in CI | P1 |
| FR-404 | System SHALL support NLI-based verification using DeBERTa-v3-base | P1 |
| FR-405 | System SHALL block or flag responses that fail output safety checks | P0 |

### 6.5 Compliance (FR-500 series)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-501 | System SHALL store user_id, doc_id, tenant_id as metadata on every vector | P0 |
| FR-502 | System SHALL support right-to-deletion by user_id within 72 hours | P0 |
| FR-503 | System SHALL maintain immutable audit logs via S3 Object Lock (WORM) | P0 |
| FR-504 | System SHALL trace every LLM call with full input/output in Langfuse | P0 |
| FR-505 | System SHALL support data retention policies with configurable TTLs | P1 |
| FR-506 | System SHALL export Langfuse traces to S3 for long-term compliance archive | P0 |

### 6.6 Deployment & Experimentation (FR-600 series)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-601 | System SHALL support shadow mode via Temporal workflow fork | P0 |
| FR-602 | System SHALL support pre-deploy comparison via Promptfoo eval --compare | P0 |
| FR-603 | System SHALL support production A/B testing via LaunchDarkly feature flags | P1 |
| FR-604 | System SHALL support experiment analysis via Statsig or Eppo | P1 |
| FR-605 | System SHALL gate all prompt/model changes behind eval regression tests | P0 |

### 6.7 Observability & Monitoring (FR-700 series)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-701 | System SHALL track embedding drift via Arize Phoenix | P0 |
| FR-702 | System SHALL track cosine sim distribution (p50/p95) between queries and results | P0 |
| FR-703 | System SHALL alert on quality score degradation within 5 minutes | P0 |
| FR-704 | System SHALL run Ragas metrics on daily production sample | P1 |
| FR-705 | System SHALL provide a unified quality dashboard (Grafana + Arize Phoenix) | P1 |

### 6.8 Data Flywheel (FR-800 series)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-801 | System SHALL collect user feedback (thumbs up/down) via Langfuse | P0 |
| FR-802 | System SHALL support structured annotation via Argilla for failure triage | P1 |
| FR-803 | System SHALL maintain and expand a golden evaluation dataset | P0 |
| FR-804 | System SHALL run regression evals in CI via Promptfoo / DeepEval | P0 |
| FR-805 | System SHALL support automated prompt optimization via DSPy | P2 |
| FR-806 | System SHALL support synthetic test data generation via Curator | P2 |

---

## 7. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | End-to-end latency (p95) for standard queries | <3 seconds |
| NFR-02 | Input safety layer latency overhead | <100ms |
| NFR-03 | Hallucination detection latency overhead | <200ms |
| NFR-04 | System availability | 99.9% uptime |
| NFR-05 | Right-to-deletion execution time | <72 hours |
| NFR-06 | Audit log retention | ≥7 years (configurable) |
| NFR-07 | Concurrent request throughput | ≥100 requests/second |
| NFR-08 | Eval suite execution time in CI | <15 minutes |
| NFR-09 | Shadow mode overhead on primary path | 0ms (async fork) |
| NFR-10 | All secrets rotated automatically | ≤90 day rotation cycle |

---

## 8. Dependencies and Risks

### External Dependencies

| Dependency | Risk | Mitigation |
|------------|------|------------|
| Lakera Guard API | Vendor lock-in, uptime | Rebuff as open-source fallback |
| Cohere Reranker API | Cost, latency | Self-hosted cross-encoder fallback |
| Langfuse SaaS | Data residency | Self-host Langfuse (Docker) |
| OpenAI / Anthropic API | Rate limits, cost | Portkey for load balancing + fallback routing |
| S3 Object Lock | AWS-specific | Abstract behind interface for multi-cloud |

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Hallucination detection adds too much latency | Medium | High | Async scoring, serve response optimistically, flag post-hoc |
| Query expansion increases cost 3-5x | Medium | Medium | Budget caps per query, smart routing to skip expansion for simple queries |
| Embedding drift goes undetected | Low | High | Multiple monitoring signals, daily Ragas evals |
| Shadow mode diverges from primary path | Low | Medium | Shared config management, automated consistency checks |

---

## 9. Success Criteria for Launch

| Milestone | Criteria | Validation |
|-----------|----------|------------|
| **Phase 1 Complete** | Core pipeline with safety, dedup, compression, and tracing operational | End-to-end integration test passes; Langfuse shows full traces |
| **Phase 2 Complete** | Compliance, experimentation, and monitoring layers operational | GDPR deletion test passes; shadow mode demo; Grafana dashboard live |
| **Phase 3 Complete** | Data flywheel producing at least 1 optimization cycle | Prompt change deployed via flywheel with measured improvement |

---

## 10. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| 1 | Self-host vs. SaaS for Langfuse? | Platform Eng | Open — Defer to Wave 4. Self-host works for dev/staging. |
| 2 | pgvector vs. Qdrant as primary vector store? | Platform Eng | Resolved (Wave 1) — Qdrant. Async client, filter DSL, good ergonomics. |
| 3 | Budget for Lakera Guard API at production volume? | Finance | Partially Resolved (Wave 2) — L1 regex handles known patterns at $0. Lakera is additive at ~$0.001/query (~$1K/month at 1M queries). Recommend production trial. |
| 4 | Which LLM provider(s) for generation layer? | ML Eng | Resolved (post-Wave 3) — OpenRouter as unified LLM gateway (OpenAI-compatible API). Default: `anthropic/claude-sonnet-4-5`, fallback: `anthropic/claude-haiku-4-5`. Single API key: `OPENROUTER_API_KEY`. |
| 5 | Latency budget allocation per pipeline layer? | Platform Eng | Resolved (Wave 2) — Safety <50ms, Routing <100ms, Expansion <2000ms (optional), Retrieval+Rerank <500ms, Generation <2000ms. Total p95 target: <3s (NFR-01). |
| 6 | Annotation staffing for data flywheel? | Product | Open |

---

## Appendix A: Tool Selection Matrix

See `01-tool-gap-fixes.md` for the full tool evaluation with recommendations per capability area.

## Appendix B: Phase & Wave Plan

See `03-implementation-plan.md` for the detailed phased rollout with waves, milestones, and dependencies.
