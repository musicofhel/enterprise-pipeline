# ISSUE-004: Validate query routing accuracy with real OpenAI embeddings

**Priority:** P1 — before Wave 3 goes live
**Status:** Open
**Owner:** Pipeline Engineer
**Created:** 2026-02-24

## Problem

Wave 2 EC-3 (">95% query routing accuracy on 500-query test set") was validated with deterministic embeddings that assign orthogonal vectors per route. This proves the algorithm scores correctly, not that real OpenAI embeddings produce enough separation between route utterances to classify production queries.

The routes.yaml has 12-13 utterances per route. With real embeddings, utterances like "What is the refund policy?" (rag_knowledge_base) and "How many refunds last month?" (sql_structured_data) may have high cosine similarity, causing misroutes.

## Acceptance Criteria

- [ ] Run QueryRouter with real OpenAI text-embedding-3-small against 100+ diverse queries with known correct routes
- [ ] Accuracy must exceed 95% on the test set
- [ ] If <95%, investigate: add more utterances? adjust confidence_threshold? use a different embedding model?
- [ ] Update `docs/baselines/wave-2-baseline.json` with real routing accuracy

## Blocked By

- Valid OPENAI_API_KEY in .env

## Blocks

- Wave 3 route-dependent pipeline behavior
