# ISSUE-002: Backfill null baselines on first live retrieval

**Priority:** P1 — Wave 2 kickoff task
**Status:** Open
**Owner:** Pipeline Engineer
**Created:** 2026-02-24

## Problem

`docs/baselines/wave-1-baseline.json` has null values for:
- `retrieval_cosine_sim.p50` / `p95`
- `end_to_end_latency_ms.p50` / `p95`

These are the "before" numbers Wave 6 dashboards need. Without them, we can't measure whether future waves actually improve anything.

## When to Capture

The moment retrieval is callable end-to-end in staging:
1. Ingest docs/ into Qdrant
2. Run 50+ queries from golden_dataset
3. Record cosine sim distribution from Qdrant search results
4. Record end-to-end latency (embed + search + rerank + compress + generate)

## Acceptance Criteria

- [ ] `retrieval_cosine_sim.p50` and `p95` populated with real numbers
- [ ] `end_to_end_latency_ms.p50` and `p95` populated with real numbers
- [ ] Baseline JSON updated and committed
- [ ] Numbers reviewed — do they look reasonable? p50 cosine sim should be >0.5 for a functioning retrieval system
