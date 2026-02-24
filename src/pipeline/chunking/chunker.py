from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class DocumentChunker:
    def __init__(
        self,
        strategy: str = "by_title",
        max_characters: int = 1500,
        overlap: int = 200,
    ) -> None:
        self._strategy = strategy
        self._max_characters = max_characters
        self._overlap = overlap

    def chunk_file(self, file_path: str | Path) -> list[dict[str, Any]]:
        """Chunk a document file using Unstructured."""
        from unstructured.chunking.title import chunk_by_title
        from unstructured.partition.auto import partition

        file_path = Path(file_path)
        logger.info("chunking_file", path=str(file_path), strategy=self._strategy)

        elements = partition(filename=str(file_path))

        chunks = chunk_by_title(
            elements,
            max_characters=self._max_characters,
            overlap=self._overlap,
        )

        result = []
        for i, chunk in enumerate(chunks):
            result.append({
                "text_content": str(chunk),
                "chunk_index": i,
                "section_header": getattr(chunk.metadata, "section", None) if hasattr(chunk, "metadata") else None,
                "page_number": getattr(chunk.metadata, "page_number", None) if hasattr(chunk, "metadata") else None,
            })

        logger.info("chunking_complete", path=str(file_path), chunks=len(result))
        return result

    def chunk_text(self, text: str, doc_id: str = "unknown") -> list[dict[str, Any]]:
        """Chunk raw text by character limit with overlap."""
        chunks = []
        start = 0
        index = 0

        while start < len(text):
            end = start + self._max_characters
            chunk_text = text[start:end]

            chunks.append({
                "text_content": chunk_text,
                "chunk_index": index,
                "section_header": None,
                "page_number": None,
            })

            start = end - self._overlap
            index += 1

        logger.info("text_chunking_complete", doc_id=doc_id, chunks=len(chunks))
        return chunks
