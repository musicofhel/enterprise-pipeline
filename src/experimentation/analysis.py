"""Experiment analyzer — statistical comparison of control vs treatment traces.

Uses scipy for parametric (t-test) and non-parametric (Mann-Whitney U) tests,
plus Cohen's d for effect size estimation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class ExperimentAnalyzer:
    """Analyze experiment results from local trace files."""

    def __init__(self, traces_dir: Path = Path("traces/local")) -> None:
        self._traces_dir = traces_dir

    def load_traces_by_variant(self) -> dict[str, list[dict[str, Any]]]:
        """Read trace JSON files, group by feature_flags.pipeline_variant."""
        groups: dict[str, list[dict[str, Any]]] = {}

        if not self._traces_dir.exists():
            logger.warning("traces_dir_not_found", path=str(self._traces_dir))
            return groups

        for trace_path in self._traces_dir.glob("*.json"):
            try:
                data: dict[str, Any] = json.loads(trace_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            variant = data.get("feature_flags", {}).get("pipeline_variant", "control")
            groups.setdefault(variant, []).append(data)

        return groups

    @staticmethod
    def compute_metrics(traces: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute summary metrics from a list of traces."""
        latencies = [t.get("total_latency_ms", 0) for t in traces]
        costs = [t.get("total_cost_usd", 0) for t in traces]
        faithfulness_scores = [
            t.get("scores", {}).get("faithfulness")
            for t in traces
            if t.get("scores", {}).get("faithfulness") is not None
        ]

        def _mean(vals: list[float]) -> float | None:
            return sum(vals) / len(vals) if vals else None

        def _percentile(vals: list[float], pct: float) -> float | None:
            if not vals:
                return None
            s = sorted(vals)
            idx = int(len(s) * pct / 100)
            return s[min(idx, len(s) - 1)]

        return {
            "count": len(traces),
            "faithfulness_mean": _mean(faithfulness_scores),
            "latency_p50_ms": _percentile(latencies, 50),
            "latency_p95_ms": _percentile(latencies, 95),
            "cost_total_usd": sum(costs),
        }

    @staticmethod
    def run_statistical_test(
        control_values: list[float],
        treatment_values: list[float],
    ) -> dict[str, Any]:
        """Run t-test, Mann-Whitney U, and compute Cohen's d."""
        from scipy import stats

        result: dict[str, Any] = {
            "control_n": len(control_values),
            "treatment_n": len(treatment_values),
        }

        if len(control_values) < 2 or len(treatment_values) < 2:
            result["error"] = "Insufficient samples for statistical testing"
            return result

        # Welch's t-test (unequal variances)
        t_stat, t_pvalue = stats.ttest_ind(control_values, treatment_values, equal_var=False)
        result["ttest_statistic"] = round(float(t_stat), 4)
        result["ttest_pvalue"] = round(float(t_pvalue), 6)

        # Mann-Whitney U (non-parametric)
        u_stat, u_pvalue = stats.mannwhitneyu(
            control_values, treatment_values, alternative="two-sided"
        )
        result["mannwhitney_statistic"] = round(float(u_stat), 4)
        result["mannwhitney_pvalue"] = round(float(u_pvalue), 6)

        # Cohen's d (effect size)
        import math

        mean_c = sum(control_values) / len(control_values)
        mean_t = sum(treatment_values) / len(treatment_values)
        var_c = sum((x - mean_c) ** 2 for x in control_values) / (len(control_values) - 1)
        var_t = sum((x - mean_t) ** 2 for x in treatment_values) / (len(treatment_values) - 1)
        pooled_std = math.sqrt(
            ((len(control_values) - 1) * var_c + (len(treatment_values) - 1) * var_t)
            / (len(control_values) + len(treatment_values) - 2)
        )
        cohens_d = (mean_t - mean_c) / pooled_std if pooled_std > 0 else 0.0
        result["cohens_d"] = round(cohens_d, 4)

        # Interpret
        result["significant_005"] = bool(t_pvalue < 0.05)
        if abs(cohens_d) < 0.2:
            result["effect_size"] = "negligible"
        elif abs(cohens_d) < 0.5:
            result["effect_size"] = "small"
        elif abs(cohens_d) < 0.8:
            result["effect_size"] = "medium"
        else:
            result["effect_size"] = "large"

        return result

    def analyze(self, min_traces: int = 30) -> dict[str, Any]:
        """Full experiment analysis with recommendation."""
        groups = self.load_traces_by_variant()

        if not groups:
            return {"status": "no_data", "message": "No trace files found"}

        report: dict[str, Any] = {"variants": {}}

        for variant, traces in groups.items():
            report["variants"][variant] = self.compute_metrics(traces)

        # Statistical comparison if we have control + at least one treatment
        control_traces = groups.get("control", [])
        treatment_variants = [k for k in groups if k != "control" and k != "shadow"]

        report["statistical_tests"] = {}

        for tv in treatment_variants:
            treatment_traces = groups[tv]

            if len(control_traces) < min_traces or len(treatment_traces) < min_traces:
                report["statistical_tests"][tv] = {
                    "status": "insufficient_data",
                    "control_n": len(control_traces),
                    "treatment_n": len(treatment_traces),
                    "min_required": min_traces,
                }
                continue

            # Compare faithfulness scores
            control_faith = [
                t.get("scores", {}).get("faithfulness", 0)
                for t in control_traces
                if t.get("scores", {}).get("faithfulness") is not None
            ]
            treatment_faith = [
                t.get("scores", {}).get("faithfulness", 0)
                for t in treatment_traces
                if t.get("scores", {}).get("faithfulness") is not None
            ]

            if len(control_faith) >= 2 and len(treatment_faith) >= 2:
                report["statistical_tests"][tv] = self.run_statistical_test(
                    control_faith, treatment_faith
                )
            else:
                report["statistical_tests"][tv] = {
                    "status": "insufficient_scored_traces",
                }

        # Recommendation
        report["recommendation"] = self._make_recommendation(report)

        return report

    @staticmethod
    def _make_recommendation(report: dict[str, Any]) -> str:
        """Generate a human-readable recommendation."""
        tests = report.get("statistical_tests", {})
        if not tests:
            return "No statistical tests performed — collect more data."

        for variant, result in tests.items():
            if result.get("status") in ("insufficient_data", "insufficient_scored_traces"):
                return f"Insufficient data for {variant} — collect more traces."

            if result.get("significant_005"):
                d = result.get("cohens_d", 0)
                if d > 0:
                    return f"Treatment '{variant}' shows significant improvement (d={d:.2f}). Consider promoting."
                return f"Treatment '{variant}' shows significant regression (d={d:.2f}). Do NOT promote."

        return "No significant difference detected. Continue collecting data or try a different treatment."
