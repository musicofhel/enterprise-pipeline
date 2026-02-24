# ISSUE-001: Validate EC-4 against Cohere Rerank in staging

**Priority:** P0 — blocks Wave 3
**Status:** Open
**Owner:** Pipeline Engineer
**Created:** 2026-02-24

## Problem

Wave 1 EC-4 ("Reranking improves MRR@10 by >=15%") was validated with a simulated model, not the real Cohere Rerank API. The 110% simulated improvement is meaningless — it proves the code reorders results correctly, not that Cohere actually improves retrieval quality on our data.

Wave 3 builds hallucination checks (HHEM) on top of reranked results. If reranking is broken or underperforms, faithfulness scores will be calculated against poorly-ordered context, making HHEM metrics unreliable.

## Acceptance Criteria

- [ ] Run Cohere Rerank API against golden_dataset queries with real embeddings in Qdrant
- [ ] Measure MRR@10 before reranking (cosine sim only) and after (Cohere rerank-v3.5)
- [ ] Improvement must be >=15% to close EC-4 for real
- [ ] If <15%, investigate: wrong embedding model? wrong top_k? need query expansion first?
- [ ] Update `docs/baselines/wave-1-baseline.json` with real MRR numbers

## Blocked By

- Qdrant running with ingested documents (at least the project's own docs/)
- Valid COHERE_API_KEY in .env

## Blocks

- Wave 3 output quality work — do NOT start HHEM integration until this is closed

## Validation Plan (added Wave 3 pre-work)

Integration test written: `tests/integration/test_cohere_rerank_validation.py`

- Uses 10 realistic retrieval chunks (HR policy, financial data, facilities) with a remote work query
- Measures MRR@10 before/after Cohere rerank-v3.5
- Asserts >=15% MRR improvement
- Also asserts top-3 reranked results overlap with ground-truth relevant chunks

Run with: `COHERE_API_KEY=xxx pytest tests/integration/test_cohere_rerank_validation.py -m integration -v`
