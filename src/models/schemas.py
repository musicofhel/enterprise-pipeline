from __future__ import annotations

from pydantic import BaseModel, Field


class QueryOptions(BaseModel):
    max_tokens: int = 4000
    temperature: float = 0.1
    include_sources: bool = True
    force_route: str | None = None


class QueryRequest(BaseModel):
    query: str = Field(..., max_length=10000)
    user_id: str
    session_id: str | None = None
    tenant_id: str
    options: QueryOptions = Field(default_factory=QueryOptions)


class SourceInfo(BaseModel):
    doc_id: str
    chunk_id: str
    text_snippet: str
    relevance_score: float
    source_url: str | None = None


class QueryMetadata(BaseModel):
    route_used: str
    faithfulness_score: float | None = None
    model: str
    latency_ms: int
    tokens_used: int


class QueryResponse(BaseModel):
    answer: str | None
    trace_id: str
    sources: list[SourceInfo] = Field(default_factory=list)
    metadata: QueryMetadata
    fallback: bool = False
    message: str | None = None


class IngestRequest(BaseModel):
    user_id: str
    tenant_id: str
    doc_type: str = "markdown"
    source_url: str | None = None
    access_level: str = "internal"


class IngestResponse(BaseModel):
    doc_id: str
    chunks_created: int
    status: str = "success"


class FeedbackRequest(BaseModel):
    trace_id: str
    user_id: str
    rating: str  # "positive" | "negative"
    correction: str | None = None
    comment: str | None = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    status: str = "recorded"


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadyResponse(BaseModel):
    status: str
    qdrant: str
    langfuse: str


class ErrorResponse(BaseModel):
    error: str
    reason: str | None = None
    trace_id: str | None = None
