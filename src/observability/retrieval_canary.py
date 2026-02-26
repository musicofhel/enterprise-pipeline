"""Retrieval quality canary — tracks cosine similarity distribution over time.

Maintains a rolling window of retrieval scores and compares against a
baseline to detect quality degradation. Exports metrics to Prometheus.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Any

import structlog

from src.observability.metrics import (
    RETRIEVAL_COSINE_SIM_MEAN,
    RETRIEVAL_COSINE_SIM_P50,
    RETRIEVAL_COSINE_SIM_P95,
    RETRIEVAL_EMPTY_RESULT_RATE,
    RETRIEVAL_QUALITY_ALERT_LEVEL,
    RETRIEVAL_RESULT_COUNT_AVG,
)

logger = structlog.get_logger()

# Alert thresholds
P50_WARN_DROP_PCT = 5.0  # WARN if p50 drops >5% from baseline
P50_CRITICAL_DROP_PCT = 10.0  # CRITICAL if p50 drops >10%
P95_CRITICAL_FLOOR = 0.3  # CRITICAL if p95 drops below this
EMPTY_RATE_CRITICAL_PCT = 5.0  # CRITICAL if >5% of queries return 0 results

# Alert levels
ALERT_OK = 0
ALERT_WARN = 1
ALERT_CRITICAL = 2


class RetrievalQualityCanary:
    """Track retrieval quality via cosine similarity distribution."""

    def __init__(
        self,
        window_size: int = 1000,
        baseline_window_size: int = 7000,  # ~7 days at 1000/day
    ) -> None:
        self._window_size = window_size
        # Each entry: (timestamp, scores_list)
        self._recent_queries: deque[tuple[float, list[float]]] = deque(maxlen=window_size)
        # Baseline: longer window for 7-day rolling average
        self._baseline_queries: deque[tuple[float, list[float]]] = deque(
            maxlen=baseline_window_size
        )

    def record_scores(self, scores: list[float]) -> None:
        """Record retrieval scores from a single query."""
        now = time.time()
        self._recent_queries.append((now, scores))
        self._baseline_queries.append((now, scores))
        self._update_metrics()

    def _all_scores(self, window: deque[tuple[float, list[float]]]) -> list[float]:
        """Flatten all scores from a window."""
        result: list[float] = []
        for _, scores in window:
            result.extend(scores)
        return result

    def _percentile(self, values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        idx = int(len(s) * pct / 100)
        return s[min(idx, len(s) - 1)]

    def _mean(self, values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def _empty_rate(self, window: deque[tuple[float, list[float]]]) -> float:
        if not window:
            return 0.0
        empty = sum(1 for _, scores in window if len(scores) == 0)
        return empty / len(window)

    def _avg_result_count(self, window: deque[tuple[float, list[float]]]) -> float:
        if not window:
            return 0.0
        return sum(len(scores) for _, scores in window) / len(window)

    def get_status(self) -> dict[str, Any]:
        """Compute current canary status with alert level."""
        all_recent = self._all_scores(self._recent_queries)
        all_baseline = self._all_scores(self._baseline_queries)

        current_p50 = self._percentile(all_recent, 50)
        current_p95 = self._percentile(all_recent, 95)
        current_mean = self._mean(all_recent)
        baseline_p50 = self._percentile(all_baseline, 50)
        empty_rate = self._empty_rate(self._recent_queries)
        avg_count = self._avg_result_count(self._recent_queries)

        # Determine alert level
        alert_level = ALERT_OK
        alert_reasons: list[str] = []

        if baseline_p50 > 0:
            p50_drop_pct = ((baseline_p50 - current_p50) / baseline_p50) * 100
            if p50_drop_pct > P50_CRITICAL_DROP_PCT:
                alert_level = ALERT_CRITICAL
                alert_reasons.append(f"p50 dropped {p50_drop_pct:.1f}% (>{P50_CRITICAL_DROP_PCT}%)")
            elif p50_drop_pct > P50_WARN_DROP_PCT:
                alert_level = max(alert_level, ALERT_WARN)
                alert_reasons.append(f"p50 dropped {p50_drop_pct:.1f}% (>{P50_WARN_DROP_PCT}%)")

        if current_p95 < P95_CRITICAL_FLOOR and len(all_recent) > 0:
            alert_level = ALERT_CRITICAL
            alert_reasons.append(f"p95={current_p95:.3f} below {P95_CRITICAL_FLOOR}")

        if empty_rate * 100 > EMPTY_RATE_CRITICAL_PCT:
            alert_level = ALERT_CRITICAL
            alert_reasons.append(
                f"empty_result_rate={empty_rate*100:.1f}% (>{EMPTY_RATE_CRITICAL_PCT}%)"
            )

        return {
            "p50": round(current_p50, 4),
            "p95": round(current_p95, 4),
            "mean": round(current_mean, 4),
            "baseline_p50": round(baseline_p50, 4),
            "empty_result_rate": round(empty_rate, 4),
            "avg_result_count": round(avg_count, 2),
            "alert_level": alert_level,
            "alert_label": ["ok", "warn", "critical"][alert_level],
            "alert_reasons": alert_reasons,
            "recent_queries": len(self._recent_queries),
            "baseline_queries": len(self._baseline_queries),
        }

    def _update_metrics(self) -> None:
        """Push current stats to Prometheus gauges."""
        status = self.get_status()
        RETRIEVAL_COSINE_SIM_P50.set(status["p50"])
        RETRIEVAL_COSINE_SIM_P95.set(status["p95"])
        RETRIEVAL_COSINE_SIM_MEAN.set(status["mean"])
        RETRIEVAL_RESULT_COUNT_AVG.set(status["avg_result_count"])
        RETRIEVAL_EMPTY_RESULT_RATE.set(status["empty_result_rate"])
        RETRIEVAL_QUALITY_ALERT_LEVEL.set(status["alert_level"])
