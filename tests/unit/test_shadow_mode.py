"""Tests for shadow mode runner — 10 tests."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from src.config.pipeline_config import ShadowModeConfig
from src.experimentation.shadow_mode import ShadowComparison, ShadowRunner, load_shadow_traces
from src.observability.audit_log import AuditLogService
from src.observability.tracing import TracingService


@pytest.fixture
def shadow_config() -> ShadowModeConfig:
    return ShadowModeConfig(
        enabled=True,
        candidate_model="anthropic/claude-haiku-4-5",
        sample_rate=1.0,  # always sample for tests
        budget_limit_usd=10.0,
        circuit_breaker_latency_multiplier=3.0,
    )


@pytest.fixture
def tracing() -> TracingService:
    return TracingService(client=None, local_fallback=True)


@pytest.fixture
def audit_log(tmp_path: Path) -> AuditLogService:
    return AuditLogService(storage_dir=tmp_path / "audit")


@pytest.fixture
def mock_llm() -> MagicMock:
    llm = MagicMock()
    llm._model = "anthropic/claude-haiku-4-5"
    llm.generate = AsyncMock(return_value={
        "answer": "Shadow answer",
        "model": "anthropic/claude-haiku-4-5",
        "tokens_in": 100,
        "tokens_out": 50,
    })
    return llm


@pytest.fixture
def runner(
    mock_llm: MagicMock,
    tracing: TracingService,
    shadow_config: ShadowModeConfig,
    audit_log: AuditLogService,
) -> ShadowRunner:
    return ShadowRunner(
        llm_client=mock_llm,
        tracing=tracing,
        config=shadow_config,
        audit_log=audit_log,
    )


class TestShadowRunner:
    def test_disabled_returns_none(
        self, mock_llm: MagicMock, tracing: TracingService, audit_log: AuditLogService
    ) -> None:
        config = ShadowModeConfig(enabled=False)
        runner = ShadowRunner(mock_llm, tracing, config, audit_log)
        result = runner.maybe_run("query", {}, [], "user-1")
        assert result is None

    def test_budget_exhausted_returns_none(self, runner: ShadowRunner) -> None:
        runner._budget_spent_usd = 999.0  # way over budget
        result = runner.maybe_run("query", {}, [], "user-1")
        assert result is None

    def test_circuit_breaker_trips(self, runner: ShadowRunner) -> None:
        # Simulate shadow being 5x slower than primary
        runner._primary_latencies = [100.0] * 10
        runner._shadow_latencies = [1000.0] * 10
        assert runner._check_circuit_breaker() is False
        assert runner.circuit_open is True

    def test_circuit_breaker_ok(self, runner: ShadowRunner) -> None:
        runner._primary_latencies = [100.0] * 10
        runner._shadow_latencies = [150.0] * 10  # well within 3x
        assert runner._check_circuit_breaker() is True
        assert runner.circuit_open is False

    @pytest.mark.asyncio
    async def test_maybe_run_creates_task(self, runner: ShadowRunner) -> None:
        task = runner.maybe_run("test query", {"answer": "primary"}, [], "user-1")
        assert task is not None
        assert isinstance(task, asyncio.Task)
        # Clean up
        task.cancel()

    def test_record_primary_latency(self, runner: ShadowRunner) -> None:
        runner.record_primary_latency(150.0)
        runner.record_primary_latency(200.0)
        assert len(runner._primary_latencies) == 2
        assert runner._primary_latencies == [150.0, 200.0]

    @pytest.mark.asyncio
    async def test_run_shadow_calls_llm(self, runner: ShadowRunner, mock_llm: MagicMock) -> None:
        await runner._run_shadow("test query", {"answer": "primary"}, [], "user-1")
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_shadow_updates_budget(self, runner: ShadowRunner) -> None:
        assert runner.budget_spent_usd == 0.0
        await runner._run_shadow("test query", {"answer": "primary"}, [], "user-1")
        assert runner.budget_spent_usd > 0.0

    def test_sample_rate_zero_skips(
        self, mock_llm: MagicMock, tracing: TracingService, audit_log: AuditLogService
    ) -> None:
        config = ShadowModeConfig(enabled=True, sample_rate=0.0)
        runner = ShadowRunner(mock_llm, tracing, config, audit_log)
        # With sample_rate=0, should never sample
        results = [runner.maybe_run("q", {}, [], "u") for _ in range(100)]
        assert all(r is None for r in results)

    @pytest.mark.asyncio
    async def test_run_shadow_handles_llm_error(self, runner: ShadowRunner, mock_llm: MagicMock) -> None:
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM failed"))
        # Should not raise — shadow failures are swallowed
        await runner._run_shadow("test query", {}, [], "user-1")


class TestShadowComparison:
    def test_compare_empty(self) -> None:
        result = ShadowComparison.compare([], [])
        assert result["primary"]["count"] == 0
        assert result["shadow"]["count"] == 0

    def test_compare_with_traces(self) -> None:
        primary = [
            {"total_latency_ms": 100, "total_cost_usd": 0.01, "scores": {"faithfulness": 0.9}},
            {"total_latency_ms": 200, "total_cost_usd": 0.02, "scores": {"faithfulness": 0.8}},
        ]
        shadow = [
            {"total_latency_ms": 150, "total_cost_usd": 0.005, "scores": {"faithfulness": 0.85}},
        ]
        result = ShadowComparison.compare(primary, shadow)
        assert result["primary"]["count"] == 2
        assert result["shadow"]["count"] == 1
        assert result["primary"]["faithfulness_mean"] == pytest.approx(0.85)
        assert result["shadow"]["faithfulness_mean"] == pytest.approx(0.85)


class TestLoadShadowTraces:
    def test_empty_dir(self, tmp_path: Path) -> None:
        primary, shadow = load_shadow_traces(tmp_path / "empty")
        assert primary == []
        assert shadow == []

    def test_splits_by_variant(self, tmp_path: Path) -> None:
        import json

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        (traces_dir / "ctrl.json").write_text(json.dumps({
            "feature_flags": {"pipeline_variant": "control"},
            "total_latency_ms": 100,
        }))
        (traces_dir / "shadow.json").write_text(json.dumps({
            "feature_flags": {"pipeline_variant": "shadow"},
            "total_latency_ms": 200,
        }))

        primary, shadow = load_shadow_traces(traces_dir)
        assert len(primary) == 1
        assert len(shadow) == 1
