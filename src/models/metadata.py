from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DocType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    MARKDOWN = "markdown"
    CSV = "csv"


class AccessLevel(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ChunkMetadata(BaseModel):
    user_id: str
    tenant_id: str
    doc_id: str
    chunk_id: str = Field(default_factory=lambda: str(uuid4()))
    doc_type: DocType
    section_header: str | None = None
    page_number: int | None = None
    chunk_index: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    embedding_model: str = "text-embedding-3-small"
    embedding_model_version: str = "1"
    source_url: str | None = None
    access_level: AccessLevel = AccessLevel.INTERNAL


class VectorRecord(BaseModel):
    vector_id: UUID = Field(default_factory=uuid4)
    embedding: list[float]
    text_content: str
    metadata: ChunkMetadata
