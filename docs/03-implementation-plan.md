# Enterprise AI Pipeline — Implementation Plan

**Version:** 1.0
**Date:** February 24, 2026
**Estimated Duration:** 24 weeks (6 months)

---

## Overview

The pipeline is built across **3 Phases** and **8 Waves**. Each wave delivers independently deployable capability. Waves within a phase can overlap where dependencies allow.

```
Phase 1: Core Pipeline (Weeks 1–10)
├── Wave 1: Retrieval Quality Foundation      (Weeks 1–4)
├── Wave 2: Input Safety & Query Intelligence (Weeks 3–6)
└── Wave 3: Output Quality & Tracing          (Weeks 5–10)

Phase 2: Production Hardening (Weeks 8–18)
├── Wave 4: Compliance & Data Governance      (Weeks 8–12)
├── Wave 5: Deployment & Experimentation      (Weeks 10–14)
└── Wave 6: Observability & Monitoring        (Weeks 12–18)

Phase 3: Continuous Improvement (Weeks 16–24)
├── Wave 7: Data Flywheel (Feedback → Evals)  (Weeks 16–20)
└── Wave 8: Advanced Optimization             (Weeks 20–24)
```

---

## Phase 1: Core Pipeline

> **Goal:** A working RAG pipeline with clean retrieval, safety guardrails, hallucination detection, and full tracing. This is the minimum viable production system.

---

### Wave 1 — Retrieval Quality Foundation

**Duration:** Weeks 1–4
**Team:** 2 Pipeline Engineers
**Dependencies:** Existing vector store, embedding model

#### Deliverables

| # | Deliverable | Tool(s) | Acceptance Criteria |
|---|-------------|---------|---------------------|
| 1.1 | Document-aware chunking pipeline | Unstructured.io | Documents chunked respecting headers, tables, lists; no mid-sentence splits |
| 1.2 | Semantic deduplication on retrieval results | Custom cosine sim threshold (numpy) | <5% of result sets contain >0.95 similarity pairs |
| 1.3 | Context compression via BM25 sub-scoring | Custom (rank-bm25 library) | Average context tokens reduced by ≥40% vs. baseline |
| 1.4 | Reranking integration | Cohere Rerank API | MRR@10 improves by ≥15% on eval dataset |
| 1.5 | Token budget enforcement | Custom middleware | No LLM call exceeds configured token limit |

#### Technical Specifications

**1.1 — Document-Aware Chunking**

```
Input:  Raw documents (PDF, DOCX, HTML, Markdown)
Output: Chunks with metadata {doc_id, chunk_id, section_header, page_number, user_id, tenant_id}

Processing:
  1. Unstructured.io partition → element-level parse (headers, paragraphs, tables, lists)
  2. Chunking strategy: by_title with max_characters=1500, overlap=200
  3. Metadata propagation: every chunk inherits doc-level metadata
  4. Output: JSON lines to vector store ingestion pipeline

Config (chunking_config.yaml):
  strategy: by_title
  max_characters: 1500
  overlap: 200
  combine_under_n_chars: 500
  respect_table_boundaries: true
```

**1.2 — Semantic Deduplication**

```python
# Post-retrieval dedup — runs after vector search, before reranking
# Threshold: configurable, default 0.95

def deduplicate_results(results: list[RetrievalResult], threshold: float = 0.95) -> list[RetrievalResult]:
    """
    Pairwise cosine similarity. Greedy removal: for each duplicate pair,
    keep the one with higher retrieval score.
    Time complexity: O(n²) — acceptable for n < 100 results.
    """
```

**1.3 — BM25 Sub-Scoring for Context Compression**

```
Input:  Retrieved chunks (post-dedup, post-rerank)
Output: Compressed context — top-k sentences per chunk

Process:
  1. Split each chunk into sentences (spaCy sentence tokenizer)
  2. BM25 score each sentence against the original query
  3. Keep top-k sentences per chunk (k configurable, default 5)
  4. Reassemble in original order within each chunk
  5. Enforce total token budget across all chunks

Config:
  sentences_per_chunk: 5
  max_total_tokens: 4000
  preserve_order: true
```

