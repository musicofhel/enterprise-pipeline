from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    import cohere

logger = structlog.get_logger()


class CohereReranker:
    def __init__(self, client: cohere.AsyncClientV2, top_n: int = 5) -> None:
        self._client = client
        self._top_n = top_n

    async def rerank(self, query: str, results: list[dict[str, Any]], top_n: int | None = None) -> list[dict[str, Any]]:
        """Rerank results using Cohere Rerank API."""
        if not results:
            return []

        top_n = top_n or self._top_n
        documents = [r.get("text_content", "") for r in results]

        logger.info("reranking", query_len=len(query), num_docs=len(documents), top_n=top_n)

        response = await self._client.rerank(
            model="rerank-v3.5",
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents)),
        )

        reranked = []
        for item in response.results:
            original = results[item.index]
            reranked.append({
                **original,
                "relevance_score": item.relevance_score,
            })

        logger.info("reranking_complete", output_count=len(reranked))
        return reranked
