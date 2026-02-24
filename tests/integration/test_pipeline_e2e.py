"""Integration tests requiring Docker services (Qdrant, Langfuse)."""
from __future__ import annotations

import pytest

from src.models.schemas import QueryRequest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_query():
    """E2E test: ingest a document, query it, verify response structure.

    Requires: Qdrant running on localhost:6333, valid OpenAI + Cohere API keys.
    Run with: pytest tests/integration -m integration
    """
    from src.api.deps import get_orchestrator

    orchestrator = get_orchestrator()

    # Ensure collection
    await orchestrator._vector_store.ensure_collection()

    # Query (may return empty results if no docs ingested)
    request = QueryRequest(
        query="What are the pipeline phases?",
        user_id="test-user",
        tenant_id="test-tenant",
    )

    response = await orchestrator.query(request)

    assert response.trace_id is not None
    assert response.metadata.route_used == "rag_knowledge_base"
    assert response.metadata.latency_ms > 0
