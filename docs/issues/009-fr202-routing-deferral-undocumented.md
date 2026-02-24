# ISSUE-009: FR-202 routing deferral was undocumented (now fixed)

**Priority:** P3 — process gap, code already fixed
**Status:** Open
**Owner:** Pipeline Engineer
**Created:** 2026-02-24
**Found in:** Wave 2 verification follow-up

## Problem

FR-202 in the PRD (`docs/02-prd.md`) states:

> FR-202: System SHALL route classified queries to appropriate retrieval strategies via RunnableBranch (P0)

This is a P0 requirement. However:

1. FR-202 is **not listed** in Wave 2 deliverables in `docs/03-implementation-plan.md`. Wave 2 deliverable 2.4 only covers "Semantic query routing" (classification, FR-201), not route-dependent dispatch (FR-202).
2. The deferral was **not documented** in the Wave 2 completion checklist, retrospective, or any issue file.
3. The gap was caught during verification follow-up. Route branching has now been implemented (commit `0fe2b46`).

## Current State

The orchestrator now branches on route result:
- `rag_knowledge_base` → full RAG pipeline
- `direct_llm` → skip retrieval, go straight to generation
- `sql_structured_data` → `NotImplementedError` (Wave 3+)
- `api_lookup` → `NotImplementedError` (Wave 3+)
- `escalate_human` → return handoff response without LLM call

## Acceptance Criteria

- [ ] Add a note to `docs/retros/wave-2.md` documenting that FR-202 was a spec gap caught in verification
- [ ] Review `docs/03-implementation-plan.md` — confirm each FR requirement maps clearly to a wave deliverable
- [ ] If any other P0 FRs are missing from wave deliverables, create tracking issues

## Affects

- Process improvement. No code changes needed (already fixed).
