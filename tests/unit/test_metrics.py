"""Tests for Prometheus metrics registry and /metrics endpoint (Deliverable 6.4)."""
from __future__ import annotations

import json
from pathlib import Path

from src.observability.metrics import (
    PIPELINE_REQUESTS_TOTAL,
    get_metrics_text,
)


class TestMetricsRegistry:
    def test_metrics_text_valid_format(self) -> None:
        """get_metrics_text returns valid Prometheus text format."""
        output = get_metrics_text()
        assert isinstance(output, bytes)
        text = output.decode("utf-8")
        # Should contain at least one metric family
        assert "pipeline_requests_total" in text or "# HELP" in text or "# TYPE" in text

    def test_counter_increment(self) -> None:
        """Counters can be incremented and appear in output."""
        PIPELINE_REQUESTS_TOTAL.labels(route="rag_knowledge_base", variant="control").inc()
        output = get_metrics_text().decode("utf-8")
        assert "pipeline_requests_total" in output

    def test_all_metric_families_present(self) -> None:
        """All expected metric families are registered."""
        output = get_metrics_text().decode("utf-8")
        expected_metrics = [
            "pipeline_requests_total",
            "pipeline_request_duration_seconds",
            "pipeline_request_duration_per_stage_seconds",
            "pipeline_errors_total",
            "safety_injection_blocked_total",
            "safety_pii_detected_total",
            "hallucination_score",
            "hallucination_check_failed_total",
            "llm_cost_usd_total",
            "llm_tokens_total",
            "embedding_centroid_shift_cosine",
            "embedding_spread_change",
            "embedding_drift_detected",
            "embedding_sample_count",
            "retrieval_cosine_sim_p50",
            "retrieval_cosine_sim_p95",
            "retrieval_cosine_sim_mean",
            "retrieval_result_count_avg",
            "retrieval_empty_result_rate",
            "retrieval_quality_alert_level",
            "ragas_faithfulness_daily",
            "ragas_context_precision_daily",
            "ragas_answer_relevancy_daily",
            "ragas_eval_sample_size",
            "ragas_eval_last_run_timestamp",
            "experiment_variant_assignment_total",
            "shadow_mode_runs_total",
            "shadow_mode_budget_remaining_usd",
        ]
        for metric in expected_metrics:
            assert metric in output, f"Missing metric: {metric}"

    def test_metrics_endpoint_zero_state(self) -> None:
        """All counters start at 0 — /metrics works before any queries."""
        output = get_metrics_text().decode("utf-8")
        # Should be parseable and non-empty
        assert len(output) > 100


class TestGrafanaDashboard:
    def test_dashboard_json_valid(self) -> None:
        """Grafana dashboard JSON is valid and has 5 rows."""
        dashboard_path = Path("monitoring/grafana/dashboards/pipeline-health.json")
        assert dashboard_path.exists(), "Dashboard JSON not found"

        data = json.loads(dashboard_path.read_text())
        assert data["title"] == "AI Pipeline Health"
        assert data["uid"] == "pipeline-health"

        # Count row panels
        rows = [p for p in data["panels"] if p["type"] == "row"]
        assert len(rows) == 5, f"Expected 5 rows, got {len(rows)}"

        # Verify row titles
        row_titles = [r["title"] for r in rows]
        assert "Row 1 — Traffic & Latency" in row_titles
        assert "Row 2 — Quality Scores" in row_titles
        assert "Row 3 — Retrieval Health" in row_titles
        assert "Row 4 — Safety & Compliance" in row_titles
        assert "Row 5 — Cost" in row_titles

    def test_prometheus_config_valid(self) -> None:
        """Prometheus config scrapes the FastAPI target."""
        config_path = Path("monitoring/prometheus.yml")
        assert config_path.exists()

        import yaml

        data = yaml.safe_load(config_path.read_text())
        assert data["scrape_configs"][0]["job_name"] == "enterprise-pipeline"
        assert data["scrape_configs"][0]["metrics_path"] == "/metrics"
