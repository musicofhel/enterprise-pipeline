# ISSUE-013: Wire OutputSchemaEnforcer Into Orchestrator Pipeline

**Priority:** P2 — not blocking, but should be done before Wave 4
**Status:** Open
**Wave:** 3 follow-up
**Created:** 2026-02-24

## Problem

`OutputSchemaEnforcer` is built and tested (10 tests passing) but not yet called in the orchestrator pipeline. The enforcer validates LLM output structure against per-route JSON schemas, but the orchestrator currently passes LLM output directly to the response without schema enforcement.

## Current State

- `src/pipeline/output_schema.py` — fully functional, per-route schemas (RAG, direct_llm)
- `tests/unit/test_output_schema.py` — 10 tests passing
- `src/pipeline/orchestrator.py` — does NOT call `OutputSchemaEnforcer.enforce()`

## What's Needed

1. Add `OutputSchemaEnforcer` as a constructor dependency on `PipelineOrchestrator`
2. After LLM generation, call `enforcer.enforce(llm_result["answer"], route=route)`
3. Handle invalid schema: either wrap or return structured error
4. Wire in `src/api/deps.py`
5. Add Langfuse span for schema enforcement step

## Design Decision

Should schema enforcement run BEFORE or AFTER hallucination checking?

- **Before:** Ensures HHEM receives well-structured input. But HHEM scores raw text, not JSON.
- **After:** Schema enforcement on the final answer, after all quality checks.
- **Recommendation:** After. HHEM checks groundedness of the answer text. Schema enforcement validates the output format for the API response. They're independent concerns.

## Acceptance Criteria

- [ ] `OutputSchemaEnforcer` wired into orchestrator after generation
- [ ] Invalid schema outputs handled gracefully (wrapped or error response)
- [ ] Langfuse span records schema enforcement result
- [ ] Integration test verifies schema enforcement in E2E pipeline
