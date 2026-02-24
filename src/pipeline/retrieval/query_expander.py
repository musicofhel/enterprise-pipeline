from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = structlog.get_logger()

EXPANSION_SYSTEM_PROMPT = (
    "You are a search query expansion assistant. Your job is to rephrase a user's "
    "question into alternative formulations that capture different angles, synonyms, "
    "and perspectives. This helps retrieve a broader set of relevant documents.\n\n"
    "Rules:\n"
    "- Each rephrased query must preserve the original intent.\n"
    "- Use different vocabulary, phrasing structure, or emphasis.\n"
    "- Do NOT answer the question — only rephrase it.\n"
    "- Return exactly {num_queries} rephrased queries, one per line.\n"
    "- Do NOT number the lines or add any prefix."
)


class QueryExpander:
    """Generates alternative phrasings of a query to improve retrieval recall."""

    def __init__(
        self,
        client: AsyncOpenAI,
        num_queries: int = 3,
        model: str = "gpt-4o",
    ) -> None:
        self._client = client
        self._num_queries = num_queries
        self._model = model

    async def expand(self, query: str) -> list[str]:
        """Return the original query plus LLM-generated rephrasings.

        On any failure, gracefully degrades to returning just the original query.
        """
        if self._num_queries < 1:
            return [query]

        logger.info(
            "query_expansion_start",
            original_query=query,
            num_queries=self._num_queries,
            model=self._model,
        )

        try:
            rephrasings = await self._generate_rephrasings(query)
        except Exception:
            logger.warning(
                "query_expansion_failed",
                original_query=query,
                exc_info=True,
            )
            return [query]

        expanded = [query, *rephrasings]

        logger.info(
            "query_expansion_complete",
            original_query=query,
            num_expanded=len(expanded),
        )
        return expanded

    async def _generate_rephrasings(self, query: str) -> list[str]:
        """Call the LLM to produce alternative query phrasings."""
        system_message = EXPANSION_SYSTEM_PROMPT.format(num_queries=self._num_queries)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": query},
            ],
            temperature=0.7,
            max_tokens=300,
        )

        content = response.choices[0].message.content or ""
        lines = [line.strip() for line in content.strip().splitlines() if line.strip()]

        # Take at most num_queries rephrasings (the LLM may return more or fewer)
        return lines[: self._num_queries]
