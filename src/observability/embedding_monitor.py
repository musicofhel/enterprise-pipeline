"""Embedding drift monitoring — tracks how embedding distributions change over time.

Computes drift metrics by comparing current embedding batches against a reference
distribution (centroid + spread). Uses cosine distance for centroid shift and
standard deviation change for spread monitoring.
"""
from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Any

import numpy as np
import structlog

from src.observability.metrics import (
    EMBEDDING_CENTROID_SHIFT,
    EMBEDDING_DRIFT_DETECTED,
    EMBEDDING_SAMPLE_COUNT,
    EMBEDDING_SPREAD_CHANGE,
)

logger = structlog.get_logger()

# Drift thresholds
CENTROID_SHIFT_THRESHOLD = 0.15  # cosine distance from reference centroid
SPREAD_CHANGE_THRESHOLD = 0.20  # relative change in spread


class EmbeddingMonitor:
    """Track embedding distribution drift against a reference."""

    def __init__(
        self,
        reference_embeddings: np.ndarray | None = None,
        window_size: int = 1000,
        drift_threshold: float = CENTROID_SHIFT_THRESHOLD,
    ) -> None:
        self._window_size = window_size
        self._drift_threshold = drift_threshold
        self._embeddings_buffer: deque[list[float]] = deque(maxlen=window_size)

        # Reference distribution stats
        self._reference_centroid: np.ndarray | None = None
        self._reference_spread: float = 0.0

        if reference_embeddings is not None:
            self.set_reference(reference_embeddings)

    def set_reference(self, embeddings: np.ndarray) -> None:
        """Set the reference distribution from a numpy array of embeddings."""
        if len(embeddings) == 0:
            return
        self._reference_centroid = np.mean(embeddings, axis=0)
        # Spread = mean pairwise distance from centroid
        distances = np.linalg.norm(embeddings - self._reference_centroid, axis=1)
        self._reference_spread = float(np.mean(distances))
        logger.info(
            "embedding_reference_set",
            num_embeddings=len(embeddings),
            spread=round(self._reference_spread, 4),
        )

    def record_embeddings(self, embeddings: list[list[float]]) -> None:
        """Record a batch of embeddings from a retrieval call."""
        for emb in embeddings:
            self._embeddings_buffer.append(emb)
            EMBEDDING_SAMPLE_COUNT.inc()

    def check_drift(self) -> dict[str, Any]:
        """Compute drift metrics comparing current buffer to reference."""
        now = datetime.now(UTC).isoformat()

        if self._reference_centroid is None:
            return {
                "reference_centroid_shift": 0.0,
                "reference_spread_change": 0.0,
                "drift_detected": False,
                "sample_size": 0,
                "timestamp": now,
                "error": "No reference distribution set",
            }

        if len(self._embeddings_buffer) < 10:
            return {
                "reference_centroid_shift": 0.0,
                "reference_spread_change": 0.0,
                "drift_detected": False,
                "sample_size": len(self._embeddings_buffer),
                "timestamp": now,
                "error": "Insufficient samples (need >= 10)",
            }

        current = np.array(list(self._embeddings_buffer))
        current_centroid = np.mean(current, axis=0)

        # Cosine distance between centroids
        dot = float(np.dot(self._reference_centroid, current_centroid))
        norm_ref = float(np.linalg.norm(self._reference_centroid))
        norm_cur = float(np.linalg.norm(current_centroid))
        if norm_ref > 0 and norm_cur > 0:
            cosine_sim = dot / (norm_ref * norm_cur)
            centroid_shift = 1.0 - cosine_sim
        else:
            centroid_shift = 0.0

        # Spread change (relative)
        distances = np.linalg.norm(current - current_centroid, axis=1)
        current_spread = float(np.mean(distances))
        if self._reference_spread > 0:
            spread_change = (current_spread - self._reference_spread) / self._reference_spread
        else:
            spread_change = 0.0

        drift_detected = (
            abs(centroid_shift) > self._drift_threshold
            or abs(spread_change) > SPREAD_CHANGE_THRESHOLD
        )

        # Update Prometheus metrics
        EMBEDDING_CENTROID_SHIFT.set(round(centroid_shift, 6))
        EMBEDDING_SPREAD_CHANGE.set(round(spread_change, 6))
        EMBEDDING_DRIFT_DETECTED.set(1 if drift_detected else 0)

        report = {
            "reference_centroid_shift": round(centroid_shift, 6),
            "reference_spread_change": round(spread_change, 6),
            "drift_detected": drift_detected,
            "sample_size": len(self._embeddings_buffer),
            "timestamp": now,
        }

        if drift_detected:
            logger.warning("embedding_drift_detected", **report)
        else:
            logger.info("embedding_drift_check", **report)

        return report