#### Exit Criteria
- [ ] Chunking pipeline processes 10 document types without error
- [ ] Dedup reduces duplicate retrieval results to <5%
- [ ] Context compression achieves ≥40% token reduction
- [ ] Reranking improves MRR@10 by ≥15%
- [ ] Token budget never exceeded in 1000 test queries

---

### Wave 2 — Input Safety & Query Intelligence

**Duration:** Weeks 3–6
**Team:** 1 Security Engineer, 1 Pipeline Engineer
**Dependencies:** Wave 1 (retrieval pipeline exists to route to)

#### Deliverables

| # | Deliverable | Tool(s) | Acceptance Criteria |
|---|-------------|---------|---------------------|
| 2.1 | Regex/heuristic injection filter (Layer 1) | Guardrails AI validators | Blocks known injection patterns in <10ms |
| 2.2 | ML-based injection detection (Layer 2) | Lakera Guard API | <1% pass-through on adversarial benchmark |
| 2.3 | PII detection and redaction | Lakera Guard PII module | Zero PII in logged traces |
| 2.4 | Semantic query routing | Semantic Router (Aurelio Labs) | >95% classification accuracy on test set |
| 2.5 | Multi-query expansion | LangChain MultiQueryRetriever | Recall@10 improves by ≥20% on eval set |

#### Technical Specifications

**2.1/2.2 — Layered Injection Defense**

```
Request Flow:
  User Input
    → Layer 1: Guardrails AI validators (regex, heuristics)
        - Known injection patterns
        - Suspicious token sequences
        - Latency: <10ms
        - Action on match: BLOCK + log
    → Layer 2: Lakera Guard API
        - ML-based classification
        - Jailbreak detection
        - Indirect injection detection
        - Latency: <50ms
        - Action on match: BLOCK + log
    → Layer 3 (P2): LLM-based detector for edge cases
        - Only triggered on medium-confidence results from Layer 2
        - Latency: <500ms

Logging:
  Every blocked request → audit log with:
    - timestamp, user_id, input_hash (not raw input for PII safety)
    - detection_layer, classification, confidence
    - action_taken
```

**2.4 — Semantic Query Routing**

```
Routes:
  - rag_knowledge_base: "What is our refund policy?" → Standard RAG pipeline
  - sql_structured_data: "How many orders last month?" → Text-to-SQL
  - direct_llm: "Summarize this text" → No retrieval needed
  - api_lookup: "What's the status of order #12345?" → API call
  - escalate_human: "I want to speak to someone" → Human handoff

Config (routes.yaml):
  - name: rag_knowledge_base
    utterances:
      - "What is the policy on..."
      - "Tell me about..."
      - "How does X work?"
    threshold: 0.7

Implementation: Semantic Router with OpenAI embeddings
Fallback: If no route exceeds threshold → default to rag_knowledge_base
```

#### Exit Criteria
- [ ] Injection defense blocks ≥99% of attacks in OWASP LLM benchmark
- [ ] PII detection catches 100% of test PII patterns
- [ ] Query routing achieves >95% accuracy on 500-query test set
- [ ] Multi-query expansion improves recall by ≥20%
- [ ] Total input processing latency <100ms (p95)

---

### Wave 3 — Output Quality & Tracing

**Duration:** Weeks 5–10
**Team:** 1 ML Engineer, 1 Pipeline Engineer
**Dependencies:** Wave 1 (retrieval), Wave 2 (input processing)

#### Deliverables

| # | Deliverable | Tool(s) | Acceptance Criteria |
|---|-------------|---------|---------------------|
| 3.1 | Hallucination detection (real-time) | Vectara HHEM | Faithfulness ≥ 0.92 on eval set |
| 3.2 | Claim-level fact checking (CI) | DeepEval FaithfulnessMetric | Runs in CI, fails build on regression |
| 3.3 | Full LLM call tracing | Langfuse | 100% of calls traced with input/output/latency/tokens |
| 3.4 | Output schema enforcement | lm-format-enforcer | 100% of outputs conform to expected schema |
| 3.5 | Structured logging | structlog (Python) | All logs are structured JSON |

#### Technical Specifications

**3.1 — Real-Time Hallucination Detection**

