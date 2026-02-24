import pytest

from src.pipeline.retrieval.vector_store import VectorStore


@pytest.mark.asyncio
async def test_search(mock_qdrant_client):
    store = VectorStore(client=mock_qdrant_client)
    results = await store.search(
        query_embedding=[0.1] * 1536,
        top_k=5,
        tenant_id="test-tenant",
    )
    assert len(results) == 5
    assert all("text_content" in r for r in results)
    assert all("score" in r for r in results)


@pytest.mark.asyncio
async def test_is_healthy(mock_qdrant_client):
    store = VectorStore(client=mock_qdrant_client)
    assert await store.is_healthy() is True


@pytest.mark.asyncio
async def test_is_healthy_failure(mock_qdrant_client):
    mock_qdrant_client.get_collections.side_effect = Exception("connection refused")
    store = VectorStore(client=mock_qdrant_client)
    assert await store.is_healthy() is False
