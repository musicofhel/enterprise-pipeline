# Enterprise AI Pipeline - API Documentation

**Document Version:** 3.2
**Effective Date:** January 5, 2026
**Owner:** Platform Engineering
**Last Reviewed:** January 3, 2026
**Classification:** External - Public

---

## 1. Overview

The Meridian AI Pipeline API provides programmatic access to document ingestion, semantic querying, and feedback collection. All endpoints are RESTful and use JSON for request and response bodies.

**Base URL:** `https://api.meridian-ai.com/api/v1`

**OpenAPI Specification:** Available at `https://api.meridian-ai.com/api/v1/openapi.json`

## 2. Authentication

All API requests must include a valid API key in the `Authorization` header:

```
Authorization: Bearer mp_live_abc123xyz456
```

### API Key Types

| Key Type | Prefix | Permissions | Use Case |
|---|---|---|---|
| **Read-only** | `mp_ro_` | Query, feedback | Client-side applications |
| **Read-write** | `mp_rw_` | Query, ingest, feedback | Backend integrations |
| **Admin** | `mp_admin_` | All operations including delete | Administrative tools |

API keys are generated in the Meridian Dashboard under **Settings > API Keys**. Each key is scoped to a single project and cannot access resources in other projects.

### Key Rotation
- API keys can be rotated at any time from the Dashboard
- Rotated keys remain valid for a **24-hour grace period** to allow migration
- A maximum of **5 active keys** per project are allowed

## 3. Rate Limiting

Rate limits are enforced per API key on a **sliding window** basis:

| Plan | Rate Limit | Burst Allowance |
|---|---|---|
| **Starter** | 100 requests/minute | 20 additional requests |
| **Professional** | 1,000 requests/minute | 200 additional requests |
| **Enterprise** | 10,000 requests/minute | 2,000 additional requests |

### Rate Limit Headers

Every API response includes rate limit information:

| Header | Description |
|---|---|
| `X-RateLimit-Limit` | Maximum requests allowed per window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |
| `X-RateLimit-RetryAfter` | Seconds to wait before retrying (only on 429) |

When a rate limit is exceeded, the API returns a `429 Too Many Requests` response. Clients should implement exponential backoff with jitter, starting at 1 second.

## 4. Endpoints

### 4.1 Query Endpoint

Perform a semantic search against your ingested document corpus.

```
POST /api/v1/query
```

**Request Body:**

```json
{
  "query": "What is the data retention policy for customer records?",
  "top_k": 5,
  "filters": {
    "document_type": "policy",
    "created_after": "2025-01-01"
  },
  "include_sources": true,
  "model": "meridian-v2"
}
```

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | Yes | - | Natural language query (max 2,000 characters) |
| `top_k` | integer | No | 5 | Number of source chunks to retrieve (1-20) |
| `filters` | object | No | {} | Metadata filters to narrow results |
| `include_sources` | boolean | No | true | Include source document references |
| `model` | string | No | `meridian-v2` | Model version for generation |

**Response:**

```json
{
  "answer": "Customer records are retained for 7 years from the end of the contract...",
  "confidence": 0.94,
  "sources": [
    {
      "document_id": "doc_abc123",
      "chunk_id": "chunk_456",
      "title": "Data Security and Privacy Policy",
      "relevance_score": 0.97,
      "text_snippet": "Customer data (archived): 7 years from contract end..."
    }
  ],
  "usage": {
    "prompt_tokens": 1250,
    "completion_tokens": 180,
    "total_tokens": 1430
  },
  "request_id": "req_789xyz"
}
```

### 4.2 Document Ingestion

Upload and index documents into your project corpus.

```
POST /api/v1/ingest
```

**Request Body (JSON):**

