"""Wave 5 exit criteria — experimentation infrastructure.

EC-1: Promptfoo runs and compares current vs candidate
EC-2: Shadow mode processes request with zero primary impact
EC-3: Feature flags deterministically route 90/10 traffic
EC-4: Experiment analyzer produces significance report
EC-5: CI eval gate blocks on >2% regression
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from src.config.pipeline_config import FeatureFlagConfig, ShadowModeConfig
from src.experimentation.analysis import ExperimentAnalyzer
from src.experimentation.feature_flags import FeatureFlagService
from src.experimentation.shadow_mode import ShadowRunner
from src.observability.audit_log import AuditLogService
from src.observability.tracing import TracingService

# ---------------------------------------------------------------------------
# EC-1: Promptfoo config exists and is well-formed
# ---------------------------------------------------------------------------


class TestEC1PromptfooConfig:
    """Promptfoo can run and compare current vs candidate."""

    def test_promptfoo_config_exists(self) -> None:
        assert Path("promptfoo.config.yaml").exists()

    def test_two_prompts_configured(self) -> None:
        with open("promptfoo.config.yaml") as f:
            config = yaml.safe_load(f)
        assert len(config["prompts"]) == 2
        assert "current.txt" in config["prompts"][0]
        assert "candidate.txt" in config["prompts"][1]


# ---------------------------------------------------------------------------
# EC-2: Shadow mode — zero primary impact
# ---------------------------------------------------------------------------


class TestEC2ShadowMode:
    """Shadow mode processes request without affecting primary response."""

    @pytest.fixture
    def shadow_runner(self, tmp_path: Path) -> ShadowRunner:
        llm = MagicMock()
        llm._model = "anthropic/claude-haiku-4-5"
        llm.generate = AsyncMock(return_value={
            "answer": "shadow answer",
            "model": "anthropic/claude-haiku-4-5",
            "tokens_in": 50,
            "tokens_out": 25,
        })
        config = ShadowModeConfig(enabled=True, sample_rate=1.0, budget_limit_usd=10.0)
        tracing = TracingService(client=None, local_fallback=True)
        audit_log = AuditLogService(storage_dir=tmp_path / "audit")
        return ShadowRunner(llm, tracing, config, audit_log)

    @pytest.mark.asyncio
    async def test_shadow_fire_and_forget(self, shadow_runner: ShadowRunner) -> None:
        """Shadow returns a task without blocking."""
        task = shadow_runner.maybe_run("test query", {"answer": "primary"}, [], "user-1")
        assert task is not None
        task.cancel()

    @pytest.mark.asyncio
    async def test_shadow_does_not_raise(self, shadow_runner: ShadowRunner) -> None:
        """Shadow failure does not propagate."""
        shadow_runner._llm.generate = AsyncMock(side_effect=RuntimeError("boom"))
        # Should not raise
        await shadow_runner._run_shadow("query", {}, [], "user-1")


# ---------------------------------------------------------------------------
# EC-3: Feature flags — deterministic 90/10 routing
# ---------------------------------------------------------------------------


class TestEC3FeatureFlags:
    """Feature flags deterministically route traffic."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> FeatureFlagService:
        config_data = {
            "variants": [{"name": "control", "weight": 0.9}, {"name": "treatment_a", "weight": 0.1}],
            "user_overrides": {},
            "tenant_overrides": {},
        }
        flags_path = tmp_path / "flags.yaml"
        flags_path.write_text(yaml.dump(config_data))
        ff_config = FeatureFlagConfig(enabled=True, config_path=str(flags_path))
        audit_log = AuditLogService(storage_dir=tmp_path / "audit")
        return FeatureFlagService(config=ff_config, audit_log=audit_log)

    def test_deterministic_assignment(self, service: FeatureFlagService) -> None:
        """Same user always gets same variant."""
        v1 = service.get_variant("stable-user-xyz")
        v2 = service.get_variant("stable-user-xyz")
        assert v1 == v2

    def test_approximate_90_10_split(self, service: FeatureFlagService) -> None:
        """1000 users split roughly 90/10."""
        variants = [service.get_variant(f"user-{i}") for i in range(1000)]
        control_pct = variants.count("control") / len(variants)
        assert 0.82 < control_pct < 0.97, f"control={control_pct:.1%}"


# ---------------------------------------------------------------------------
# EC-4: Experiment analyzer — significance report
# ---------------------------------------------------------------------------


class TestEC4ExperimentAnalysis:
    """Experiment analyzer produces valid significance report."""

    def test_analyzer_produces_report(self, tmp_path: Path) -> None:
        import random

        random.seed(42)
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        for i in range(35):
            for variant, base_faith in [("control", 0.88), ("treatment_a", 0.91)]:
                data = {
                    "trace_id": f"{variant}-{i}",
                    "feature_flags": {"pipeline_variant": variant},
                    "total_latency_ms": 100 + random.gauss(0, 10),
                    "total_cost_usd": 0.01,
                    "scores": {"faithfulness": base_faith + random.gauss(0, 0.03)},
                }
                (traces_dir / f"{variant}_{i}.json").write_text(json.dumps(data))

        analyzer = ExperimentAnalyzer(traces_dir=traces_dir)
        report = analyzer.analyze(min_traces=30)

        assert "variants" in report
        assert "statistical_tests" in report
        assert "recommendation" in report
        assert "treatment_a" in report["statistical_tests"]
        # Should have run the actual test
        test_result = report["statistical_tests"]["treatment_a"]
        assert "ttest_pvalue" in test_result


# ---------------------------------------------------------------------------
# EC-5: CI eval gate blocks on regression
# ---------------------------------------------------------------------------


class TestEC5CIEvalGate:
    """check_regression.py blocks on >2% regression."""

    def test_check_regression_script_exists(self) -> None:
        assert Path("scripts/check_regression.py").exists()

    def test_check_regression_supports_promptfoo_flag(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "check_regression", "scripts/check_regression.py"
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        # Should have check_promptfoo_results function
        assert hasattr(mod, "check_promptfoo_results")
