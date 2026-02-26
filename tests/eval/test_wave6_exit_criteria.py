"""Wave 6 exit criteria tests.

EC-1: Arize Phoenix shows embedding distributions and drift trends
EC-2: Grafana alerts fire within 5 minutes of injected quality degradation
EC-3: Ragas daily eval runs (or skips gracefully without API key)
EC-4: Unified dashboard has all 5 rows operational
EC-5: Every alert has a documented runbook
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from src.observability.embedding_monitor import EmbeddingMonitor
from src.observability.metrics import get_metrics_text
from src.observability.retrieval_canary import ALERT_CRITICAL, RetrievalQualityCanary


class TestEC1EmbeddingDrift:
    """EC-1: Arize Phoenix shows embedding distributions and drift trends."""

    def test_drift_detection_works(self) -> None:
        """EmbeddingMonitor detects centroid shift."""
        rng = np.random.default_rng(42)
        reference = rng.normal(loc=0.0, scale=1.0, size=(100, 64))

        monitor = EmbeddingMonitor(reference_embeddings=reference, drift_threshold=0.10)
        # Shift direction: concentrate all values in first half positive, second half negative
        shifted = np.zeros((100, 64))
        shifted[:, :32] = rng.normal(loc=5.0, scale=0.1, size=(100, 32))
        shifted[:, 32:] = rng.normal(loc=-5.0, scale=0.1, size=(100, 32))
        monitor.record_embeddings(shifted.tolist())

        report = monitor.check_drift()
        assert report["drift_detected"] is True

    def test_no_false_positives(self) -> None:
        """Same distribution does NOT trigger drift."""
        rng = np.random.default_rng(42)
        reference = rng.normal(loc=0.5, scale=0.1, size=(100, 64))

        monitor = EmbeddingMonitor(reference_embeddings=reference, drift_threshold=0.15)
        same = rng.normal(loc=0.5, scale=0.1, size=(100, 64))
        monitor.record_embeddings(same.tolist())

        report = monitor.check_drift()
        assert report["drift_detected"] is False

    def test_metrics_exported(self) -> None:
        """Drift metrics appear in Prometheus output."""
        output = get_metrics_text().decode("utf-8")
        assert "embedding_centroid_shift_cosine" in output
        assert "embedding_drift_detected" in output


class TestEC2RetrievalAlerts:
    """EC-2: Grafana alerts fire on injected quality degradation."""

    def test_critical_alert_on_quality_drop(self) -> None:
        """Canary triggers CRITICAL alert when p50 drops >10%."""
        canary = RetrievalQualityCanary(window_size=50, baseline_window_size=300)

        # Establish baseline
        for _ in range(200):
            canary.record_scores([0.75, 0.72, 0.80])

        # Inject degradation
        for _ in range(50):
            canary.record_scores([0.50, 0.45, 0.48])

        status = canary.get_status()
        assert status["alert_level"] == ALERT_CRITICAL

    def test_critical_alert_on_empty_results(self) -> None:
        """Canary triggers CRITICAL on >5% empty result rate."""
        canary = RetrievalQualityCanary(window_size=100)

        for i in range(100):
            if i < 10:
                canary.record_scores([])
            else:
                canary.record_scores([0.75, 0.72])

        status = canary.get_status()
        assert status["alert_level"] == ALERT_CRITICAL
        assert status["empty_result_rate"] > 0.05


class TestEC3RagasEval:
    """EC-3: Ragas daily eval runs (or skips gracefully)."""

    def test_daily_eval_runner_imports(self) -> None:
        """DailyEvalRunner can be imported and instantiated."""
        from src.observability.daily_eval import DailyEvalRunner

        runner = DailyEvalRunner()
        assert runner is not None

    def test_no_traces_returns_insufficient_data(self, tmp_path: Path) -> None:
        """No traces → insufficient_data report."""
        from src.observability.daily_eval import DailyEvalRunner

        runner = DailyEvalRunner(
            traces_dir=tmp_path / "empty",
            output_dir=tmp_path / "output",
        )
        report = runner.run()
        assert report["status"] == "insufficient_data"


class TestEC4UnifiedDashboard:
    """EC-4: Unified dashboard has all 5 rows operational."""

    def test_dashboard_has_5_rows(self) -> None:
        """Dashboard JSON has exactly 5 row panels."""
        dashboard_path = Path("monitoring/grafana/dashboards/pipeline-health.json")
        data = json.loads(dashboard_path.read_text())
        rows = [p for p in data["panels"] if p["type"] == "row"]
        assert len(rows) == 5

    def test_metrics_endpoint_works(self) -> None:
        """/metrics output is valid Prometheus format."""
        output = get_metrics_text()
        text = output.decode("utf-8")
        assert "# HELP" in text or "# TYPE" in text
        assert len(text) > 200


class TestEC5AlertPlaybooks:
    """EC-5: Every alert has a documented runbook."""

    def test_all_alerts_covered(self) -> None:
        """Every Prometheus alert has a matching playbook entry."""
        playbook = Path("docs/runbooks/alerting-playbooks.md").read_text()

        alerts = [
            "Retrieval Quality p50 Drop >10%",
            "Retrieval Empty Result Rate >5%",
            "HHEM Faithfulness Below Threshold",
            "Embedding Drift Detected",
            "Shadow Mode Circuit Breaker Triggered",
            "LLM Cost Spike",
            "Injection Attempt Spike",
        ]
        for alert in alerts:
            assert alert in playbook, f"Missing playbook for: {alert}"

    def test_playbook_structure(self) -> None:
        """Each playbook section has Trigger, Investigation, Remediation."""
        content = Path("docs/runbooks/alerting-playbooks.md").read_text()
        sections = re.split(r"\n## ", content)
        alert_sections = [s for s in sections if "CRITICAL:" in s or "WARN:" in s]

        assert len(alert_sections) >= 7  # at least 7 CRITICAL/WARN alerts

        for section in alert_sections:
            title = section.split("\n")[0].strip()
            assert "**Trigger:**" in section, f"'{title}' missing Trigger"
            assert "**Investigation:**" in section, f"'{title}' missing Investigation"
            assert "**Remediation:**" in section, f"'{title}' missing Remediation"
