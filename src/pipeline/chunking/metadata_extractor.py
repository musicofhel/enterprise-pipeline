from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from src.models.metadata import AccessLevel, ChunkMetadata, DocType


class MetadataExtractor:
    def __init__(
        self,
        embedding_model: str = "text-embedding-3-small",
        embedding_model_version: str = "1",
    ) -> None:
        self._embedding_model = embedding_model
        self._embedding_model_version = embedding_model_version

    def create_metadata(
        self,
        chunk: dict[str, Any],
        user_id: str,
        tenant_id: str,
        doc_id: str,
        doc_type: str = "markdown",
        source_url: str | None = None,
        access_level: str = "internal",
    ) -> ChunkMetadata:
        """Create ChunkMetadata from a chunk dict and ingestion parameters."""
        now = datetime.utcnow()

        return ChunkMetadata(
            user_id=user_id,
            tenant_id=tenant_id,
            doc_id=doc_id,
            chunk_id=str(uuid4()),
            doc_type=DocType(doc_type),
            section_header=chunk.get("section_header"),
            page_number=chunk.get("page_number"),
            chunk_index=chunk.get("chunk_index", 0),
            created_at=now,
            updated_at=now,
            embedding_model=self._embedding_model,
            embedding_model_version=self._embedding_model_version,
            source_url=source_url,
            access_level=AccessLevel(access_level),
        )
