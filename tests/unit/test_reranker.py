import pytest

from src.pipeline.reranking.cohere_reranker import CohereReranker


@pytest.mark.asyncio
async def test_rerank(mock_cohere_client, sample_chunks):
    reranker = CohereReranker(client=mock_cohere_client, top_n=3)
    result = await reranker.rerank("test query", sample_chunks[:3])
    assert len(result) == 3
    assert all("relevance_score" in r for r in result)


@pytest.mark.asyncio
async def test_rerank_empty(mock_cohere_client):
    reranker = CohereReranker(client=mock_cohere_client)
    result = await reranker.rerank("query", [])
    assert result == []
    mock_cohere_client.rerank.assert_not_called()