```
Flow:
  LLM Response + Retrieved Context
    → HHEM cross-encoder scores response against context
    → Score: 0.0 (hallucinated) to 1.0 (grounded)

Thresholds:
  ≥ 0.85: PASS — serve response
  0.70–0.85: WARN — serve with disclaimer, flag for review
  < 0.70: FAIL — don't serve, return fallback response

Fallback response: "I found relevant information but I'm not confident
  in my answer. Here are the source documents: [links]"

Performance:
  Model: vectara/hallucination_evaluation_model (HuggingFace)
  Hosting: Self-hosted on GPU instance (T4 sufficient)
  Latency target: <200ms per response
  Batch: Score all sentences in parallel
```

**3.3 — Langfuse Tracing Integration**

```
Every pipeline execution produces a Trace containing:
  - trace_id (UUID)
  - user_id
  - session_id
  - Spans:
      - input_safety (duration, result, blocked?)
      - query_routing (duration, route_selected, confidence)
      - query_expansion (duration, queries_generated)
      - retrieval (duration, num_results, top_score)
      - deduplication (duration, num_removed)
      - compression (duration, tokens_before, tokens_after)
      - generation (duration, model, tokens_in, tokens_out, cost)
      - hallucination_check (duration, score, passed?)
  - Scores:
      - faithfulness_score (HHEM)
      - user_feedback (when received)
  - Metadata:
      - pipeline_version
      - config_hash
      - feature_flags
```

#### Exit Criteria
- [ ] HHEM scores ≥0.92 faithfulness on eval set of 500 queries
- [ ] DeepEval runs in CI and blocks builds with >5% regression
- [ ] 100% of LLM calls have Langfuse traces with all spans
- [ ] All logs output structured JSON (no string-formatted logs)
- [ ] End-to-end pipeline latency <3s (p95)

---

## Phase 2: Production Hardening

> **Goal:** The pipeline is compliant, observable, and safely changeable. Teams can ship prompt/model changes without fear.

---

### Wave 4 — Compliance & Data Governance

**Duration:** Weeks 8–12
**Team:** 1 Security Engineer, 1 Backend Engineer
**Dependencies:** Wave 3 (Langfuse tracing operational)

#### Deliverables

| # | Deliverable | Tool(s) | Acceptance Criteria |
|---|-------------|---------|---------------------|
| 4.1 | Metadata schema on all vectors | pgvector / Qdrant | Every vector has user_id, doc_id, tenant_id |
| 4.2 | Right-to-deletion API | Custom + vector store API | User data deleted within 72 hours, verified |
| 4.3 | Immutable audit log store | S3 Object Lock (WORM) | Logs cannot be modified or deleted; 7-year retention |
| 4.4 | Langfuse → S3 export pipeline | Langfuse export + AWS Lambda | Daily export, validated for completeness |
| 4.5 | Data retention policy automation | Custom + S3 lifecycle rules | Expired data purged automatically |

#### Technical Specifications

**4.2 — Right-to-Deletion API**

```
Endpoint: DELETE /api/v1/users/{user_id}/data

Process:
  1. Validate request (auth, authorization)
  2. Delete vectors: DELETE FROM embeddings WHERE user_id = :user_id
     (or Qdrant filter delete, depending on vector store)
  3. Delete document sources: DELETE FROM documents WHERE user_id = :user_id
  4. Redact Langfuse traces: Replace input/output with "[REDACTED]" for user's traces
  5. Log deletion event to immutable audit log (S3)
  6. Return deletion receipt with timestamp and item counts

SLA: Complete within 72 hours of request
Verification: Weekly automated check — query for any remaining data after deletion

Audit trail entry:
  {
    "event": "user_data_deletion",
    "user_id": "...",
    "timestamp": "...",
    "vectors_deleted": 142,
    "documents_deleted": 23,
    "traces_redacted": 87,
    "executor": "system/deletion-worker",
    "receipt_id": "..."
  }
```

**4.3 — Immutable Audit Logging**

```
Architecture:
  Langfuse (operational logs, queryable)
    → Daily export to S3 (Parquet format)
      → S3 Object Lock (Compliance mode, 7-year retention)

S3 Configuration:
  Bucket: {org}-ai-pipeline-audit-logs
  Object Lock: Compliance mode (cannot be disabled, even by root)
  Retention: 2,555 days (7 years)
  Lifecycle: Transition to Glacier Deep Archive after 90 days

What's logged:
  - Every LLM call (input, output, model, cost, latency)
  - Every safety check result
  - Every user feedback event
  - Every data deletion event
  - Every config/prompt change with before/after
  - Every A/B test assignment
```

