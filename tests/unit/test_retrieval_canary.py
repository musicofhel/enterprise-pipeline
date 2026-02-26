"""Tests for RetrievalQualityCanary (Deliverable 6.2)."""
from __future__ import annotations

from src.observability.metrics import (
    REGISTRY,
    RETRIEVAL_COSINE_SIM_P50,
    RETRIEVAL_QUALITY_ALERT_LEVEL,
)
from src.observability.retrieval_canary import (
    ALERT_CRITICAL,
    ALERT_OK,
    RetrievalQualityCanary,
)


def _reset_canary_metrics() -> None:
    RETRIEVAL_COSINE_SIM_P50.set(0)
    RETRIEVAL_QUALITY_ALERT_LEVEL.set(0)


class TestRetrievalQualityCanary:
    def test_normal_scores_no_alert(self) -> None:
        """Normal scores → no alert."""
        _reset_canary_metrics()
        canary = RetrievalQualityCanary(window_size=200, baseline_window_size=500)

        # Feed 100 queries with good scores
        for _ in range(100):
            canary.record_scores([0.75, 0.72, 0.80, 0.68, 0.77])

        status = canary.get_status()
        assert status["alert_level"] == ALERT_OK
        assert 0.65 < status["p50"] < 0.85
        assert status["empty_result_rate"] == 0.0

    def test_critical_p50_drop(self) -> None:
        """Significant p50 drop → CRITICAL alert."""
        _reset_canary_metrics()
        canary = RetrievalQualityCanary(window_size=200, baseline_window_size=500)

        # First: establish baseline with good scores
        for _ in range(200):
            canary.record_scores([0.75, 0.72, 0.80])

        # Then: drop scores by more than 10%
        # Create a new canary to test fresh window vs baseline
        canary2 = RetrievalQualityCanary(window_size=50, baseline_window_size=300)
        # Baseline with good scores
        for _ in range(200):
            canary2.record_scores([0.75, 0.72, 0.80])
        # Now flood with bad scores in the recent window
        for _ in range(50):
            canary2.record_scores([0.55, 0.50, 0.52])

        status = canary2.get_status()
        assert status["alert_level"] == ALERT_CRITICAL
        assert len(status["alert_reasons"]) > 0

    def test_critical_empty_result_rate(self) -> None:
        """High empty result rate → CRITICAL alert."""
        _reset_canary_metrics()
        canary = RetrievalQualityCanary(window_size=100, baseline_window_size=200)

        # Mix of normal and empty results (>5% empty)
        for i in range(100):
            if i < 10:
                canary.record_scores([])  # 10% empty
            else:
                canary.record_scores([0.75, 0.72, 0.80])

        status = canary.get_status()
        assert status["alert_level"] == ALERT_CRITICAL
        assert status["empty_result_rate"] > 0.05

    def test_prometheus_metrics_exported(self) -> None:
        """Metrics should be set after recording scores."""
        _reset_canary_metrics()
        canary = RetrievalQualityCanary(window_size=50)

        for _ in range(20):
            canary.record_scores([0.75, 0.70, 0.80])

        p50_val = REGISTRY.get_sample_value("retrieval_cosine_sim_p50")
        assert p50_val is not None
        assert p50_val > 0

    def test_rolling_window_eviction(self) -> None:
        """Old data should be evicted from the rolling window."""
        _reset_canary_metrics()
        canary = RetrievalQualityCanary(window_size=10, baseline_window_size=20)

        # Fill past capacity
        for _ in range(15):
            canary.record_scores([0.75])

        status = canary.get_status()
        assert status["recent_queries"] == 10  # window_size cap
        assert status["baseline_queries"] == 15  # within baseline_window_size
