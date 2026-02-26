from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog
import yaml

if TYPE_CHECKING:
    from src.pipeline.retrieval.embeddings import EmbeddingService

logger = structlog.get_logger()

# Type alias for the injectable embedding function.
# Accepts a list of strings, returns a list of float vectors.
EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]


def _default_routes_path() -> Path:
    """Return the path to the bundled routes.yaml next to this module."""
    return Path(__file__).parent / "routes.yaml"


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    dot = float(np.dot(a, b))
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class RouteDefinition:
    """A single route with its name, description, and utterance examples."""

    __slots__ = ("description", "name", "utterances")

    def __init__(self, name: str, description: str, utterances: list[str]) -> None:
        self.name = name
        self.description = description
        self.utterances = utterances


class QueryRouter:
    """Lightweight semantic query router.

    Routes incoming queries to the best-matching pipeline route by computing
    cosine similarity between the query embedding and pre-computed utterance
    embeddings for each route.  Falls back to ``default_route`` when the
    highest confidence is below ``confidence_threshold``.

    The embedding function is injectable so that unit tests can substitute
    deterministic vectors without calling an external API.
    """

    def __init__(
        self,
        default_route: str = "rag_knowledge_base",
        confidence_threshold: float = 0.7,
        routes_path: str | Path | None = None,
        embedding_service: EmbeddingService | None = None,
        embed_fn: EmbedFn | None = None,
    ) -> None:
        self._default_route = default_route
        self._confidence_threshold = confidence_threshold
        self._routes_path = Path(routes_path) if routes_path else _default_routes_path()

        # Accept either a full EmbeddingService or a raw callable.
        # The callable form makes testing trivial — no mock OpenAI needed.
        if embed_fn is not None:
            self._embed_fn: EmbedFn = embed_fn
        elif embedding_service is not None:
            self._embed_fn = embedding_service.embed_texts
        else:
            raise ValueError(
                "QueryRouter requires either embed_fn or embedding_service"
            )

        # Loaded on first use (or via explicit initialize())
        self._routes: list[RouteDefinition] = []
        self._route_embeddings: dict[str, np.ndarray] = {}  # route_name -> (N, D) array
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _load_routes(self) -> list[RouteDefinition]:
        """Parse the routes YAML file and return route definitions."""
        if not self._routes_path.exists():
            raise FileNotFoundError(f"Routes file not found: {self._routes_path}")

        with open(self._routes_path) as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        route_defs: list[RouteDefinition] = []
        for entry in raw.get("routes", []):
            route_defs.append(
                RouteDefinition(
                    name=entry["name"],
                    description=entry.get("description", ""),
                    utterances=entry.get("utterances", []),
                )
            )

        logger.info(
            "routes_loaded",
            path=str(self._routes_path),
            num_routes=len(route_defs),
            total_utterances=sum(len(r.utterances) for r in route_defs),
        )
        return route_defs

    async def _compute_route_embeddings(self) -> dict[str, np.ndarray]:
        """Embed all utterances for every route and cache the result."""
        # Collect all utterances in a single batch for efficiency.
        all_utterances: list[str] = []
        route_slices: list[tuple[str, int, int]] = []  # (route_name, start_idx, end_idx)

        for route in self._routes:
            start = len(all_utterances)
            all_utterances.extend(route.utterances)
            route_slices.append((route.name, start, len(all_utterances)))

        if not all_utterances:
            return {}

        logger.info("computing_route_embeddings", num_utterances=len(all_utterances))
        raw_embeddings = await self._embed_fn(all_utterances)
        all_vectors = np.array(raw_embeddings, dtype=np.float32)

        embeddings: dict[str, np.ndarray] = {}
        for route_name, start, end in route_slices:
            embeddings[route_name] = all_vectors[start:end]

        return embeddings

    async def initialize(self) -> None:
        """Explicitly pre-load routes and compute embeddings.

        This is called automatically on the first ``route()`` call, but can
        be invoked eagerly at startup if you want to fail fast on bad config.
        """
        self._routes = self._load_routes()
        self._route_embeddings = await self._compute_route_embeddings()
        self._initialized = True
        logger.info("query_router_initialized", num_routes=len(self._routes))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def routes(self) -> list[RouteDefinition]:
        """Return loaded route definitions (empty before initialization)."""
        return list(self._routes)

    async def route(self, query: str) -> dict[str, Any]:
        """Route a query to the best-matching pipeline route.

        Returns a dict with at least:
          - ``route``: the chosen route name
          - ``confidence``: similarity score (0-1)
          - ``matched_utterances``: top matching utterances from the winning route
          - ``scores``: per-route max similarity
          - ``skipped``: always ``False`` (this is a real router, not the stub)
        """
        if not self._initialized:
            await self.initialize()

        # Embed the incoming query (batch of 1).
        query_vectors = await self._embed_fn([query])
        query_vec = np.array(query_vectors[0], dtype=np.float32)

        # Score each route by MAX cosine similarity to its utterances.
        # Max-sim is the standard approach for intent classification: the query
        # only needs to match ONE example utterance well, not all of them.
        route_scores: dict[str, float] = {}
        route_top_utterances: dict[str, list[tuple[float, str]]] = {}

        for route in self._routes:
            route_vecs = self._route_embeddings.get(route.name)
            if route_vecs is None or route_vecs.shape[0] == 0:
                route_scores[route.name] = 0.0
                route_top_utterances[route.name] = []
                continue

            similarities = np.array([
                _cosine_similarity(query_vec, route_vecs[i])
                for i in range(route_vecs.shape[0])
            ])
            max_sim = float(np.max(similarities))
            route_scores[route.name] = max_sim

            # Keep top-3 utterances by similarity for explainability.
            top_indices = np.argsort(similarities)[::-1][:3]
            route_top_utterances[route.name] = [
                (float(similarities[idx]), route.utterances[idx])
                for idx in top_indices
            ]

        # Pick the route with the highest max similarity.
        best_route = max(route_scores, key=route_scores.get)  # type: ignore[arg-type]
        # Clamp to [0, 1] — cosine similarity can be negative with dissimilar vectors
        best_confidence = max(0.0, min(1.0, route_scores[best_route]))

        # Fall back to the default route if below threshold.
        if best_confidence < self._confidence_threshold:
            logger.info(
                "route_below_threshold",
                best_route=best_route,
                best_confidence=round(best_confidence, 4),
                threshold=self._confidence_threshold,
                fallback=self._default_route,
            )
            chosen_route = self._default_route
            confidence = best_confidence
        else:
            chosen_route = best_route
            confidence = best_confidence

        logger.info(
            "query_routed",
            query_preview=query[:80],
            route=chosen_route,
            confidence=round(confidence, 4),
            all_scores={k: round(v, 4) for k, v in route_scores.items()},
        )

        return {
            "route": chosen_route,
            "confidence": round(confidence, 4),
            "matched_utterances": [
                {"text": text, "similarity": round(sim, 4)}
                for sim, text in route_top_utterances.get(chosen_route, [])
            ],
            "scores": {k: round(max(0.0, min(1.0, v)), 4) for k, v in route_scores.items()},
            "skipped": False,
        }
