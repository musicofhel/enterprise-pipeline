from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

if TYPE_CHECKING:
    from uuid import UUID

    from qdrant_client import AsyncQdrantClient

logger = structlog.get_logger()

COLLECTION_NAME = "documents"


class VectorStore:
    def __init__(self, client: AsyncQdrantClient) -> None:
        self._client = client

    async def ensure_collection(self, vector_size: int = 1536) -> None:
        """Create collection if it doesn't exist."""
        collections = await self._client.get_collections()
        existing = [c.name for c in collections.collections]

        if COLLECTION_NAME not in existing:
            await self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("collection_created", name=COLLECTION_NAME, vector_size=vector_size)

    async def upsert(
        self,
        vector_id: UUID,
        embedding: list[float],
        text_content: str,
        metadata: dict[str, Any],
    ) -> None:
        """Upsert a single vector with metadata."""
        point = PointStruct(
            id=str(vector_id),
            vector=embedding,
            payload={"text_content": text_content, **metadata},
        )
        await self._client.upsert(collection_name=COLLECTION_NAME, points=[point])

    async def upsert_batch(
        self,
        points: list[dict[str, Any]],
    ) -> None:
        """Upsert a batch of vectors."""
        qdrant_points = [
            PointStruct(
                id=str(p["vector_id"]),
                vector=p["embedding"],
                payload={"text_content": p["text_content"], **p["metadata"]},
            )
            for p in points
        ]
        await self._client.upsert(collection_name=COLLECTION_NAME, points=qdrant_points)
        logger.info("batch_upserted", count=len(qdrant_points))

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors with optional tenant/user filtering."""
        conditions = []
        if tenant_id:
            conditions.append(FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)))
        if user_id:
            conditions.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))

        query_filter = Filter(must=conditions) if conditions else None

        results = await self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            {
                "id": str(point.id),
                "score": point.score,
                "text_content": point.payload.get("text_content", "") if point.payload else "",
                "metadata": {
                    k: v
                    for k, v in (point.payload or {}).items()
                    if k != "text_content"
                },
            }
            for point in results.points
        ]

    async def delete_by_user(self, user_id: str) -> int:
        """Delete all vectors for a user. Returns estimated count deleted."""
        await self._client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
        )
        logger.info("vectors_deleted_by_user", user_id=user_id)
        return 0  # Qdrant doesn't return count on delete

    async def is_healthy(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            await self._client.get_collections()
            return True
        except Exception:
            return False
