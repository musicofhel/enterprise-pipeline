"""Local embedding service using sentence-transformers.

Runs on CPU (or GPU if available). No API key needed.
Used for routing embeddings — fast, free, and deterministic.
"""
from __future__ import annotations

import structlog
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger()

# Module-level model cache — load once, reuse across requests.
_model_cache: dict[str, SentenceTransformer] = {}


def _get_model(model_name: str) -> SentenceTransformer:
    """Load the sentence-transformers model, caching it for reuse."""
    if model_name not in _model_cache:
        logger.info("local_embedding_model_loading", model=model_name)
        _model_cache[model_name] = SentenceTransformer(model_name)
        logger.info("local_embedding_model_loaded", model=model_name)
    return _model_cache[model_name]


class LocalEmbeddingService:
    """Embedding service using sentence-transformers for local inference.

    Drop-in replacement for EmbeddingService where API embeddings aren't needed.
    Primary use case: routing embeddings (fast, no API cost).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    def _ensure_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = _get_model(self._model_name)
        return self._model

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        model = self._ensure_model()
        return model.get_sentence_embedding_dimension()  # type: ignore[return-value]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts using local model."""
        if not texts:
            return []

        logger.info("generating_local_embeddings", count=len(texts), model=self._model_name)

        model = self._ensure_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()  # type: ignore[no-any-return]

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query."""
        results = await self.embed_texts([query])
        return results[0]