#### Exit Criteria
- [ ] All vectors in production have user_id, doc_id, tenant_id metadata
- [ ] Deletion API deletes a test user's data within 72 hours
- [ ] S3 Object Lock verified — attempt to delete/modify logs fails
- [ ] Daily Langfuse export runs successfully for 14 consecutive days
- [ ] Compliance officer signs off on audit trail completeness

---

### Wave 5 — Deployment & Experimentation

**Duration:** Weeks 10–14
**Team:** 1 Platform Engineer, 1 ML Engineer
**Dependencies:** Wave 3 (tracing), Wave 4 (audit logging)

#### Deliverables

| # | Deliverable | Tool(s) | Acceptance Criteria |
|---|-------------|---------|---------------------|
| 5.1 | Pre-deploy eval comparison | Promptfoo | `promptfoo eval --compare` in CI; blocks deploy on regression |
| 5.2 | Shadow mode pipeline | Temporal workflow fork | Shadow path runs on 100% traffic, 0ms impact on primary |
| 5.3 | Feature-flagged pipeline versions | LaunchDarkly | Can toggle between pipeline versions per user/segment |
| 5.4 | A/B test analysis | Statsig or Eppo | Statistical significance calculations for prompt experiments |
| 5.5 | Eval regression gate in CI/CD | Promptfoo + DeepEval | No prompt/model change ships without passing evals |

#### Technical Specifications

**5.1 — Pre-Deploy Eval Comparison**

```yaml
# promptfoo.config.yaml
prompts:
  - file://prompts/current.txt
  - file://prompts/candidate.txt

providers:
  - id: openai:gpt-4o
    config:
      temperature: 0

tests:
  - file://golden_dataset.jsonl

defaultTest:
  assert:
    - type: llm-rubric
      value: "Response is factually grounded in the provided context"
    - type: python
      value: "output_faithfulness_score >= 0.85"
    - type: cost
      value: "< 0.05"

# CI integration:
# promptfoo eval --compare --output results.json
# Script checks: candidate must not regress on any metric by >2%
```

**5.2 — Shadow Mode via Temporal**

```
Temporal Workflow:
  1. Receive request
  2. Fork:
     a. Primary path → current pipeline version → serve response
     b. Shadow path → candidate pipeline version → log output (don't serve)
  3. Both paths log to Langfuse with pipeline_version tag
  4. Async comparison job runs nightly:
     - Compare faithfulness scores
     - Compare latency
     - Compare cost
     - Compare user feedback (primary only, shadow N/A)
     - Generate comparison report

Shadow path guarantees:
  - Async execution — cannot block primary
  - Separate LLM API key budget (shadow_budget)
  - Auto-disable if shadow latency >10x primary (circuit breaker)
  - Results never served to users
```

#### Exit Criteria
- [ ] Promptfoo runs in CI and blocks deploys with >2% regression
- [ ] Shadow mode runs for 1 week processing 100% traffic with zero primary impact
- [ ] Feature flags successfully toggle 10% of traffic to new pipeline version
- [ ] A/B test report shows statistical significance calculation
- [ ] No prompt/model change ships without CI eval gate passing

---

### Wave 6 — Observability & Monitoring

**Duration:** Weeks 12–18
**Team:** 1 Platform Engineer, 1 ML Engineer
**Dependencies:** Wave 3 (Langfuse), Wave 5 (shadow mode generating comparison data)

#### Deliverables

| # | Deliverable | Tool(s) | Acceptance Criteria |
|---|-------------|---------|---------------------|
| 6.1 | Embedding drift monitoring | Arize Phoenix | Dashboard shows drift trends; alerts on significant shift |
| 6.2 | Retrieval quality canary | Custom cosine sim tracking + Grafana | p50/p95 cosine sim tracked; alert if p50 drops >10% |
| 6.3 | Daily Ragas eval on production sample | Ragas + cron job | Daily faithfulness, context precision, answer relevancy scores |
| 6.4 | Unified quality dashboard | Grafana | Single dashboard: latency, cost, quality scores, errors, drift |
| 6.5 | Alert playbooks | Runbook docs | Every alert has documented investigation + remediation steps |

