"""Shared test fixtures and OpenRouter → OpenAI env bridge.

DeepEval's FaithfulnessMetric uses the OpenAI SDK internally for LLM-based
claim decomposition.  It reads OPENAI_API_KEY and OPENAI_BASE_URL from the
environment — it knows nothing about OpenRouter.

This conftest installs a **session-scoped autouse fixture** that copies
OPENROUTER_API_KEY into the two OpenAI env vars so that DeepEval (and any
other library that speaks the OpenAI protocol) routes through OpenRouter
automatically.

    OPENROUTER_API_KEY  →  OPENAI_API_KEY
    (always)            →  OPENAI_BASE_URL = https://openrouter.ai/api/v1

The bridge only activates when OPENROUTER_API_KEY is set **and**
OPENAI_API_KEY is *not* already set (so an explicit OPENAI_API_KEY still
wins if someone needs raw OpenAI access).

CI only needs one secret: OPENROUTER_API_KEY.
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config.pipeline_config import PipelineConfig
from src.config.settings import Settings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@pytest.fixture(autouse=True, scope="session")
def _bridge_openrouter_to_openai_env() -> None:
    """Set OPENAI_API_KEY and OPENAI_BASE_URL from OPENROUTER_API_KEY.

    Runs once per test session, before any test collection.  Only writes the
    env vars when OPENROUTER_API_KEY is present and OPENAI_API_KEY is absent.
    """
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if openrouter_key and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = openrouter_key
        os.environ["OPENAI_BASE_URL"] = OPENROUTER_BASE_URL


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


@pytest.fixture
def mock_audit_log_service() -> MagicMock:
    from src.observability.audit_log import AuditLogService

    service = MagicMock(spec=AuditLogService)
    service.log_event.return_value = "test-event-id"
    service.list_events.return_value = []
    return service


@pytest.fixture
def mock_deletion_service() -> AsyncMock:
    from src.services.deletion_service import DeletionReceipt, DeletionService

    service = AsyncMock(spec=DeletionService)
    receipt = DeletionReceipt(
        deletion_id="del-123",
        user_id="test-user",
        tenant_id="test-tenant",
        reason="test",
    )
    receipt.status = "completed"
    receipt.vectors_deleted = 5
    receipt.traces_redacted = 2
    service.delete_user_data.return_value = receipt
    service.get_deletion_status.return_value = receipt
    service.verify_deletion.return_value = True
    return service
