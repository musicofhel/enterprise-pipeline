"""Tests for experiment analyzer — 7 tests."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from src.experimentation.analysis import ExperimentAnalyzer


@pytest.fixture
def traces_dir(tmp_path: Path) -> Path:
    d = tmp_path / "traces"
    d.mkdir()
    return d


def _write_trace(traces_dir: Path, variant: str, latency: float, faith: float, idx: int = 0) -> None:
    data = {
        "trace_id": f"trace-{variant}-{idx}",
        "feature_flags": {"pipeline_variant": variant},
        "total_latency_ms": latency,
        "total_cost_usd": 0.01,
        "scores": {"faithfulness": faith},
    }
    (traces_dir / f"{variant}_{idx}.json").write_text(json.dumps(data))


class TestExperimentAnalyzer:
    def test_no_traces_returns_no_data(self, tmp_path: Path) -> None:
        analyzer = ExperimentAnalyzer(traces_dir=tmp_path / "empty")
        report = analyzer.analyze()
        assert report["status"] == "no_data"

    def test_load_traces_groups_by_variant(self, traces_dir: Path) -> None:
        _write_trace(traces_dir, "control", 100, 0.9, 0)
        _write_trace(traces_dir, "control", 110, 0.85, 1)
        _write_trace(traces_dir, "treatment_a", 120, 0.88, 0)

        analyzer = ExperimentAnalyzer(traces_dir=traces_dir)
        groups = analyzer.load_traces_by_variant()
        assert len(groups["control"]) == 2
        assert len(groups["treatment_a"]) == 1

    def test_compute_metrics(self) -> None:
        traces = [
            {"total_latency_ms": 100, "total_cost_usd": 0.01, "scores": {"faithfulness": 0.9}},
            {"total_latency_ms": 200, "total_cost_usd": 0.02, "scores": {"faithfulness": 0.8}},
        ]
        metrics = ExperimentAnalyzer.compute_metrics(traces)
        assert metrics["count"] == 2
        assert metrics["faithfulness_mean"] == pytest.approx(0.85)
        assert metrics["cost_total_usd"] == pytest.approx(0.03)

    def test_statistical_test_with_enough_data(self) -> None:
        import random

        random.seed(42)
        control = [0.9 + random.gauss(0, 0.05) for _ in range(50)]
        treatment = [0.92 + random.gauss(0, 0.05) for _ in range(50)]

        result = ExperimentAnalyzer.run_statistical_test(control, treatment)
        assert "ttest_statistic" in result
        assert "mannwhitney_statistic" in result
        assert "cohens_d" in result
        assert result["effect_size"] in ("negligible", "small", "medium", "large")

    def test_statistical_test_insufficient_samples(self) -> None:
        result = ExperimentAnalyzer.run_statistical_test([0.9], [0.85])
        assert "error" in result

    def test_analyze_insufficient_data_for_stats(self, traces_dir: Path) -> None:
        # Only 5 traces per variant — below min_traces=30
        for i in range(5):
            _write_trace(traces_dir, "control", 100 + i, 0.9, i)
            _write_trace(traces_dir, "treatment_a", 110 + i, 0.88, i)

        analyzer = ExperimentAnalyzer(traces_dir=traces_dir)
        report = analyzer.analyze(min_traces=30)
        assert report["statistical_tests"]["treatment_a"]["status"] == "insufficient_data"

    def test_analyze_full_report(self, traces_dir: Path) -> None:
        import random

        random.seed(42)
        for i in range(35):
            _write_trace(traces_dir, "control", 100 + random.gauss(0, 10), 0.9 + random.gauss(0, 0.03), i)
            _write_trace(traces_dir, "treatment_a", 105 + random.gauss(0, 10), 0.91 + random.gauss(0, 0.03), i)

        analyzer = ExperimentAnalyzer(traces_dir=traces_dir)
        report = analyzer.analyze(min_traces=30)

        assert "variants" in report
        assert "control" in report["variants"]
        assert "treatment_a" in report["variants"]
        assert "statistical_tests" in report
        assert "recommendation" in report
        # Should have performed the test
        assert "ttest_pvalue" in report["statistical_tests"]["treatment_a"]
