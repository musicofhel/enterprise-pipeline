# ISSUE-012: Generate HHEM 500-Query Eval Set for EC-1

**Priority:** P1 — blocks full EC-1 validation
**Status:** Open — needs OPENAI_API_KEY
**Wave:** 3 (Output Quality & Tracing)
**Created:** 2026-02-24

## Problem

Wave 3 EC-1 requires HHEM faithfulness ≥0.92 on an eval set of 500 queries. The HHEM model is operational and runs real inference, but we don't have a 500-query eval set to measure against.

The eval set requires:
1. 500 diverse queries across multiple topics
2. Retrieved context chunks for each query (from Qdrant or synthetic)
3. LLM-generated answers for each query given the context
4. HHEM scoring of each (context, answer) pair

Steps 2-3 require OPENAI_API_KEY (for embeddings and LLM generation).

## What's Working

- HHEM loads from HuggingFace and runs on CPU
- 7 unit tests pass with real model inference
- Grounded answers score >0.85, hallucinated answers score <0.30
- Aggregation methods: max (default), mean, min all functional
- Thresholds: pass=0.85, warn=0.70 configurable via pipeline_config.yaml

## What's Needed

1. Script to generate 500 diverse queries (can be done without API key)
2. For each query, retrieve context from Qdrant (needs Qdrant + OPENAI_API_KEY)
3. For each query + context, generate an LLM answer (needs OPENAI_API_KEY)
4. Score all 500 (context, answer) pairs with HHEM
5. Measure: mean score, % above 0.92, distribution

## Alternative: Synthetic Eval Set

If API keys remain unavailable:
- Build 500 synthetic (context, answer) pairs manually or from existing documents
- Ensure distribution: 80% grounded, 10% partial, 10% hallucinated
- Score with HHEM and report distribution

## Acceptance Criteria

- [ ] 500-query eval set generated and saved to `golden_dataset/hhem_eval_set.jsonl`
- [ ] HHEM mean faithfulness ≥0.92 across the set
- [ ] CI test runs the eval set with `@pytest.mark.eval` marker
- [ ] Results logged in `docs/baselines/wave-3-baseline.json`