#### Technical Specifications

**6.2 — Retrieval Quality Canary**

```python
# Runs every hour on the last hour's production queries
# Tracks cosine similarity distribution between queries and retrieved docs

Metrics exported to Prometheus:
  - retrieval_cosine_sim_p50
  - retrieval_cosine_sim_p95
  - retrieval_cosine_sim_mean
  - retrieval_result_count_avg
  - retrieval_empty_result_rate

Grafana alerts:
  - WARN: p50 drops >5% from 7-day rolling average
  - CRITICAL: p50 drops >10% OR empty_result_rate > 5%
  - CRITICAL: p95 drops below 0.3 (results are barely relevant)
```

**6.4 — Unified Dashboard Panels**

```
Dashboard: "AI Pipeline Health"

Row 1 — Traffic & Latency
  - Requests per minute (total, by route)
  - p50/p95/p99 end-to-end latency
  - p50/p95 per pipeline layer

Row 2 — Quality Scores
  - HHEM faithfulness score (p50, p95, % below threshold)
  - Ragas daily scores (faithfulness, context precision, answer relevancy)
  - User feedback rate (thumbs up %)

Row 3 — Retrieval Health
  - Cosine sim distribution (p50/p95)
  - Empty result rate
  - Embedding drift indicator (Arize Phoenix embed)
  - Dedup removal rate

Row 4 — Safety & Compliance
  - Injection attempts blocked (by layer)
  - PII detections
  - Deletion requests processed
  - Audit log export status

Row 5 — Cost
  - LLM API cost per day (by model, by route)
  - Token usage trends
  - Cost per query (mean, p95)
```

#### Exit Criteria
- [ ] Arize Phoenix dashboard shows embedding distributions and drift trends
- [ ] Grafana alerts fire within 5 minutes of injected quality degradation
- [ ] Ragas daily eval runs for 14 consecutive days
- [ ] Unified dashboard has all 5 rows operational
- [ ] Every alert has a documented runbook

---

## Phase 3: Continuous Improvement

> **Goal:** The pipeline gets better over time. Production failures become training data. Prompt changes are data-driven.

---

### Wave 7 — Data Flywheel (Feedback → Evals)

**Duration:** Weeks 16–20
**Team:** 1 ML Engineer, 1 Data Annotator (part-time)
**Dependencies:** Wave 3 (Langfuse), Wave 6 (monitoring identifies failures)

#### Deliverables

| # | Deliverable | Tool(s) | Acceptance Criteria |
|---|-------------|---------|---------------------|
| 7.1 | User feedback collection | Langfuse SDK | Thumbs up/down captured on ≥10% of responses |
| 7.2 | Failure triage workflow | Langfuse dashboard + Arize Phoenix | Low-score responses clustered and triaged weekly |
| 7.3 | Annotation pipeline | Argilla | 50+ annotated failure examples per week |
| 7.4 | Golden dataset expansion | Argilla export + Lilac | Golden dataset grows by ≥20% per month |
| 7.5 | Regression eval suite | Promptfoo + DeepEval | Suite includes examples from every known failure pattern |

#### Flywheel Process

```
Weekly Cadence:

Monday:
  - Auto-generated report: lowest-scoring responses from past week
  - Arize Phoenix clusters failure patterns

Tuesday-Wednesday:
  - Annotators triage failures in Argilla
  - Classify: retrieval_failure | hallucination | wrong_route | context_gap | other
  - Add corrected expected outputs

Thursday:
  - Export annotated examples to golden dataset
  - Run regression suite with new examples
  - Identify if any failure pattern is net-new vs. known

Friday:
  - ML Engineer proposes fix (prompt change, config change, or new data)
  - Run Promptfoo comparison: current vs. proposed
  - If improved: queue for shadow mode testing next week
```

#### Exit Criteria
- [ ] Feedback collected on ≥10% of production responses
- [ ] Weekly failure triage produces ≥50 annotated examples
- [ ] Golden dataset grows by ≥20% in first month
- [ ] At least 1 prompt improvement deployed via this process
- [ ] Regression suite covers all known failure patterns

