"""Pipeline instrumentation — updates Prometheus metrics from pipeline events.

This module provides a lightweight `PipelineInstrumentation` class that the
orchestrator calls at key points. Keeps metric-update logic out of the
orchestrator itself.
"""
from __future__ import annotations

from src.observability.metrics import (
    EXPERIMENT_VARIANT_ASSIGNMENT_TOTAL,
    HALLUCINATION_CHECK_FAILED_TOTAL,
    HALLUCINATION_SCORE,
    LLM_COST_USD_TOTAL,
    LLM_TOKENS_TOTAL,
    PIPELINE_ERRORS_TOTAL,
    PIPELINE_REQUEST_DURATION_SECONDS,
    PIPELINE_REQUESTS_TOTAL,
    PIPELINE_STAGE_DURATION_SECONDS,
    SAFETY_INJECTION_BLOCKED_TOTAL,
    SAFETY_PII_DETECTED_TOTAL,
    SHADOW_MODE_RUNS_TOTAL,
)


class PipelineInstrumentation:
    """Update Prometheus metrics for pipeline events."""

    @staticmethod
    def record_request(route: str, variant: str, duration_seconds: float) -> None:
        PIPELINE_REQUESTS_TOTAL.labels(route=route, variant=variant).inc()
        PIPELINE_REQUEST_DURATION_SECONDS.labels(route=route).observe(duration_seconds)

    @staticmethod
    def record_stage(stage: str, duration_seconds: float) -> None:
        PIPELINE_STAGE_DURATION_SECONDS.labels(stage=stage).observe(duration_seconds)

    @staticmethod
    def record_error(stage: str, error_type: str) -> None:
        PIPELINE_ERRORS_TOTAL.labels(stage=stage, error_type=error_type).inc()

    @staticmethod
    def record_safety_block(layer: str) -> None:
        SAFETY_INJECTION_BLOCKED_TOTAL.labels(layer=layer).inc()

    @staticmethod
    def record_pii_detection(pii_type: str) -> None:
        SAFETY_PII_DETECTED_TOTAL.labels(pii_type=pii_type).inc()

    @staticmethod
    def record_hallucination(score: float, passed: bool) -> None:
        HALLUCINATION_SCORE.observe(score)
        if not passed:
            HALLUCINATION_CHECK_FAILED_TOTAL.inc()

    @staticmethod
    def record_generation(model: str, route: str, tokens_in: int, tokens_out: int, cost_usd: float) -> None:
        LLM_TOKENS_TOTAL.labels(direction="in", model=model).inc(tokens_in)
        LLM_TOKENS_TOTAL.labels(direction="out", model=model).inc(tokens_out)
        LLM_COST_USD_TOTAL.labels(model=model, route=route).inc(cost_usd)

    @staticmethod
    def record_variant_assignment(variant: str) -> None:
        EXPERIMENT_VARIANT_ASSIGNMENT_TOTAL.labels(variant=variant).inc()

    @staticmethod
    def record_shadow_run() -> None:
        SHADOW_MODE_RUNS_TOTAL.inc()
