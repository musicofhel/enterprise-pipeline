"""Tests for EmbeddingMonitor (Deliverable 6.1)."""
from __future__ import annotations

import numpy as np

from src.observability.embedding_monitor import EmbeddingMonitor
from src.observability.metrics import (
    EMBEDDING_CENTROID_SHIFT,
    EMBEDDING_DRIFT_DETECTED,
    EMBEDDING_SPREAD_CHANGE,
    REGISTRY,
)


def _reset_metrics() -> None:
    """Reset embedding metrics for test isolation."""
    # Gauges can be set; counter needs _value reset
    EMBEDDING_CENTROID_SHIFT.set(0)
    EMBEDDING_SPREAD_CHANGE.set(0)
    EMBEDDING_DRIFT_DETECTED.set(0)


class TestEmbeddingMonitor:
    def test_no_drift_same_distribution(self) -> None:
        """Same distribution as reference → no drift."""
        _reset_metrics()
        rng = np.random.default_rng(42)
        reference = rng.normal(loc=0.5, scale=0.1, size=(100, 64))

        monitor = EmbeddingMonitor(reference_embeddings=reference, drift_threshold=0.15)

        # Record embeddings from the same distribution
        current = rng.normal(loc=0.5, scale=0.1, size=(100, 64))
        monitor.record_embeddings(current.tolist())

        report = monitor.check_drift()
        assert report["drift_detected"] is False
        assert report["sample_size"] == 100
        assert abs(report["reference_centroid_shift"]) < 0.05  # small shift

    def test_drift_detected_shifted_centroid(self) -> None:
        """Shifted centroid → drift detected."""
        _reset_metrics()
        rng = np.random.default_rng(42)
        # Reference centered at 0 — half positive, half negative
        reference = rng.normal(loc=0.0, scale=1.0, size=(100, 64))

        monitor = EmbeddingMonitor(reference_embeddings=reference, drift_threshold=0.10)

        # Shift half the dimensions to large negative values to change direction
        shifted = rng.normal(loc=0.0, scale=1.0, size=(100, 64))
        shifted[:, :32] = rng.normal(loc=5.0, scale=0.1, size=(100, 32))
        shifted[:, 32:] = rng.normal(loc=-5.0, scale=0.1, size=(100, 32))
        monitor.record_embeddings(shifted.tolist())

        report = monitor.check_drift()
        assert report["drift_detected"] is True
        assert report["reference_centroid_shift"] > 0.10

    def test_prometheus_metrics_exported(self) -> None:
        """Metrics should be set after check_drift."""
        _reset_metrics()
        rng = np.random.default_rng(42)
        reference = rng.normal(loc=0.5, scale=0.1, size=(50, 32))

        monitor = EmbeddingMonitor(reference_embeddings=reference)
        current = rng.normal(loc=0.5, scale=0.1, size=(50, 32))
        monitor.record_embeddings(current.tolist())
        monitor.check_drift()

        # Check that Prometheus metrics are populated
        centroid_val = REGISTRY.get_sample_value("embedding_centroid_shift_cosine")
        assert centroid_val is not None

        drift_val = REGISTRY.get_sample_value("embedding_drift_detected")
        assert drift_val is not None

    def test_no_reference_set(self) -> None:
        """Without a reference, check_drift returns safe defaults."""
        monitor = EmbeddingMonitor()
        report = monitor.check_drift()
        assert report["drift_detected"] is False
        assert "error" in report

    def test_insufficient_samples(self) -> None:
        """Fewer than 10 samples → safe defaults."""
        rng = np.random.default_rng(42)
        reference = rng.normal(loc=0.5, scale=0.1, size=(50, 32))
        monitor = EmbeddingMonitor(reference_embeddings=reference)

        # Only 5 embeddings
        monitor.record_embeddings([[0.1] * 32] * 5)
        report = monitor.check_drift()
        assert report["drift_detected"] is False
        assert report["sample_size"] == 5
