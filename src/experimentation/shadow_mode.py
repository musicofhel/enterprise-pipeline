"""Shadow mode — fire-and-forget candidate pipeline execution.

Reuses the same retrieval results from the primary path. Only the generation
step (different model/prompt) runs in the background via asyncio.create_task().
"""
from __future__ import annotations

import asyncio
import random
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.config.pipeline_config import ShadowModeConfig
    from src.observability.audit_log import AuditLogService
    from src.observability.tracing import TracingService
    from src.pipeline.generation.llm_client import LLMClient

logger = structlog.get_logger()


class ShadowRunner:
    """Run a shadow (candidate) pipeline in the background.

    The shadow runner reuses retrieval results from the primary path and only
    re-runs generation with a different model/prompt. Results are traced with
    variant="shadow" for later analysis.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tracing: TracingService,
        config: ShadowModeConfig,
        audit_log: AuditLogService,
    ) -> None:
        self._llm = llm_client
        self._tracing = tracing
        self._config = config
        self._audit_log = audit_log
        self._budget_spent_usd: float = 0.0
        self._primary_latencies: list[float] = []
        self._shadow_latencies: list[float] = []
        self._circuit_open: bool = False

    @property
    def budget_spent_usd(self) -> float:
        return self._budget_spent_usd

    @property
    def circuit_open(self) -> bool:
        return self._circuit_open

    def record_primary_latency(self, latency_ms: float) -> None:
        """Track primary path latency for circuit breaker comparison."""
        self._primary_latencies.append(latency_ms)
        # Keep a rolling window of 100
        if len(self._primary_latencies) > 100:
            self._primary_latencies = self._primary_latencies[-100:]

    def _check_circuit_breaker(self) -> bool:
        """Return True if circuit is OK (closed), False if tripped (open)."""
        if not self._shadow_latencies or not self._primary_latencies:
            return True

        avg_primary = sum(self._primary_latencies) / len(self._primary_latencies)
        avg_shadow = sum(self._shadow_latencies) / len(self._shadow_latencies)

        multiplier = self._config.circuit_breaker_latency_multiplier
        if avg_shadow > avg_primary * multiplier:
            logger.warning(
                "shadow_circuit_breaker_tripped",
                avg_primary_ms=round(avg_primary, 2),
                avg_shadow_ms=round(avg_shadow, 2),
                multiplier=multiplier,
            )
            self._circuit_open = True
            return False
        self._circuit_open = False
        return True

    def _check_budget(self) -> bool:
        """Return True if budget is available."""
        return self._budget_spent_usd < self._config.budget_limit_usd

    def _should_sample(self) -> bool:
        """Return True if this request should be sampled for shadow execution."""
        return random.random() < self._config.sample_rate

    def maybe_run(
        self,
        request_query: str,
        primary_response: dict[str, Any],
        context_chunks: list[dict[str, Any]],
        user_id: str,
        tenant_id: str | None = None,
    ) -> asyncio.Task[None] | None:
        """If enabled + budget + circuit OK + sampled, fire shadow task."""
        if not self._config.enabled:
            return None

        if not self._check_budget():
            logger.info("shadow_skipped", reason="budget_exhausted")
            return None

        if not self._check_circuit_breaker():
            logger.info("shadow_skipped", reason="circuit_breaker_open")
            return None

        if not self._should_sample():
            return None

        task = asyncio.create_task(
            self._run_shadow(
                request_query=request_query,
                primary_response=primary_response,
                context_chunks=context_chunks,
                user_id=user_id,
                tenant_id=tenant_id,
            )
        )
        logger.info("shadow_task_created", query=request_query[:100])
        return task

    async def _run_shadow(
        self,
        request_query: str,
        primary_response: dict[str, Any],
        context_chunks: list[dict[str, Any]],
        user_id: str,
        tenant_id: str | None = None,
    ) -> None:
        """Execute shadow generation and log trace."""
        start = time.monotonic()

        try:
            trace = self._tracing.create_trace(
                name="pipeline_query_shadow",
                user_id=user_id,
                metadata={"tenant_id": tenant_id},
                variant="shadow",
            )

            with trace.generation(
                name="shadow_generation",
                model=self._llm._model,
                input=request_query,
            ) as gen:
                result = await self._llm.generate(
                    query=request_query,
                    context_chunks=context_chunks,
                )
                gen.set_output(
                    result["answer"],
                    usage={
                        "input": result["tokens_in"],
                        "output": result["tokens_out"],
                    },
                )

            latency_ms = (time.monotonic() - start) * 1000
            self._shadow_latencies.append(latency_ms)
            if len(self._shadow_latencies) > 100:
                self._shadow_latencies = self._shadow_latencies[-100:]

            # Estimate cost (rough: $3/M input, $15/M output for Sonnet)
            cost = (result["tokens_in"] * 3 + result["tokens_out"] * 15) / 1_000_000
            self._budget_spent_usd += cost

            trace.save_local()

            logger.info(
                "shadow_completed",
                latency_ms=round(latency_ms, 2),
                cost_usd=round(cost, 6),
                budget_remaining=round(self._config.budget_limit_usd - self._budget_spent_usd, 4),
            )

        except Exception:
            logger.exception("shadow_execution_failed")


class ShadowComparison:
    """Compare primary and shadow trace outputs."""

    @staticmethod
    def compare(
        primary_traces: list[dict[str, Any]],
        shadow_traces: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Produce a comparison report from two sets of traces."""
        primary_latencies = [t.get("total_latency_ms", 0) for t in primary_traces]
        shadow_latencies = [t.get("total_latency_ms", 0) for t in shadow_traces]

        primary_costs = [t.get("total_cost_usd", 0) for t in primary_traces]
        shadow_costs = [t.get("total_cost_usd", 0) for t in shadow_traces]

        primary_faithfulness = [
            t.get("scores", {}).get("faithfulness")
            for t in primary_traces
            if t.get("scores", {}).get("faithfulness") is not None
        ]
        shadow_faithfulness = [
            t.get("scores", {}).get("faithfulness")
            for t in shadow_traces
            if t.get("scores", {}).get("faithfulness") is not None
        ]

        def _safe_mean(values: list[float]) -> float | None:
            return sum(values) / len(values) if values else None

        def _safe_p95(values: list[float]) -> float | None:
            if not values:
                return None
            s = sorted(values)
            idx = int(len(s) * 0.95)
            return s[min(idx, len(s) - 1)]

        return {
            "primary": {
                "count": len(primary_traces),
                "latency_mean_ms": _safe_mean(primary_latencies),
                "latency_p95_ms": _safe_p95(primary_latencies),
                "cost_total_usd": sum(primary_costs),
                "faithfulness_mean": _safe_mean(primary_faithfulness),
            },
            "shadow": {
                "count": len(shadow_traces),
                "latency_mean_ms": _safe_mean(shadow_latencies),
                "latency_p95_ms": _safe_p95(shadow_latencies),
                "cost_total_usd": sum(shadow_costs),
                "faithfulness_mean": _safe_mean(shadow_faithfulness),
            },
        }


def load_shadow_traces(traces_dir: Path = Path("traces/local")) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load and split traces into primary and shadow groups."""
    import json

    primary: list[dict[str, Any]] = []
    shadow: list[dict[str, Any]] = []

    if not traces_dir.exists():
        return primary, shadow

    for trace_path in traces_dir.glob("*.json"):
        try:
            data: dict[str, Any] = json.loads(trace_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        variant = data.get("feature_flags", {}).get("pipeline_variant", "control")
        if variant == "shadow":
            shadow.append(data)
        else:
            primary.append(data)

    return primary, shadow
