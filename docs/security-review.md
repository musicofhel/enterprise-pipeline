# Security Review — Phase 13

**Date:** 2026-02-26
**Reviewer:** Automated security audit
**Scope:** Secrets, dependencies, RBAC, input validation

---

## 1. Secrets Audit

### Scan Results

Scanned all `*.py`, `*.yaml`, `*.toml`, `*.json` files under `src/`, `scripts/`, `monitoring/`, and `pipeline_config.yaml`.

| File | Line | Match | Classification |
|------|------|-------|---------------|
| `src/api/auth.py` | 22 | `# Example env value: "sk-admin-1=security_admin;..."` | **OK** — comment with example placeholder |
| `src/api/v1/health.py` | 87 | `api_key=settings.qdrant_api_key.get_secret_value()` | **OK** — Pydantic `SecretStr` env reference |
| `src/api/deps.py` | 82 | `api_key=settings.qdrant_api_key.get_secret_value()` | **OK** — Pydantic `SecretStr` env reference |
| `src/api/deps.py` | 129 | `api_key=settings.openrouter_api_key.get_secret_value()` | **OK** — Pydantic `SecretStr` env reference |
| `src/api/deps.py` | 134 | `api_key=settings.qdrant_api_key.get_secret_value()` | **OK** — Pydantic `SecretStr` env reference |
| `src/api/deps.py` | 136 | `api_key=settings.cohere_api_key.get_secret_value()` | **OK** — Pydantic `SecretStr` env reference |
| `src/api/deps.py` | 166 | `LakeraGuardClient(api_key=lakera_key)` | **OK** — variable from `SecretStr` |
| `src/observability/daily_eval.py` | 189 | `api_key=api_key` | **OK** — variable from `os.environ.get()` |
| `scripts/validate_environment.py` | 123 | `AsyncOpenAI(api_key=key, ...)` | **OK** — variable from env |
| `tests/conftest.py` | 51-56 | `"sk-or-test"`, `"sk-test"`, etc. | **OK** — test fixtures (not real keys) |
| `tests/unit/test_auth.py` | 58-108 | `"sk-admin"`, `"sk-worker"`, etc. | **OK** — test fixtures (not real keys) |

**Result: CLEAN.** No hardcoded secrets found in source code. All API keys are loaded via `pydantic.SecretStr` from environment variables or `.env` file.

### Docker Compose Secrets

| File | Line | Issue | Severity |
|------|------|-------|----------|
| `docker-compose.yaml` | 19 | `POSTGRES_PASSWORD: langfuse` | **LOW** — dev-only default, acceptable for local Langfuse DB |
| `docker-compose.yaml` | 29 | `NEXTAUTH_SECRET: mysecret` | **LOW** — dev-only placeholder. Must be randomized for production |
| `docker-compose.yaml` | 32 | `SALT: mysalt` | **LOW** — dev-only placeholder. Must be randomized for production |

These are acceptable for local development but the `docker-compose.yaml` should NOT be used directly in production. The `.env.production.example` correctly uses placeholder values.

### .gitignore Verification

| Pattern | Present? | Notes |
|---------|----------|-------|
| `.env` | Yes (line 22) | Covers `.env` |
| `.env.local` | Yes (line 23) | |
| `.env.production` | Yes (line 24) | |
| `*.key` | **Added** | Was missing; added in this review |
| `audit_logs/` | Yes (line 56) | |
| `traces/` | Yes (line 53) | |
| `annotations/` | **Added** | Was missing; added in this review (may contain PII) |
| `deletions/` | Yes (line 57) | |
| `feedback/` | Yes (line 58) | |
| `eval_reports/` | **Added** | Was missing; added in this review (may contain trace data) |

**Fix applied:** Added `annotations/`, `*.key`, and `eval_reports/` to `.gitignore`.

---

## 2. Dependency Vulnerability Audit

**Tool:** `pip-audit 2.10.0`

### Findings

| Package | Version | CVE | Severity | Fix Version | Applies to Us? |
|---------|---------|-----|----------|-------------|----------------|
| diskcache | 5.6.3 | CVE-2025-69872 | MEDIUM | None available | **No** — `diskcache` is not imported or used anywhere in `src/`. It is a transitive dependency (likely via Ragas or DeepEval). The vulnerability requires write access to the cache directory, which is not exposed to untrusted users. |
| langchain-core | 0.3.83 | CVE-2026-26013 | LOW | 1.2.11 | **No** — SSRF in `ChatOpenAI.get_num_tokens_from_messages()` with `image_url`. We use `langchain_openai.ChatOpenAI` only in `daily_eval.py` for Ragas eval with text-only messages. No image URLs are ever passed. |
| pip | 25.0.1 | CVE-2025-8869 | LOW | 25.3 | **No** — symlink extraction attack during `pip install` of malicious sdist. We only install from PyPI and trusted sources. Python 3.11+ has PEP 706 protections. |
| pip | 25.0.1 | CVE-2026-1703 | MEDIUM | 26.0 | **No** — path traversal in wheel extraction. Same mitigation: only trusted sources. |