```json
{
  "documents": [
    {
      "title": "Q4 2025 Financial Report",
      "content": "Revenue for Q4 2025 reached $12.3M...",
      "metadata": {
        "department": "finance",
        "document_type": "report",
        "author": "Jane Smith"
      }
    }
  ],
  "chunking_strategy": "semantic",
  "chunk_size": 512
}
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `documents` | array | Yes | Array of document objects (max 100 per request) |
| `documents[].title` | string | Yes | Document title (max 500 characters) |
| `documents[].content` | string | Yes | Document content (max 100,000 characters) |
| `documents[].metadata` | object | No | Key-value metadata for filtering |
| `chunking_strategy` | string | No | `semantic` (default), `fixed`, or `paragraph` |
| `chunk_size` | integer | No | Target chunk size in tokens (128-2048, default 512) |

**Supported file uploads** via `multipart/form-data`:
- PDF (`.pdf`) - up to 50 MB
- Markdown (`.md`) - up to 10 MB
- Plain text (`.txt`) - up to 10 MB
- Microsoft Word (`.docx`) - up to 25 MB
- HTML (`.html`) - up to 10 MB

**Response:**

```json
{
  "ingestion_id": "ing_abc123",
  "status": "processing",
  "documents_accepted": 1,
  "documents_rejected": 0,
  "estimated_completion": "2026-01-15T10:05:00Z"
}
```

Ingestion status can be polled at `GET /api/v1/ingest/{ingestion_id}`.

### 4.3 Document Deletion

Delete documents from the corpus by ID or filter.

```
DELETE /api/v1/documents/{document_id}
```

**Response:**

```json
{
  "document_id": "doc_abc123",
  "status": "deleted",
  "chunks_removed": 24
}
```

**Bulk deletion by filter:**

```
POST /api/v1/documents/delete
```

```json
{
  "filters": {
    "document_type": "draft",
    "created_before": "2025-01-01"
  }
}
```

Bulk deletions are processed asynchronously. A job ID is returned for status tracking.

### 4.4 Feedback

Submit feedback on query responses to improve future results.

```
POST /api/v1/feedback
```

```json
{
  "request_id": "req_789xyz",
  "rating": "positive",
  "comment": "Accurate and well-sourced answer"
}
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `request_id` | string | Yes | The request_id from the original query response |
| `rating` | string | Yes | `positive`, `negative`, or `neutral` |
| `comment` | string | No | Free-text feedback (max 1,000 characters) |

### 4.5 List Documents

Retrieve a paginated list of ingested documents.

```
GET /api/v1/documents?page=1&per_page=20&sort=created_at&order=desc
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Results per page (max 100) |
| `sort` | string | `created_at` | Sort field: `created_at`, `title`, `updated_at` |
| `order` | string | `desc` | Sort order: `asc` or `desc` |
| `filter[document_type]` | string | - | Filter by document type |

## 5. Error Codes

| HTTP Status | Error Code | Description |
|---|---|---|
| 400 | `invalid_request` | Malformed request body or missing required fields |
| 401 | `unauthorized` | Invalid or missing API key |
| 403 | `forbidden` | API key lacks required permissions |
| 404 | `not_found` | Resource does not exist |
| 409 | `conflict` | Document with the same ID already exists |
| 413 | `payload_too_large` | Request body exceeds maximum size |
| 422 | `unprocessable_entity` | Request is well-formed but contains invalid data |
| 429 | `rate_limit_exceeded` | Rate limit exceeded; retry after `X-RateLimit-RetryAfter` seconds |
| 500 | `internal_error` | Unexpected server error; contact support with `request_id` |
| 503 | `service_unavailable` | Temporary service disruption; retry with backoff |

**Error Response Format:**

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit of 1000 requests per minute exceeded",
    "request_id": "req_error_123",
    "retry_after": 45
  }
}
```

## 6. Webhooks

Configure webhooks in the Dashboard to receive real-time notifications for:

- `ingestion.completed` - Document ingestion finished
- `ingestion.failed` - Document ingestion failed
- `document.deleted` - Document removed from corpus
- `usage.threshold` - Query usage reached configured threshold (e.g., 80% of plan limit)

Webhook payloads are signed with HMAC-SHA256 using your webhook secret. Verify the `X-Meridian-Signature` header before processing.

## 7. SDKs and Libraries

Official SDKs are available for:

- **Python:** `pip install meridian-ai` (v2.1.0)
- **Node.js:** `npm install @meridian-ai/sdk` (v2.0.3)
- **Go:** `go get github.com/meridian-ai/go-sdk` (v1.4.0)

Community-maintained SDKs exist for Ruby, Java, and Rust. See the [SDK Directory](https://docs.meridian-ai.com/sdks) for details.

---

*API versioning follows semantic versioning. The current stable version is v1. Breaking changes will be introduced in v2 with a minimum 12-month migration window.*
