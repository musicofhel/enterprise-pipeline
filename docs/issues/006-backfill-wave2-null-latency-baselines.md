# ISSUE-006: Backfill null latency baselines for Lakera Guard, routing, and expansion

**Priority:** P2 — nice-to-have before Wave 3, required before Wave 6
**Status:** Open
**Owner:** Pipeline Engineer
**Created:** 2026-02-24

## Problem

`docs/baselines/wave-2-baseline.json` has null values for:
- `lakera_guard_l2.p50` / `p95` — requires LAKERA_API_KEY
- `query_routing.p50` / `p95` — requires OPENROUTER_API_KEY for embeddings
- `query_expansion.p50` / `p95` — requires OPENROUTER_API_KEY for LLM calls

These are the "before" numbers that Wave 6 dashboards need for latency budgeting.

## When to Capture

The moment API keys are provisioned:
1. Run 100+ safety checks with Lakera Guard enabled, record L2 latency distribution
2. Run 100+ routing calls with real embeddings, record routing latency
3. Run 50+ query expansions, record expansion latency
4. Verify total input processing latency still under 100ms p95 (NFR-02)

## Acceptance Criteria

- [ ] All null latency values populated with real numbers
- [ ] Baseline JSON updated and committed
- [ ] Numbers reviewed — Lakera should be <50ms, routing <100ms, expansion <2000ms
