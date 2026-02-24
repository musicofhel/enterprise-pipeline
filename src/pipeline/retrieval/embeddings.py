from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = structlog.get_logger()


class EmbeddingService:
    def __init__(
        self,
        client: AsyncOpenAI,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []

        logger.info("generating_embeddings", count=len(texts), model=self._model)

        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
            dimensions=self._dimensions,
        )

        return [item.embedding for item in response.data]

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query."""
        results = await self.embed_texts([query])
        return results[0]