### Assessment

**No actionable vulnerabilities.** All 4 CVEs are either in transitive dependencies we don't directly use, or in scenarios that don't apply to our usage patterns. However, upgrading pip to 26.0 when convenient is recommended as good hygiene.

**Recommendation:** When langchain-core publishes a compatible 1.2.x release that works with our Ragas version, upgrade. Currently pinned at 0.3.x by Ragas compatibility.

---

## 3. RBAC Matrix Verification

### Roles and Permissions (from `src/models/rbac.py`)

5 roles defined: `pipeline_worker`, `ml_engineer`, `platform_engineer`, `security_admin`, `compliance_officer`

13 permissions defined: `read_traces`, `write_traces`, `read_audit`, `delete_user_data`, `change_config`, `manage_models`, `read_vectors`, `write_vectors`, `read_feedback`, `write_feedback`, `run_pipeline`, `view_experiments`, `manage_experiments`

### Auth Chain

Authentication is in `src/api/auth.py`:
1. `_extract_api_key(request)` — reads from `Authorization: Bearer <key>` or `X-API-Key` header
2. `_resolve_role(api_key)` — looks up key in `API_KEY_ROLES` dict (loaded from env var at import time). Returns 401 if missing/unknown.
3. `require_permission(permission)` — FastAPI dependency factory. Calls `_extract_api_key` -> `_resolve_role` -> `PermissionChecker.has_permission()`. Returns 403 if role lacks permission.

### Per-Endpoint Verification

| Endpoint | Method | Required Permission | Enforced via | Verified? |
|----------|--------|-------------------|-------------|-----------|
| `/api/v1/query` | POST | **NONE** | No auth dependency | **FINDING** |
| `/api/v1/ingest` | POST | **NONE** | No auth dependency | **FINDING** |
| `/api/v1/users/{user_id}/data` | DELETE | `delete_user_data` | `dependencies=[Depends(require_permission(Permission.DELETE_USER_DATA))]` | Yes |
| `/api/v1/deletions/{deletion_id}` | GET | `delete_user_data` | `dependencies=[Depends(require_permission(Permission.DELETE_USER_DATA))]` | Yes |
| `/api/v1/feedback` | POST | `write_feedback` | `dependencies=[Depends(require_permission(Permission.WRITE_FEEDBACK))]` | Yes |
| `/api/v1/feedback/stats` | POST | **NONE** | No auth dependency | **FINDING** |
| `/health` | GET | None (intentional) | No auth — health check | OK |
| `/metrics` | GET | None (intentional) | No auth — Prometheus scrape | OK |
| `/ready` | GET | None (intentional) | No auth — readiness probe | OK |

### Code Evidence

**DELETE `/api/v1/users/{user_id}/data`** (`src/api/v1/deletion.py:25-29`):
```python
@router.delete(
    "/users/{user_id}/data",
    response_model=DeletionResponse,
    status_code=202,
    dependencies=[Depends(require_permission(Permission.DELETE_USER_DATA))],
)
```
Only `security_admin` and `compliance_officer` roles have `DELETE_USER_DATA` permission.

**GET `/api/v1/deletions/{deletion_id}`** (`src/api/v1/deletion.py:49-52`):
```python
@router.get(
    "/deletions/{deletion_id}",
    response_model=DeletionStatusResponse,
    dependencies=[Depends(require_permission(Permission.DELETE_USER_DATA))],
)
```

**POST `/api/v1/feedback`** (`src/api/v1/feedback.py:18-21`):
```python
@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    dependencies=[Depends(require_permission(Permission.WRITE_FEEDBACK))],
)
```
`pipeline_worker`, `ml_engineer` roles have `WRITE_FEEDBACK`.

**POST `/api/v1/feedback/stats`** (`src/api/v1/feedback.py:38-41`):
```python
@router.post(
    "/feedback/stats",
    response_model=FeedbackStatsResponse,
)
```
**No auth dependency.** This should require `READ_FEEDBACK` permission.

**POST `/api/v1/query`** (`src/api/v1/query.py:16`):
```python
@router.post("/query", response_model=QueryResponse)
```
**No auth dependency.** This should require `RUN_PIPELINE` permission.

**POST `/api/v1/ingest`** (`src/api/v1/ingest.py:18`):
```python
@router.post("/ingest", response_model=IngestResponse)
```
**No auth dependency.** This should require `WRITE_VECTORS` permission.

### RBAC Findings Summary

| Finding | Severity | Endpoint | Recommendation |
|---------|----------|----------|----------------|
| Missing auth on `/api/v1/query` | **HIGH** | POST | Add `Depends(require_permission(Permission.RUN_PIPELINE))` |
| Missing auth on `/api/v1/ingest` | **HIGH** | POST | Add `Depends(require_permission(Permission.WRITE_VECTORS))` |
| Missing auth on `/api/v1/feedback/stats` | **MEDIUM** | POST | Add `Depends(require_permission(Permission.READ_FEEDBACK))` |

