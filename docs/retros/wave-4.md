# Wave 4 Retrospective — Compliance & Data Governance

**Date:** 2026-02-25
**Duration:** Two sessions (initial implementation + 7-gap fix sprint)
**Team:** 1 Security Engineer, 1 Backend Engineer
**Status:** 5/5 exit criteria PASS (with local fallback adaptations for S3/Langfuse)

---

## Exit Criteria Results

| # | Criterion | Target | Actual | Status |
|---|-----------|--------|--------|--------|
| EC-1 | Metadata on all vectors | user_id, doc_id, tenant_id on every vector | `validate_vector_metadata()` at upsert + upsert_batch; 6 tests | PASS |
| EC-2 | Deletion API end-to-end | User data deleted within 72h, verified | 3-step deletion (vectors/traces/feedback), receipt, verify_deletion(); 14 tests | PASS |
| EC-3 | Immutable audit log | No delete/modify; WORM | Local JSON, no delete_event/update_event methods; 4 tests | PASS |
| EC-4 | Trace export | Daily export, validated | Local trace files with schema validation; 2 tests | PASS |
| EC-5 | Compliance RBAC | 5 roles, correct permissions | 5 roles, 13 permissions, PermissionChecker; 4+8 tests | PASS |

---

## What Worked

**Code path tracing exposed real gaps.** After initial implementation, tracing `DELETE /api/v1/users/{user_id}/data` from HTTP to database revealed 7 concrete gaps: no RBAC enforcement, vectors_deleted always 0, no feedback deletion, sync event loop blocking, null tenant_id on audit events, no partial completion tracking, and hardcoded audit path. Without the trace, these would have shipped as "complete."

**Per-step deletion tracking makes partial failures visible.** Each deletion step (vectors, traces, feedback) is tracked independently with its own `DeletionStepResult` (status/count/error). The overall receipt reports `completed` (all pass), `partial` (some fail), `failed` (all fail). This is much more useful for compliance auditing than a binary pass/fail.

**`asyncio.to_thread()` for sync file I/O.** The trace redaction and feedback deletion methods are synchronous (file system glob + read + write). Wrapping them in `asyncio.to_thread()` keeps the FastAPI event loop responsive during deletion, which matters when multiple deletion requests come in simultaneously.

**Constructor DI pattern scales cleanly.** Adding `FeedbackService` as a dependency to `DeletionService` was a one-line constructor change + one-line wiring in `deps.py`. The pattern established in Wave 1 (constructor DI, wired in `deps.py`) continues to pay dividends.

**Minimal auth that actually blocks.** Rather than stubbing auth or deferring it entirely, we built a minimal but real API key → Role mapping from environment variables. It's ~70 lines, enforces real RBAC permissions, and can be swapped for an external IdP later without changing any endpoint code (the `require_permission()` dependency interface stays the same).

---

## What Surprised Us

**transformers v5.x broke HHEM silently.** Between Wave 3 and Wave 4, `transformers` was upgraded from `<5` to `5.2.0` in the venv, violating the `pyproject.toml` pin. The HHEM model's custom `HHEMv2ForSequenceClassification` class references `all_tied_weights_keys`, which was renamed to `_tied_weights_keys` in v5.x. The 7 HHEM tests that passed in Wave 3 now failed with `AttributeError`. Downgrading to `4.57.6` immediately restored all 7 tests. **Lesson:** Version constraints in `pyproject.toml` don't protect against manual `pip install` or transitive upgrades — consider a lockfile or CI check.

**`VectorStore.delete_by_user()` was returning a hardcoded 0.** The original implementation called `self._client.delete()` (which returns nothing) and returned 0. The fix was to call `count_by_user()` before deletion, but this introduces a TOCTOU race — between count and delete, new vectors could arrive. For compliance purposes this is acceptable (the count is a lower bound), but it's worth noting.

**Deletion endpoint had no tenant_id.** The original `DeletionRequest` schema only had a `reason` field — no `tenant_id`. The audit event was written with `tenant_id=None`, making it impossible to filter audit logs by tenant. This was a spec gap, not a code bug — the tech spec didn't explicitly require `tenant_id` on the deletion request.

---

## What We'd Do Differently

**Trace the code path before declaring "done."** The initial implementation created all the right classes and interfaces but had 7 real gaps when you followed actual execution. A mandatory code path trace (HTTP → service → store → audit) as part of the definition of done would have caught these immediately.

**Pin transformers more aggressively.** The `pyproject.toml` has `transformers>=4.40,<5` but the venv had `5.2.0`. A `pip freeze` check in CI or a requirements lockfile would prevent this class of silent regression.

