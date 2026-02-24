from __future__ import annotations

from typing import Any

import structlog
from rank_bm25 import BM25Okapi

logger = structlog.get_logger()


class BM25Compressor:
    def __init__(self, sentences_per_chunk: int = 5) -> None:
        self._sentences_per_chunk = sentences_per_chunk

    def compress(self, query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compress chunks by extracting the most query-relevant sentences via BM25."""
        if not chunks:
            return []

        compressed = []
        for chunk in chunks:
            text = chunk.get("text_content", "")
            sentences = self._split_sentences(text)

            if len(sentences) <= self._sentences_per_chunk:
                compressed.append(chunk)
                continue

            # Score sentences by BM25 relevance to query
            tokenized = [s.lower().split() for s in sentences]
            bm25 = BM25Okapi(tokenized)
            scores = bm25.get_scores(query.lower().split())

            # Keep top-N sentences in original order
            indexed_scores = list(enumerate(scores))
            indexed_scores.sort(key=lambda x: x[1], reverse=True)
            top_indices = set(idx for idx, _ in indexed_scores[: self._sentences_per_chunk])
            dropped_indices = set(range(len(sentences))) - top_indices

            # Log kept/dropped sentences for Wave 3 faithfulness debugging
            logger.debug(
                "bm25_sentence_scores",
                chunk_id=chunk.get("id", "unknown"),
                query=query[:100],
                scores={i: round(float(s), 4) for i, s in enumerate(scores)},
                kept_indices=sorted(top_indices),
                dropped_indices=sorted(dropped_indices),
                dropped_sentences=[sentences[i][:80] for i in sorted(dropped_indices)],
            )

            selected = [sentences[i] for i in sorted(top_indices)]
            compressed.append({
                **chunk,
                "text_content": " ".join(selected),
                "compressed": True,
                "original_sentences": len(sentences),
                "kept_sentences": len(selected),
            })

        logger.info(
            "bm25_compression_complete",
            input_chunks=len(chunks),
            output_chunks=len(compressed),
        )
        return compressed

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Simple sentence splitting. In production, use spaCy for better accuracy."""
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s for s in sentences if s.strip()]
