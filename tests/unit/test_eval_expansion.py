"""Tests for eval suite expansion (Wave 7.5).

Covers gap filling, coverage report, JSONL format, and syntax validation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.flywheel.eval_expansion import EvalSuiteExpander


def _make_completed_annotation(
    trace_id: str,
    query: str,
    correct_answer: str,
    category: str = "context_gap",
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "query": query,
        "context": ["Some context."],
        "answer_given": "Wrong.",
        "faithfulness_score": 0.3,
        "category": category,
        "annotation": {
            "correct_answer": correct_answer,
            "failure_type": category,
            "notes": None,
            "annotator": "human",
            "annotated_at": "2026-02-25T00:00:00+00:00",
        },
    }


def _seed_with_hallucination(dataset_dir: Path) -> None:
    """Seed dataset with hallucination examples but no context_gap."""
    dataset_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({
            "id": f"h-{i}", "category": "hallucination", "query": f"Hall query {i}",
            "expected_answer": f"Answer {i}", "expected_faithfulness": 0.9,
        })
        for i in range(5)
    ]
    (dataset_dir / "faithfulness_tests.jsonl").write_text("\n".join(lines) + "\n")


class TestGapFilling:
    """Test 1: Import context_gap annotations into dataset with only hallucination examples."""

    def test_fills_category_gap(self, tmp_path: Path) -> None:
        dataset_dir = tmp_path / "golden"
        _seed_with_hallucination(dataset_dir)

        annotations_dir = tmp_path / "completed"
        annotations_dir.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            anno = _make_completed_annotation(
                f"cg-{i}", f"Context gap query {i}", f"Correct answer {i}", "context_gap",
            )
            (annotations_dir / f"cg-{i}.json").write_text(json.dumps(anno))

        expander = EvalSuiteExpander(dataset_dir=dataset_dir)
        result = expander.expand_from_annotations(annotations_dir)

        assert result["generated"] == 5
        assert "context_gap" in result["categories_filled"]


class TestCoverageReport:
    """Test 2: Assert coverage report correctly identifies gaps."""

    def test_identifies_gaps(self, tmp_path: Path) -> None:
        dataset_dir = tmp_path / "golden"
        _seed_with_hallucination(dataset_dir)

        expander = EvalSuiteExpander(dataset_dir=dataset_dir)
        report = expander.get_coverage_report()

        assert report["failure_categories"]["hallucination"]["coverage"] == "covered"
        assert report["failure_categories"]["context_gap"]["coverage"] == "GAP"
        assert "context_gap" in report["gaps"]
        assert "hallucination" not in report["gaps"]


class TestPromptfooFormat:
    """Test 3: Assert generated Promptfoo tests are valid JSONL."""

    def test_valid_promptfoo_jsonl(self, tmp_path: Path) -> None:
        dataset_dir = tmp_path / "golden"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        annotations_dir = tmp_path / "completed"
        annotations_dir.mkdir(parents=True, exist_ok=True)
        anno = _make_completed_annotation("pf-1", "Test query", "Correct answer")
        (annotations_dir / "pf-1.json").write_text(json.dumps(anno))

        expander = EvalSuiteExpander(dataset_dir=dataset_dir)
        expander.expand_from_annotations(annotations_dir)

        pf_path = dataset_dir / "promptfoo_tests.jsonl"
        assert pf_path.exists()
        for line in pf_path.read_text().strip().split("\n"):
            entry = json.loads(line)  # Should not raise
            assert "vars" in entry
            assert "query" in entry["vars"]
            assert "assert" in entry


class TestDeepEvalFormat:
    """Test 4: Assert generated DeepEval tests are valid JSONL."""

    def test_valid_deepeval_jsonl(self, tmp_path: Path) -> None:
        dataset_dir = tmp_path / "golden"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        annotations_dir = tmp_path / "completed"
        annotations_dir.mkdir(parents=True, exist_ok=True)
        anno = _make_completed_annotation("de-1", "Test query", "Correct answer")
        (annotations_dir / "de-1.json").write_text(json.dumps(anno))

        expander = EvalSuiteExpander(dataset_dir=dataset_dir)
        expander.expand_from_annotations(annotations_dir)

        de_path = dataset_dir / "faithfulness_tests.jsonl"
        assert de_path.exists()
        for line in de_path.read_text().strip().split("\n"):
            entry = json.loads(line)
            assert "category" in entry
            assert "query" in entry
            assert "expected_answer" in entry
            assert "expected_faithfulness" in entry


class TestAfterExpansion:
    """Test 5: After expansion, coverage report shows no new gaps for expanded categories."""

    def test_gaps_filled_after_expansion(self, tmp_path: Path) -> None:
        dataset_dir = tmp_path / "golden"
        _seed_with_hallucination(dataset_dir)

        # Initially, context_gap is a gap
        expander = EvalSuiteExpander(dataset_dir=dataset_dir)
        before = expander.get_coverage_report()
        assert "context_gap" in before["gaps"]

        # Add context_gap annotations
        annotations_dir = tmp_path / "completed"
        annotations_dir.mkdir(parents=True, exist_ok=True)
        for i in range(3):
            anno = _make_completed_annotation(f"fill-{i}", f"Q {i}", f"A {i}", "context_gap")
            (annotations_dir / f"fill-{i}.json").write_text(json.dumps(anno))

        expander.expand_from_annotations(annotations_dir)

        after = expander.get_coverage_report()
        assert "context_gap" not in after["gaps"]
        assert after["failure_categories"]["context_gap"]["coverage"] == "covered"
