# ISSUE-004: Validate query routing accuracy with real embeddings (local sentence-transformers)

**Priority:** P1 — before Wave 3 goes live
**Status:** Partially resolved — 4/5 accuracy on 5-query test, threshold lowered to 0.15
**Owner:** Pipeline Engineer
**Created:** 2026-02-24

## Problem

Wave 2 EC-3 (">95% query routing accuracy on 500-query test set") was validated with deterministic embeddings that assign orthogonal vectors per route. This proves the algorithm scores correctly, not that real embeddings produce enough separation between route utterances to classify production queries.

## Resolution (OpenRouter Migration)

Routing embeddings switched from OpenAI `text-embedding-3-small` (API-based) to local `all-MiniLM-L6-v2` (sentence-transformers, 384-dim, CPU). No API key needed.

### Key Finding: Confidence Threshold Adjustment

`all-MiniLM-L6-v2` produces much lower average cosine similarities (~0.05-0.28) than larger API models because it averages across all 12-13 utterances per route. The original threshold of 0.7 caused ALL queries to fall back to default.

**Threshold adjusted: 0.7 → 0.15** in both `pipeline_config.yaml` and `RoutingConfig` default.

### 5-Query Accuracy Test Results

| Query | Expected Route | Actual Route | Confidence | Status |
|-------|---------------|-------------|------------|--------|
| "What is the company refund policy?" | rag_knowledge_base | escalate_human | 0.21 | FAIL |
| "Show me total revenue by quarter for 2025" | sql_structured_data | sql_structured_data | 0.28 | PASS |
| "Write me a poem about databases" | direct_llm | direct_llm | 0.18 | PASS |
| "Check the status of order #12345" | api_lookup | api_lookup | 0.17 | PASS |
| "I want to speak with a human manager" | escalate_human | escalate_human | 0.27 | PASS |

**Accuracy: 4/5 (80%)** at threshold=0.15.

### Analysis of the 1 Failure

"What is the company refund policy?" routes to `escalate_human` (0.2119) instead of `rag_knowledge_base` (0.1585). The word "refund" is semantically closer to complaint/legal language in the `escalate_human` route ("complaint about your service", "contract terms", "enterprise agreement"). The `rag_knowledge_base` utterances focus on technical docs, architecture, and processes — none mention refunds specifically.

**Fix:** Add refund/billing-related utterances to `rag_knowledge_base` in routes.yaml. This is a routes tuning issue, not a model issue.

## Remaining Acceptance Criteria

- [x] Run QueryRouter with real local all-MiniLM-L6-v2 embeddings against test queries
- [ ] Accuracy must exceed 95% on 100+ query test set (currently 80% on 5 queries)
- [ ] Tune routes.yaml utterances to improve separation
- [x] Update `confidence_threshold` for local model (0.7 → 0.15)

## Blocks

- Wave 3 route-dependent pipeline behavior