**Start with auth, not add it later.** RBAC was an afterthought in the initial implementation — added in the fix sprint. Starting with the auth module first would have naturally led to wiring permissions into every new endpoint from the beginning.

---

## Deferred Items

| Item | Signal from Wave 4 | Recommendation |
|------|-------------------|----------------|
| S3 Object Lock for audit logs | Local JSON WORM works but lacks hardware-enforced immutability | **Deploy S3 with Object Lock when AWS is available.** `AuditLogService` already accepts `storage_dir` — add an S3 backend. |
| External identity provider | API key auth is functional but not suitable for production | **Integrate OIDC/OAuth2 when IdP is provisioned.** `require_permission()` dependency is swappable. |
| Automated retention purge | `RetentionChecker` exists but no scheduler | **Wire into cron or Temporal workflow.** `purge_expired(dry_run=False)` is the entry point. |
| Deletion transaction semantics | Steps can partially fail without rollback | **Consider saga pattern if rollback is required.** Current partial-failure tracking is sufficient for compliance (retry the failed steps). |
| Lockfile for venv | transformers version drift broke HHEM | **Generate `requirements.lock` or use `uv.lock`.** |
| Deletion SLA monitoring | 72h SLA configured but not enforced | **Add alerting on `created_at` vs `completed_at` delta.** |

---

## Open Questions Resolved

| # | Question | Resolution |
|---|----------|------------|
| 1 | How to enforce metadata without breaking existing vectors? | **Validation at upsert time.** `validate_vector_metadata()` rejects missing fields. Existing vectors are not retroactively checked (migration is a separate concern). |
| 2 | How to handle partial deletion failures? | **Per-step tracking with 3 statuses.** `completed` (all pass), `partial` (some fail), `failed` (all fail). Each step has independent status/count/error. Audit log always written, even on failure. |
| 3 | Where to store audit logs without S3? | **Local JSON with WORM semantics.** Same pattern as TracingService. Path configurable via `compliance.audit_log_path`. No delete/update methods exposed. |
| 4 | How to gate deletion access? | **API key → Role RBAC.** `require_permission(Permission.DELETE_USER_DATA)` as FastAPI dependency. Only `security_admin` and `compliance_officer` roles can delete. |
| 5 | How to avoid blocking the event loop during deletion? | **`asyncio.to_thread()` for sync I/O.** Trace redaction and feedback deletion run in thread pool. Vector deletion is already async (Qdrant client). |

---

## Downstream Readiness

**Wave 5 (Deployment & Experimentation) can start.** The integration surface is:

- `AuditLogService` — operational for experiment audit trails (A/B test assignments, config changes)
- `TracingService.create_trace()` — pipeline_version tagging supports shadow mode comparison
- `require_permission(Permission.CHANGE_CONFIG)` — gates who can modify pipeline versions
- `pipeline_config.yaml` `experimentation:` section — shadow_mode_enabled, feature_flag_provider
- `ComplianceConfig` — deletion_sla_hours, retention TTLs available for compliance dashboards

**Key constraint for Wave 5:** No external infrastructure yet (Temporal, LaunchDarkly, Promptfoo). Wave 5 will need local fallback patterns similar to Wave 3-4 (local trace files, local audit logs). The existing `pipeline_config.yaml` experimentation section has placeholders.

---

## Honest Stage Assessment (Wave 3 → Wave 4)

| Stage | Wave 3 | Wave 4 | Change |
|-------|--------|--------|--------|
| L1 Injection | REAL | REAL | — |
| PII Detection | REAL | REAL | — |
| Lakera L2 | SKIPPED | SKIPPED | — |
| Routing | REAL | REAL | — |
| Embedding | MOCKED | MOCKED | — |
| Qdrant Retrieval | MOCKED | MOCKED | — |
| Deduplication | REAL | REAL | — |
| Cohere Reranking | MOCKED | MOCKED | — |
| BM25 Compression | REAL | REAL | — |
| Token Budget | REAL | REAL | — |
| LLM Generation | MOCKED | MOCKED | — |
| HHEM Hallucination | REAL | REAL | — |
| Metadata Validation | N/A | **REAL** | **NEW** |
| Deletion API | N/A | **REAL** | **NEW** |
| Audit Logging | N/A | **REAL** | **NEW** |
| RBAC Auth | N/A | **REAL** | **NEW** |
| Feedback API | N/A | **REAL** | **NEW** |
| Retention Check | N/A | **REAL** | **NEW** |
| **Total REAL** | **7/12** | **7/12 + 6 compliance** | **+6 new** |