---

## 4. Input Validation Audit

### 4.1 Maximum Query Length

**Enforced: YES** — `QueryRequest.query` field in `src/models/schemas.py:16`:
```python
query: str = Field(..., max_length=10000)
```
Limit: 10,000 characters. Enforced by Pydantic validation before the handler runs.

### 4.2 user_id Validation

**Partially enforced:**
- `QueryRequest.user_id: str` — required (non-optional), but no format/length/character validation
- `DeletionRequest` takes `user_id` from URL path parameter — no regex constraint
- `FeedbackRequest.user_id: str` — required, no format validation
- `IngestRequest.user_id: str = Form(...)` — required via Form, no format validation

**Risk:** No protection against excessively long user_ids, path traversal in user_id (used in file paths for trace storage), or special characters. The trace redaction code in `deletion_service.py` uses user_id in file operations.

### 4.3 tenant_id Validation

**Partially enforced:**
- `QueryRequest.tenant_id: str` — required, no format validation
- `DeletionRequest.tenant_id: str = Field(..., min_length=1)` — has minimum length of 1

Inconsistent: DeletionRequest enforces `min_length=1`, but QueryRequest does not.

### 4.4 Request Body Size Limit

**Default uvicorn behavior:** No explicit body size limit configured. Uvicorn does not enforce a default body size limit. FastAPI/Starlette will read the entire body into memory.

For the `/ingest` endpoint, uploaded files are read fully into memory (`content = await file.read()`) with no size guard.

### 4.5 API Rate Limiting

**Not implemented.** There is no rate limiting middleware, per-API-key throttling, or request quotas anywhere in the codebase.

### 4.6 Additional Validation Notes

- `DeletionRequest.reason` has `min_length=1, max_length=1000` — well validated
- `FeedbackRequest.rating` is an unvalidated `str` — should be constrained to `"positive" | "negative"`
- `QueryOptions.max_tokens` and `temperature` have no bounds — a caller could set `max_tokens=1000000`
- `/metrics` endpoint is unauthenticated — exposes Prometheus metrics publicly

---

## 5. Recommendations (Prioritized)

### P0 — Critical (fix before production)

1. **Add auth to `/api/v1/query`** — The core pipeline endpoint is completely unauthenticated. Anyone who can reach the API can execute queries consuming LLM tokens.
   - File: `src/api/v1/query.py:16`
   - Fix: `dependencies=[Depends(require_permission(Permission.RUN_PIPELINE))]`

2. **Add auth to `/api/v1/ingest`** — Document ingestion is unauthenticated. Anyone can upload documents to the vector store.
   - File: `src/api/v1/ingest.py:18`
   - Fix: `dependencies=[Depends(require_permission(Permission.WRITE_VECTORS))]`

3. **Add file upload size limit** — The ingest endpoint reads entire files into memory with no size guard.
   - File: `src/api/v1/ingest.py:31`
   - Fix: Check `file.size` or read with a limit (e.g., 50MB max)

### P1 — High (fix before GA)

4. **Add auth to `/api/v1/feedback/stats`** — Feedback statistics are accessible without authentication.
   - File: `src/api/v1/feedback.py:38`
   - Fix: `dependencies=[Depends(require_permission(Permission.READ_FEEDBACK))]`

5. **Add rate limiting** — No per-key or global rate limiting exists. A single API key can exhaust LLM budget.
   - Fix: Add `slowapi` or custom middleware with per-API-key quotas

6. **Validate user_id format** — user_id is used in file path construction (trace storage). No sanitization against path traversal.
   - Fix: Add regex validator `^[a-zA-Z0-9_-]+$` and `max_length=128` to all user_id fields

7. **Validate FeedbackRequest.rating** — Currently accepts any string.
   - Fix: Use `Literal["positive", "negative"]` or an enum

### P2 — Medium (backlog)

8. **Bound QueryOptions.max_tokens** — No upper limit on requested tokens.
   - Fix: `max_tokens: int = Field(4000, ge=1, le=32000)`

9. **Consistent tenant_id validation** — `DeletionRequest` has `min_length=1` but `QueryRequest` does not.
   - Fix: Add `min_length=1` to all tenant_id fields

10. **Randomize docker-compose.yaml dev secrets** — `NEXTAUTH_SECRET: mysecret` and `SALT: mysalt` are weak. Add comments warning against production use, or use env var references.

11. **Authenticate `/metrics` endpoint** — Prometheus metrics are publicly accessible. Consider adding basic auth or network-level restriction.

12. **Upgrade pip to 26.x** — Two low-severity CVEs affect pip 25.0.1. Not exploitable in our setup but good hygiene.

### Completed in This Review

- Added `annotations/`, `*.key`, `eval_reports/` to `.gitignore`

---

## 6. Test Verification

```
$ .venv/bin/python -m pytest tests/unit/ -x -q
294 passed in 6.51s
```

All unit tests pass. No regressions from .gitignore changes.
