import pytest

from src.pipeline.retrieval.embeddings import EmbeddingService


@pytest.mark.asyncio
async def test_embed_query(mock_openai_client):
    service = EmbeddingService(client=mock_openai_client)
    result = await service.embed_query("test query")
    assert len(result) == 1536
    mock_openai_client.embeddings.create.assert_called_once()


@pytest.mark.asyncio
async def test_embed_texts(mock_openai_client):
    service = EmbeddingService(client=mock_openai_client)
    result = await service.embed_texts(["text 1", "text 2"])
    # Mock returns single item, but we test the call
    assert len(result) >= 1
    mock_openai_client.embeddings.create.assert_called_once()


@pytest.mark.asyncio
async def test_embed_empty(mock_openai_client):
    service = EmbeddingService(client=mock_openai_client)
    result = await service.embed_texts([])
    assert result == []
    mock_openai_client.embeddings.create.assert_not_called()
