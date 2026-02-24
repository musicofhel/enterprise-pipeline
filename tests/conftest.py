from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config.pipeline_config import PipelineConfig
from src.config.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        openrouter_api_key="sk-or-test",  # type: ignore[arg-type]
        cohere_api_key="test-cohere",  # type: ignore[arg-type]
        qdrant_host="localhost",
        qdrant_port=6333,
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",  # type: ignore[arg-type]
        pipeline_env="development",
    )


@pytest.fixture
def pipeline_config() -> PipelineConfig:
    return PipelineConfig()


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    client = AsyncMock()
    # Mock embeddings
    embedding_response = MagicMock()
    embedding_item = MagicMock()
    embedding_item.embedding = [0.1] * 1536
    embedding_response.data = [embedding_item]
    client.embeddings.create.return_value = embedding_response

    # Mock chat completions
    chat_response = MagicMock()
    choice = MagicMock()
    choice.message.content = "This is a test answer based on the context."
    chat_response.choices = [choice]
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    chat_response.usage = usage
    client.chat.completions.create.return_value = chat_response

    return client


@pytest.fixture
def mock_qdrant_client() -> AsyncMock:
    client = AsyncMock()

    # Mock get_collections
    collections = MagicMock()
    collections.collections = []
    client.get_collections.return_value = collections

    # Mock query_points
    search_result = MagicMock()
    points = []
    for i in range(5):
        point = MagicMock()
        point.id = f"point-{i}"
        point.score = 0.9 - (i * 0.05)
        point.payload = {
            "text_content": f"Sample chunk text {i}. This is test content for retrieval.",
            "doc_id": f"doc-{i}",
            "chunk_id": f"chunk-{i}",
            "user_id": "test-user",
            "tenant_id": "test-tenant",
        }
        points.append(point)
    search_result.points = points
    client.query_points.return_value = search_result

    return client


@pytest.fixture
def mock_cohere_client() -> AsyncMock:
    client = AsyncMock()
    rerank_response = MagicMock()
    results = []
    for i in range(3):
        item = MagicMock()
        item.index = i
        item.relevance_score = 0.95 - (i * 0.1)
        results.append(item)
    rerank_response.results = results
    client.rerank.return_value = rerank_response
    return client


@pytest.fixture
def sample_chunks() -> list[dict[str, Any]]:
    return [
        {
            "id": f"chunk-{i}",
            "score": 0.9 - (i * 0.05),
            "text_content": f"This is sample chunk {i}. It contains information about topic {i}. The content is relevant to the query.",
            "metadata": {
                "doc_id": f"doc-{i}",
                "chunk_id": f"chunk-{i}",
                "user_id": "test-user",
                "tenant_id": "test-tenant",
            },
        }
        for i in range(5)
    ]


@pytest.fixture
def sample_query_request() -> dict[str, Any]:
    return {
        "query": "What are the pipeline processing phases?",
        "user_id": "test-user",
        "tenant_id": "test-tenant",
        "session_id": "test-session",
    }
