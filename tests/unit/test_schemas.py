import pytest
from pydantic import ValidationError

from src.models.schemas import QueryMetadata, QueryRequest, QueryResponse, SourceInfo


def test_query_request_valid():
    req = QueryRequest(
        query="What is the pipeline?",
        user_id="user-1",
        tenant_id="tenant-1",
    )
    assert req.query == "What is the pipeline?"
    assert req.options.max_tokens == 4000


def test_query_request_max_length():
    with pytest.raises(ValidationError):
        QueryRequest(
            query="x" * 10001,
            user_id="user-1",
            tenant_id="tenant-1",
        )


def test_query_response():
    resp = QueryResponse(
        answer="Test answer",
        trace_id="trace-123",
        sources=[
            SourceInfo(
                doc_id="doc-1",
                chunk_id="chunk-1",
                text_snippet="snippet",
                relevance_score=0.9,
            )
        ],
        metadata=QueryMetadata(
            route_used="rag_knowledge_base",
            model="anthropic/claude-sonnet-4-5",
            latency_ms=1000,
            tokens_used=500,
        ),
    )
    assert resp.answer == "Test answer"
    assert len(resp.sources) == 1
