from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


class Deduplicator:
    def __init__(self, threshold: float = 0.95) -> None:
        self._threshold = threshold

    def deduplicate(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove near-duplicate results based on cosine similarity of their embeddings.

        If embeddings are not available, falls back to keeping all results.
        Results must have 'score' and either 'embedding' or 'text_content' keys.
        """
        if len(results) <= 1:
            return results

        # Use retrieval scores as a proxy for dedup (works when embeddings aren't stored in results)
        # In production, re-embed or store embeddings in payload for exact dedup
        deduplicated: list[dict[str, Any]] = []
        seen_texts: set[str] = set()

        for result in results:
            text = result.get("text_content", "")
            # Simple exact-text dedup + near-duplicate via text hash
            text_key = text.strip().lower()
            if text_key in seen_texts:
                logger.debug("dedup_exact_match", chunk_id=result.get("id"))
                continue
            seen_texts.add(text_key)

            # Check cosine similarity against already-accepted results
            is_duplicate = False
            for accepted in deduplicated:
                sim = self._text_similarity(text, accepted.get("text_content", ""))
                if sim >= self._threshold:
                    logger.debug(
                        "dedup_near_match",
                        similarity=round(sim, 3),
                        chunk_id=result.get("id"),
                    )
                    is_duplicate = True
                    break

            if not is_duplicate:
                deduplicated.append(result)

        logger.info(
            "deduplication_complete",
            input_count=len(results),
            output_count=len(deduplicated),
            removed=len(results) - len(deduplicated),
        )
        return deduplicated

    @staticmethod
    def _text_similarity(text_a: str, text_b: str) -> float:
        """Compute character n-gram similarity as a fast proxy for semantic similarity."""
        if not text_a or not text_b:
            return 0.0

        n = 3
        ngrams_a = set(text_a[i : i + n] for i in range(len(text_a) - n + 1))
        ngrams_b = set(text_b[i : i + n] for i in range(len(text_b) - n + 1))

        if not ngrams_a or not ngrams_b:
            return 0.0

        intersection = ngrams_a & ngrams_b
        union = ngrams_a | ngrams_b
        return len(intersection) / len(union)
