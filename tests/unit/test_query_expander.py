from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pipeline.retrieval.query_expander import QueryExpander


def _make_chat_response(content: str) -> MagicMock:
    """Build a mock OpenAI chat completion response."""
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    response.choices = [choice]
    return response


@pytest.fixture
def mock_client() -> AsyncMock:
    """AsyncOpenAI mock that returns three rephrased queries."""
    client = AsyncMock()
    client.chat.completions.create.return_value = _make_chat_response(
        "What are the key retrieval methods used in RAG systems?\n"
        "How do RAG pipelines perform document retrieval?\n"
        "Which techniques does a RAG architecture use to fetch relevant documents?"
    )
    return client


# ---- Tests ----


@pytest.mark.asyncio
async def test_expand_returns_original_plus_rephrasings(mock_client: AsyncMock):
    """The result should start with the original query followed by LLM rephrasings."""
    expander = QueryExpander(client=mock_client, num_queries=3)
    result = await expander.expand("How does RAG retrieval work?")

    assert result[0] == "How does RAG retrieval work?"
    assert len(result) == 4  # original + 3 rephrasings


@pytest.mark.asyncio
async def test_expand_returns_only_original_on_llm_error(mock_client: AsyncMock):
    """On an LLM exception, expand should gracefully return just the original query."""
    mock_client.chat.completions.create.side_effect = RuntimeError("API timeout")

    expander = QueryExpander(client=mock_client, num_queries=3)
    result = await expander.expand("What is vector search?")

    assert result == ["What is vector search?"]


@pytest.mark.asyncio
async def test_num_queries_controls_output_length(mock_client: AsyncMock):
    """Setting num_queries=2 should cap rephrasings at 2, even if LLM returns more."""
    expander = QueryExpander(client=mock_client, num_queries=2)
    result = await expander.expand("Explain embeddings")

    # original + at most 2 rephrasings
    assert len(result) == 3
    assert result[0] == "Explain embeddings"


@pytest.mark.asyncio
async def test_expand_with_num_queries_zero(mock_client: AsyncMock):
    """num_queries < 1 should skip LLM entirely and return just the original."""
    expander = QueryExpander(client=mock_client, num_queries=0)
    result = await expander.expand("test query")

    assert result == ["test query"]
    mock_client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_expand_handles_empty_llm_response(mock_client: AsyncMock):
    """If the LLM returns an empty string, expand should still return the original."""
    mock_client.chat.completions.create.return_value = _make_chat_response("")

    expander = QueryExpander(client=mock_client, num_queries=3)
    result = await expander.expand("What is chunking?")

    assert result == ["What is chunking?"]


@pytest.mark.asyncio
async def test_expand_strips_whitespace_from_lines(mock_client: AsyncMock):
    """Blank lines and leading/trailing whitespace should be stripped."""
    mock_client.chat.completions.create.return_value = _make_chat_response(
        "  Rephrased query one  \n"
        "\n"
        "  Rephrased query two  \n"
        "\n"
        "  Rephrased query three  \n"
    )

    expander = QueryExpander(client=mock_client, num_queries=3)
    result = await expander.expand("original")

    assert result[0] == "original"
    assert result[1] == "Rephrased query one"
    assert result[2] == "Rephrased query two"
    assert result[3] == "Rephrased query three"
    assert len(result) == 4


@pytest.mark.asyncio
async def test_expand_passes_correct_model(mock_client: AsyncMock):
    """The configured model should be forwarded to the OpenAI client."""
    expander = QueryExpander(client=mock_client, num_queries=2, model="anthropic/claude-haiku-4-5")
    await expander.expand("test")

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "anthropic/claude-haiku-4-5"


@pytest.mark.asyncio
async def test_expand_handles_none_content(mock_client: AsyncMock):
    """If the LLM returns None content, expand should return just the original."""
    mock_client.chat.completions.create.return_value = _make_chat_response(None)  # type: ignore[arg-type]

    expander = QueryExpander(client=mock_client, num_queries=3)
    result = await expander.expand("test query")

    assert result == ["test query"]
