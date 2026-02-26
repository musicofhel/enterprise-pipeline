"""Tests for DailyEvalRunner (Deliverable 6.3)."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — used at runtime

from src.observability.daily_eval import DailyEvalRunner
from src.observability.metrics import REGISTRY


def _create_trace(traces_dir: Path, trace_id: str, query: str, answer: str) -> None:
    """Create a minimal trace file for testing."""
    trace = {
        "trace_id": trace_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "user_id": "test-user",
        "session_id": "test-session",
        "pipeline_version": "test",
        "config_hash": "abc123",
        "feature_flags": {"pipeline_variant": "control"},
        "spans": [
            {
                "name": "generation",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "attributes": {
                    "model": "test-model",
                    "input": query,
                    "output": answer,
                    "tokens_in": 100,
                    "tokens_out": 50,
                },
            },
            {
                "name": "compression",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "attributes": {
                    "output": ["Context chunk 1", "Context chunk 2"],
                    "tokens_before": 200,
                    "tokens_after": 100,
                },
            },
        ],
        "scores": {"faithfulness": 0.92, "user_feedback": None},
        "total_latency_ms": 500,
        "total_cost_usd": 0.01,
    }
    traces_dir.mkdir(parents=True, exist_ok=True)
    (traces_dir / f"{trace_id}.json").write_text(json.dumps(trace))


class TestDailyEvalRunner:
    def test_sample_traces_extracts_data(self, tmp_path: Path) -> None:
        """Traces are sampled with query/context/answer extracted."""
        traces_dir = tmp_path / "traces"
        for i in range(10):
            _create_trace(traces_dir, f"trace-{i}", f"Query {i}", f"Answer {i}")

        runner = DailyEvalRunner(
            traces_dir=traces_dir,
            output_dir=tmp_path / "output",
            sample_size=50,
            lookback_hours=24,
        )

        samples = runner.sample_traces()
        assert len(samples) == 10
        assert all(s["query"] for s in samples)
        assert all(s["answer"] for s in samples)

    def test_report_structure(self, tmp_path: Path) -> None:
        """Report JSON has expected structure."""
        traces_dir = tmp_path / "traces"
        for i in range(5):
            _create_trace(traces_dir, f"trace-{i}", f"Query {i}", f"Answer {i}")

        runner = DailyEvalRunner(
            traces_dir=traces_dir,
            output_dir=tmp_path / "output",
            sample_size=50,
            lookback_hours=24,
        )

        # Without API key, should skip gracefully
        old_key = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            report = runner.run()
        finally:
            if old_key:
                os.environ["OPENROUTER_API_KEY"] = old_key

        assert report["status"] == "skipped"
        assert report["sample_size"] == 5
        assert "timestamp" in report

    def test_no_traces_insufficient_data(self, tmp_path: Path) -> None:
        """No traces → insufficient_data status."""
        runner = DailyEvalRunner(
            traces_dir=tmp_path / "nonexistent",
            output_dir=tmp_path / "output",
        )

        report = runner.run()
        assert report["status"] == "insufficient_data"
        assert report["sample_size"] == 0

    def test_prometheus_metrics_updated(self, tmp_path: Path) -> None:
        """Prometheus metrics should be updated after a run."""
        traces_dir = tmp_path / "traces"
        for i in range(3):
            _create_trace(traces_dir, f"trace-{i}", f"Query {i}", f"Answer {i}")

        runner = DailyEvalRunner(
            traces_dir=traces_dir,
            output_dir=tmp_path / "output",
        )

        old_key = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            runner.run()
        finally:
            if old_key:
                os.environ["OPENROUTER_API_KEY"] = old_key

        sample_size = REGISTRY.get_sample_value("ragas_eval_sample_size")
        assert sample_size is not None
        assert sample_size == 3

    def test_no_api_key_skips_gracefully(self, tmp_path: Path) -> None:
        """Without OPENROUTER_API_KEY, eval is skipped — no crash."""
        traces_dir = tmp_path / "traces"
        _create_trace(traces_dir, "trace-0", "Test query", "Test answer")

        runner = DailyEvalRunner(
            traces_dir=traces_dir,
            output_dir=tmp_path / "output",
        )

        old_key = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            report = runner.run()
        finally:
            if old_key:
                os.environ["OPENROUTER_API_KEY"] = old_key

        assert report["status"] == "skipped"
        assert "OPENROUTER_API_KEY" in report["message"]
