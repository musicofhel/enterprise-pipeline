"""Tests for HallucinationChecker with REAL HHEM model inference.

These tests load the actual vectara/hallucination_evaluation_model and run
inference on CPU. The model is ~600MB and is cached after first download.

All tests run with the real model — no mocks.
"""
from __future__ import annotations

import pytest

from src.pipeline.quality import HallucinationChecker

# Shared checker instance — reuses the cached model across tests.
# `max` aggregation: "is the answer supported by at least one chunk?"
# This is appropriate for RAG where retrieval returns mixed-relevance chunks.
_checker = HallucinationChecker(
    threshold_pass=0.85,
    threshold_warn=0.70,
    aggregation_method="max",
)


# --- Realistic context chunks for testing ---

REMOTE_WORK_CONTEXT = [
    (
        "Section 4.2 — International Remote Work. Employees based outside the home country "
        "may request remote work arrangements subject to local labor law compliance. The "
        "company will conduct a tax nexus analysis for any employee working from a foreign "
        "jurisdiction for more than 30 cumulative days per calendar year. Requests must be "
        "submitted through the HR portal at least 60 days in advance."
    ),
    (
        "Remote work equipment stipend: Employees approved for full-time remote work "
        "receive a one-time $1,500 equipment stipend and a monthly $75 internet "
        "reimbursement. International employees receive equivalent local-currency amounts "
        "based on the exchange rate at time of approval. The stipend covers desk, chair, "
        "monitor, and ergonomic accessories."
    ),
    (
        "Section 4.4 — International Remote Work Tax Implications. Employees working "
        "remotely from a foreign jurisdiction may create a permanent establishment risk. "
        "The company retains Ernst & Young for cross-border tax advisory. Employees must "
        "report any foreign work periods exceeding 14 days to HR and Tax within 5 business "
        "days of return."
    ),
]

FINANCIAL_CONTEXT = [
    (
        "Q3 2025 Revenue Report: Total revenue was $142.3 million, a 12% increase "
        "year-over-year. Operating margins improved to 23.4%, up from 21.1% in Q2. "
        "APAC region contributed 34% of total revenue, up from 28% in the prior year."
    ),
    (
        "Cost structure: R&D spending was $31.2 million (22% of revenue), up from "
        "$27.8 million in Q3 2024. Sales and marketing was $18.7 million. General and "
        "administrative expenses decreased 3% due to office consolidation in EMEA."
    ),
]


@pytest.mark.asyncio
async def test_grounded_response_scores_high():
    """Answer clearly supported by context should score >= 0.85 (PASS)."""
    answer = (
        "International employees can request remote work arrangements, but must comply "
        "with local labor laws. If working from a foreign country for more than 30 days "
        "per year, the company will conduct a tax nexus analysis. Requests must be "
        "submitted 60 days in advance through the HR portal."
    )
    result = await _checker.check(answer, REMOTE_WORK_CONTEXT)

    assert result["level"] == "pass", (
        f"Expected 'pass' for grounded answer, got '{result['level']}' "
        f"(score={result['score']:.4f}, per_chunk={result['per_chunk_scores']})"
    )
    assert result["score"] >= 0.85
    assert result["passed"] is True
    assert result["model"] == "vectara/hallucination_evaluation_model"
    assert len(result["per_chunk_scores"]) == 3


@pytest.mark.asyncio
async def test_hallucinated_response_scores_low():
    """Answer that contradicts or invents facts should score < 0.70 (FAIL)."""
    answer = (
        "The company does not allow any form of remote work for international employees. "
        "All staff must report to the headquarters office in person, 5 days a week. "
        "There is no equipment stipend and no internet reimbursement is provided. "
        "Tax implications are the sole responsibility of the employee with no company support."
    )
    result = await _checker.check(answer, REMOTE_WORK_CONTEXT)

    assert result["level"] == "fail", (
        f"Expected 'fail' for hallucinated answer, got '{result['level']}' "
        f"(score={result['score']:.4f})"
    )
    assert result["score"] < 0.70
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_partially_grounded_response():
    """Answer with some correct and some invented claims — score below pass threshold."""
    # Mixes real facts (stipend amount) with fabricated ones (compliance fee, 90-day cap)
    answer = (
        "Remote employees receive a $1,500 equipment stipend. However, the company charges "
        "a mandatory $500 monthly compliance fee that is deducted from salary for all "
        "international remote workers, and remote work is strictly capped at 90 days total."
    )
    result = await _checker.check(answer, REMOTE_WORK_CONTEXT)

    # The stipend part is grounded, the compliance fee and 90-day cap are invented.
    assert result["score"] < 0.85, (
        f"Partially grounded answer scored too high: {result['score']:.4f}"
    )
    assert result["level"] in ("warn", "fail")