---

### Wave 8 — Advanced Optimization

**Duration:** Weeks 20–24
**Team:** 1 ML Engineer, 1 Pipeline Engineer
**Dependencies:** Wave 7 (golden dataset, flywheel running)

#### Deliverables

| # | Deliverable | Tool(s) | Acceptance Criteria |
|---|-------------|---------|---------------------|
| 8.1 | Automated prompt optimization | DSPy | DSPy-optimized prompt outperforms manual by ≥5% on eval set |
| 8.2 | Synthetic test data generation | Curator (Bespokelabs) | 500+ synthetic test cases covering edge cases |
| 8.3 | LLMLingua-2 compression (aggressive mode) | LLMLingua-2 | Additional 20%+ compression beyond BM25, <2% quality loss |
| 8.4 | Late chunking experiment | Jina AI Late Chunking | A/B test vs. current chunking; measure retrieval quality diff |
| 8.5 | Fine-tuned routing classifier | SetFit | Routing accuracy improves to >98% on production distribution |
| 8.6 | Cost optimization pass | Portkey routing | 20%+ cost reduction via smart model routing |

#### Exit Criteria
- [ ] DSPy optimization produces measurably better prompts
- [ ] Synthetic data covers edge cases not in organic production data
- [ ] LLMLingua-2 achieves additional compression with <2% quality loss
- [ ] Late chunking A/B test completed with clear recommendation
- [ ] Cost per query reduced by ≥20%

---

## Resource Summary

| Phase | Duration | Engineers | Key Hires/Dependencies |
|-------|----------|-----------|----------------------|
| Phase 1 | Weeks 1–10 | 3 Engineers (Pipeline, ML, Security) | GPU instance for HHEM |
| Phase 2 | Weeks 8–18 | 3 Engineers (Platform, ML, Backend) | Lakera Guard contract, LaunchDarkly license |
| Phase 3 | Weeks 16–24 | 2 Engineers + 1 Annotator | Argilla deployment, DSPy expertise |

**Total:** 4 engineers (with overlap) + 1 part-time annotator over 24 weeks.

---

## Risk Mitigation by Phase

| Phase | Top Risk | Mitigation |
|-------|----------|------------|
| Phase 1 | Latency budget exceeded with all layers active | Profile each layer independently; async hallucination check if needed |
| Phase 2 | GDPR deletion misses data in caches or logs | Comprehensive data map created in Wave 4; automated verification |
| Phase 3 | Flywheel produces low-quality annotations | Annotator training, inter-annotator agreement checks, ML Engineer review |

---

## Milestone Timeline

```
Week  1  ██░░░░░░░░░░░░░░░░░░░░░░  Wave 1 starts (Retrieval Quality)
Week  3  ████░░░░░░░░░░░░░░░░░░░░  Wave 2 starts (Input Safety)
Week  4  █████░░░░░░░░░░░░░░░░░░░  Wave 1 complete ✓
Week  5  ██████░░░░░░░░░░░░░░░░░░  Wave 3 starts (Output Quality)
Week  6  ███████░░░░░░░░░░░░░░░░░  Wave 2 complete ✓
Week  8  █████████░░░░░░░░░░░░░░░  Wave 4 starts (Compliance)
Week 10  ███████████░░░░░░░░░░░░░  Wave 3 complete ✓ — PHASE 1 DONE
         ███████████░░░░░░░░░░░░░  Wave 5 starts (Deployment)
Week 12  █████████████░░░░░░░░░░░  Wave 4 complete ✓
         █████████████░░░░░░░░░░░  Wave 6 starts (Observability)
Week 14  ███████████████░░░░░░░░░  Wave 5 complete ✓
Week 16  █████████████████░░░░░░░  Wave 7 starts (Flywheel)
Week 18  ███████████████████░░░░░  Wave 6 complete ✓ — PHASE 2 DONE
Week 20  █████████████████████░░░  Wave 7 complete ✓
         █████████████████████░░░  Wave 8 starts (Optimization)
Week 24  █████████████████████████  Wave 8 complete ✓ — PHASE 3 DONE
```
