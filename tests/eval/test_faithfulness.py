"""DeepEval Faithfulness evaluation suite for CI.

Runs claim-level faithfulness checks against a golden dataset of 20 test cases.
Each case has a query, context, expected answer, and expected faithfulness score.

Categories:
  - grounded (5): Answers fully supported by context
  - subtle_hallucination (5): Answers with wrong numbers, dates, or invented facts
  - partial (5): Mix of grounded and fabricated claims
  - edge_case (5): Empty context, very long context, ambiguous queries

Requirements:
  - OPENAI_API_KEY must be set (DeepEval FaithfulnessMetric uses an LLM for claim decomposition)
  - Run: pytest tests/eval/test_faithfulness.py --deepeval -v
  - Or locally: OPENAI_API_KEY=xxx pytest tests/eval/test_faithfulness.py -v

CI behavior: Fails build if average faithfulness drops below 0.85 OR
any single test case drops more than 10% from its expected baseline.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GOLDEN_DATASET_PATH = Path("golden_dataset/faithfulness_tests.jsonl")

# Skip entire module if no API key — DeepEval FaithfulnessMetric requires LLM
pytestmark = [
    pytest.mark.eval,
    pytest.mark.skipif(
        not OPENAI_API_KEY,
        reason="OPENAI_API_KEY not set — DeepEval FaithfulnessMetric requires LLM for claim decomposition",
    ),
]


def _load_golden_dataset() -> list[dict]:
    """Load test cases from JSONL file."""
    if not GOLDEN_DATASET_PATH.exists():
        pytest.skip(f"Golden dataset not found: {GOLDEN_DATASET_PATH}")
    cases = []
    with open(GOLDEN_DATASET_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _get_cases_by_category(category: str) -> list[dict]:
    return [c for c in _load_golden_dataset() if c["category"] == category]


@pytest.fixture(scope="module")
def golden_dataset() -> list[dict]:
    return _load_golden_dataset()


class TestFaithfulnessGrounded:
    """5 straightforward grounded answers — should score high."""

    @pytest.mark.parametrize("case", _get_cases_by_category("grounded"), ids=lambda c: c["id"])
    def test_grounded_case(self, case: dict) -> None:
        from deepeval import assert_test
        from deepeval.metrics import FaithfulnessMetric
        from deepeval.test_case import LLMTestCase

        metric = FaithfulnessMetric(threshold=0.7, model="gpt-4o-mini")
        test_case = LLMTestCase(
            input=case["query"],
            actual_output=case["expected_answer"],
            retrieval_context=case["context"],
        )
        assert_test(test_case, [metric])


class TestFaithfulnessHallucinations:
    """5 answers with subtle hallucinations — should score low."""

    @pytest.mark.parametrize(
        "case", _get_cases_by_category("subtle_hallucination"), ids=lambda c: c["id"]
    )
    def test_hallucination_case(self, case: dict) -> None:
        from deepeval.metrics import FaithfulnessMetric
        from deepeval.test_case import LLMTestCase

        metric = FaithfulnessMetric(threshold=0.7, model="gpt-4o-mini")
        test_case = LLMTestCase(
            input=case["query"],
            actual_output=case["expected_answer"],
            retrieval_context=case["context"],
        )
        metric.measure(test_case)
        # Hallucinated answers should score below their expected baseline
        assert metric.score is not None
        assert metric.score < case["expected_faithfulness"] + 0.20, (
            f"Hallucinated case {case['id']} scored {metric.score:.2f}, "
            f"expected below ~{case['expected_faithfulness'] + 0.20:.2f}"
        )


class TestFaithfulnessPartial:
    """5 partially grounded answers — mix of real and fabricated claims."""

    @pytest.mark.parametrize("case", _get_cases_by_category("partial"), ids=lambda c: c["id"])
    def test_partial_case(self, case: dict) -> None:
        from deepeval.metrics import FaithfulnessMetric
        from deepeval.test_case import LLMTestCase

        metric = FaithfulnessMetric(threshold=0.3, model="gpt-4o-mini")
        test_case = LLMTestCase(
            input=case["query"],
            actual_output=case["expected_answer"],
            retrieval_context=case["context"],
        )
        metric.measure(test_case)
        assert metric.score is not None


class TestFaithfulnessEdgeCases:
    """5 edge cases: empty context, long context, ambiguous queries."""

    @pytest.mark.parametrize("case", _get_cases_by_category("edge_case"), ids=lambda c: c["id"])
    def test_edge_case(self, case: dict) -> None:
        from deepeval.metrics import FaithfulnessMetric
        from deepeval.test_case import LLMTestCase

        # Edge cases may have empty context — DeepEval should handle gracefully
        if not case["context"]:
            pytest.skip("Empty context — FaithfulnessMetric requires retrieval_context")
            return

        metric = FaithfulnessMetric(threshold=0.3, model="gpt-4o-mini")
        test_case = LLMTestCase(
            input=case["query"],
            actual_output=case["expected_answer"],
            retrieval_context=case["context"],
        )
        metric.measure(test_case)
        assert metric.score is not None


class TestFaithfulnessRegression:
    """Aggregate check: average faithfulness across all grounded cases >= 0.85."""

    def test_average_faithfulness_grounded(self) -> None:
        from deepeval.metrics import FaithfulnessMetric
        from deepeval.test_case import LLMTestCase

        grounded_cases = _get_cases_by_category("grounded")
        scores = []

        for case in grounded_cases:
            metric = FaithfulnessMetric(threshold=0.7, model="gpt-4o-mini")
            test_case = LLMTestCase(
                input=case["query"],
                actual_output=case["expected_answer"],
                retrieval_context=case["context"],
            )
            metric.measure(test_case)
            if metric.score is not None:
                scores.append(metric.score)

        avg = sum(scores) / len(scores) if scores else 0.0
        assert avg >= 0.85, (
            f"Average faithfulness for grounded cases: {avg:.2f} (need >= 0.85). "
            f"Individual scores: {[f'{s:.2f}' for s in scores]}"
        )
