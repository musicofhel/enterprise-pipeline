"""Central Prometheus metrics registry for the pipeline.

All pipeline components register their metrics here. The /metrics endpoint
exposes them in Prometheus text format.
"""
from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Use a dedicated registry to avoid default process/platform collectors
# that can be noisy in tests.
REGISTRY = CollectorRegistry()

# ---------------------------------------------------------------------------
# Pipeline request metrics
# ---------------------------------------------------------------------------
PIPELINE_REQUESTS_TOTAL = Counter(
    "pipeline_requests_total",
    "Total pipeline requests",
    ["route", "variant"],
    registry=REGISTRY,
)

PIPELINE_REQUEST_DURATION_SECONDS = Histogram(
    "pipeline_request_duration_seconds",
    "End-to-end pipeline request duration",
    ["route"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 3, 5, 10),
    registry=REGISTRY,
)

PIPELINE_STAGE_DURATION_SECONDS = Histogram(
    "pipeline_request_duration_per_stage_seconds",
    "Per-stage pipeline duration",
    ["stage"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
    registry=REGISTRY,
)

PIPELINE_ERRORS_TOTAL = Counter(
    "pipeline_errors_total",
    "Total pipeline errors",
    ["stage", "error_type"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Safety metrics
# ---------------------------------------------------------------------------
SAFETY_INJECTION_BLOCKED_TOTAL = Counter(
    "safety_injection_blocked_total",
    "Injection attempts blocked",
    ["layer"],
    registry=REGISTRY,
)

SAFETY_PII_DETECTED_TOTAL = Counter(
    "safety_pii_detected_total",
    "PII detections",
    ["pii_type"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Quality metrics (HHEM)
# ---------------------------------------------------------------------------
HALLUCINATION_SCORE = Histogram(
    "hallucination_score",
    "HHEM faithfulness score distribution",
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0),
    registry=REGISTRY,
)

HALLUCINATION_CHECK_FAILED_TOTAL = Counter(
    "hallucination_check_failed_total",
    "Hallucination checks that failed threshold",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Cost metrics
# ---------------------------------------------------------------------------
LLM_COST_USD_TOTAL = Counter(
    "llm_cost_usd_total",
    "Total LLM API cost in USD",
    ["model", "route"],
    registry=REGISTRY,
)

LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "Total LLM tokens used",
    ["direction", "model"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Embedding drift metrics (6.1)
# ---------------------------------------------------------------------------
EMBEDDING_CENTROID_SHIFT = Gauge(
    "embedding_centroid_shift_cosine",
    "Cosine distance from reference centroid",
    registry=REGISTRY,
)

EMBEDDING_SPREAD_CHANGE = Gauge(
    "embedding_spread_change",
    "Change in embedding spread vs reference",
    registry=REGISTRY,
)

EMBEDDING_DRIFT_DETECTED = Gauge(
    "embedding_drift_detected",
    "Whether embedding drift is detected (0 or 1)",
    registry=REGISTRY,
)

EMBEDDING_SAMPLE_COUNT = Counter(
    "embedding_sample_count",
    "Total embeddings tracked",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Retrieval quality canary metrics (6.2)
# ---------------------------------------------------------------------------
RETRIEVAL_COSINE_SIM_P50 = Gauge(
    "retrieval_cosine_sim_p50",
    "Retrieval cosine similarity p50",
    registry=REGISTRY,
)

RETRIEVAL_COSINE_SIM_P95 = Gauge(
    "retrieval_cosine_sim_p95",
    "Retrieval cosine similarity p95",
    registry=REGISTRY,
)

RETRIEVAL_COSINE_SIM_MEAN = Gauge(
    "retrieval_cosine_sim_mean",
    "Retrieval cosine similarity mean",
    registry=REGISTRY,
)

RETRIEVAL_RESULT_COUNT_AVG = Gauge(
    "retrieval_result_count_avg",
    "Average retrieval result count",
    registry=REGISTRY,
)

RETRIEVAL_EMPTY_RESULT_RATE = Gauge(
    "retrieval_empty_result_rate",
    "Fraction of queries with 0 results",
    registry=REGISTRY,
)

RETRIEVAL_QUALITY_ALERT_LEVEL = Gauge(
    "retrieval_quality_alert_level",
    "Retrieval quality alert level: 0=ok, 1=warn, 2=critical",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Ragas daily eval metrics (6.3)
# ---------------------------------------------------------------------------
RAGAS_FAITHFULNESS_DAILY = Gauge(
    "ragas_faithfulness_daily",
    "Mean faithfulness from last Ragas eval",
    registry=REGISTRY,
)

RAGAS_CONTEXT_PRECISION_DAILY = Gauge(
    "ragas_context_precision_daily",
    "Mean context precision from last Ragas eval",
    registry=REGISTRY,
)

RAGAS_ANSWER_RELEVANCY_DAILY = Gauge(
    "ragas_answer_relevancy_daily",
    "Mean answer relevancy from last Ragas eval",
    registry=REGISTRY,
)

RAGAS_EVAL_SAMPLE_SIZE = Gauge(
    "ragas_eval_sample_size",
    "Number of traces evaluated in last Ragas run",
    registry=REGISTRY,
)

RAGAS_EVAL_LAST_RUN_TIMESTAMP = Gauge(
    "ragas_eval_last_run_timestamp",
    "Unix timestamp of last Ragas eval run",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Experimentation metrics (from Wave 5)
# ---------------------------------------------------------------------------
EXPERIMENT_VARIANT_ASSIGNMENT_TOTAL = Counter(
    "experiment_variant_assignment_total",
    "Feature flag variant assignments",
    ["variant"],
    registry=REGISTRY,
)

SHADOW_MODE_RUNS_TOTAL = Counter(
    "shadow_mode_runs_total",
    "Shadow mode pipeline runs",
    registry=REGISTRY,
)

SHADOW_MODE_BUDGET_REMAINING_USD = Gauge(
    "shadow_mode_budget_remaining_usd",
    "Shadow mode budget remaining in USD",
    registry=REGISTRY,
)


def get_metrics_text() -> bytes:
    """Generate Prometheus text format output from the registry."""
    return generate_latest(REGISTRY)