@pytest.mark.asyncio
async def test_empty_context_returns_fail():
    """Empty context means we can't verify anything — should fail."""
    result = await _checker.check("Some answer about remote work.", [])
    assert result["level"] == "fail"
    assert result["score"] == 0.0
    assert result["passed"] is False
    assert result["per_chunk_scores"] == []

    # Also test empty string
    result2 = await _checker.check("Some answer.", "")
    assert result2["level"] == "fail"

    # Empty answer
    result3 = await _checker.check("", REMOTE_WORK_CONTEXT)
    assert result3["level"] == "fail"


@pytest.mark.asyncio
async def test_threshold_configuration():
    """Changing thresholds should change the level classification."""
    answer = (
        "International employees can request remote work. The company conducts tax "
        "nexus analysis for stays over 30 days."
    )
    # Use lenient thresholds — this answer should pass with very low bar
    lenient_checker = HallucinationChecker(
        threshold_pass=0.10,
        threshold_warn=0.05,
        aggregation_method="max",
    )
    result = await lenient_checker.check(answer, REMOTE_WORK_CONTEXT)
    assert result["level"] == "pass", (
        f"With lenient thresholds (pass=0.10), expected 'pass', got '{result['level']}' "
        f"(score={result['score']:.4f})"
    )

    # Use very strict thresholds — nearly everything fails
    strict_checker = HallucinationChecker(
        threshold_pass=0.9999,
        threshold_warn=0.999,
        aggregation_method="max",
    )
    result2 = await strict_checker.check(answer, REMOTE_WORK_CONTEXT)
    assert result2["level"] == "fail", (
        f"With strict thresholds (pass=0.9999), expected 'fail', got '{result2['level']}' "
        f"(score={result2['score']:.4f})"
    )


@pytest.mark.asyncio
async def test_aggregation_methods():
    """Different aggregation methods produce different scores for mixed-relevance context."""
    context = [
        "The company offers a $1,500 equipment stipend for remote workers.",
        "Annual performance reviews happen in December with 360-degree feedback.",
    ]
    # Answer grounded in chunk 1 only — chunk 2 is irrelevant
    answer = "Remote employees receive a $1,500 stipend for home office equipment."

    checker_max = HallucinationChecker(
        threshold_pass=0.85, threshold_warn=0.70, aggregation_method="max"
    )
    checker_mean = HallucinationChecker(
        threshold_pass=0.85, threshold_warn=0.70, aggregation_method="mean"
    )
    checker_min = HallucinationChecker(
        threshold_pass=0.85, threshold_warn=0.70, aggregation_method="min"
    )

    result_max = await checker_max.check(answer, context)
    result_mean = await checker_mean.check(answer, context)
    result_min = await checker_min.check(answer, context)

    # Ordering: max >= mean >= min
    assert result_max["score"] >= result_mean["score"] - 0.001
    assert result_mean["score"] >= result_min["score"] - 0.001

    # max should pick the high-scoring chunk
    assert result_max["score"] > result_min["score"], (
        f"max ({result_max['score']:.4f}) should exceed min ({result_min['score']:.4f}) "
        "for mixed-relevance context"
    )

    # All should have per-chunk scores
    assert len(result_max["per_chunk_scores"]) == 2
    assert len(result_mean["per_chunk_scores"]) == 2
    assert len(result_min["per_chunk_scores"]) == 2


@pytest.mark.asyncio
async def test_inference_latency():
    """HHEM inference should complete within 500ms on CPU for small inputs."""
    answer = "Remote work is allowed with manager approval."
    context = ["Employees may work remotely up to 3 days per week with manager approval."]

    result = await _checker.check(answer, context)
    assert result["latency_ms"] < 500, (
        f"Inference took {result['latency_ms']:.1f}ms — exceeds 500ms CPU target"
    )
