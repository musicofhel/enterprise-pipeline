"""Tests for weekly flywheel automation (Wave 7.6).

Covers end-to-end cycle, dataset growth, eval generation, and report completeness.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.flywheel.annotation import AnnotationService
from src.flywheel.dataset_manager import GoldenDatasetManager
from src.flywheel.eval_expansion import EvalSuiteExpander
from src.flywheel.failure_triage import FailureTriageService


def _make_trace(
    trace_id: str | None = None,
    faithfulness: float | None = None,
    retrieval_scores: list[float] | None = None,
    query: str = "test query",
    answer: str = "test answer",
    feedback: str | None = None,
) -> dict[str, Any]:
    tid = trace_id or str(uuid4())
    r_scores = retrieval_scores or [0.8, 0.75]
    return {
        "trace_id": tid,
        "timestamp": datetime.now(UTC).isoformat(),
        "user_id": "user-1",
        "session_id": "",
        "pipeline_version": "test",
        "config_hash": "test",
        "feature_flags": {"pipeline_variant": "control"},
        "metadata": {"query": query},
        "spans": [
            {
                "name": "query_routing",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "duration_ms": 1.0,
                "attributes": {"route": "rag_knowledge_base", "confidence": 0.9},
            },
            {
                "name": "retrieval",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "duration_ms": 50.0,
                "attributes": {
                    "result_scores": r_scores,
                    "num_results_after_rerank": len(r_scores),
                    "skipped": False,
                },
            },
            {
                "name": "compression",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "duration_ms": 5.0,
                "attributes": {"compression_ratio": 0.5},
            },
            {
                "name": "generation",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "duration_ms": 200.0,
                "attributes": {"output": answer, "model": "test-model"},
            },
            {
                "name": "hallucination_check",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "duration_ms": 100.0,
                "attributes": {"score": faithfulness, "passed": (faithfulness or 0) > 0.7},
            },
        ],
        "scores": {"faithfulness": faithfulness, "user_feedback": feedback},
        "total_latency_ms": 400.0,
        "total_cost_usd": 0.01,
    }


def _run_full_cycle(tmp_path: Path) -> dict[str, Any]:
    """Run the complete flywheel cycle with synthetic data."""
    traces_dir = tmp_path / "traces"
    annotations_dir = tmp_path / "annotations"
    dataset_dir = tmp_path / "golden"
    reports_dir = tmp_path / "reports"

    # Create 30 synthetic traces: 20 successes, 10 failures
    traces_dir.mkdir(parents=True, exist_ok=True)
    for i in range(20):
        t = _make_trace(trace_id=f"success-{i}", faithfulness=0.92, query=f"Good query {i}")
        (traces_dir / f"success-{i}.json").write_text(json.dumps(t, indent=2))

    for i in range(5):
        t = _make_trace(
            trace_id=f"hall-{i}", faithfulness=0.3,
            retrieval_scores=[0.8, 0.7], query=f"Hallucination query {i}",
        )
        (traces_dir / f"hall-{i}.json").write_text(json.dumps(t, indent=2))

    for i in range(5):
        t = _make_trace(
            trace_id=f"ret-{i}", faithfulness=0.5,
            retrieval_scores=[0.1, 0.15], query=f"Retrieval failure query {i}",
        )
        (traces_dir / f"ret-{i}.json").write_text(json.dumps(t, indent=2))

    # Seed dataset
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "metadata.json").write_text(json.dumps({
        "version": "1.0.0", "last_updated": "2026-02-01",
        "total_examples": 5, "by_source": {"manual": 5}, "history": [],
    }))
    seed_lines = [
        json.dumps({"id": f"s-{i}", "category": "hallucination", "query": f"seed {i}",
                     "expected_answer": f"a {i}", "expected_faithfulness": 0.9})
        for i in range(5)
    ]
    (dataset_dir / "faithfulness_tests.jsonl").write_text("\n".join(seed_lines) + "\n")

    # Phase 1: Triage
    triage = FailureTriageService(traces_dir=traces_dir)
    report = triage.triage(days=7)

    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "triage.json").write_text(json.dumps(report, indent=2))

    # Generate annotation tasks
    annotator = AnnotationService(annotations_dir=annotations_dir)
    annotator.generate_tasks(report)

    # Auto-annotate 5 of them
    annotated_count = 0
    pending_dir = annotations_dir / "pending"
    if pending_dir.exists():
        for path in sorted(pending_dir.glob("*.json"))[:5]:
            task = json.loads(path.read_text())
            annotator.submit_annotation(
                trace_id=task["trace_id"],
                correct_answer=f"Corrected answer for {task['query']}",
                failure_type=task["category"],
                notes="Auto-annotated for testing",
                annotator="auto-test",
            )
            annotated_count += 1

    # Phase 2: Import + expand
    mgr = GoldenDatasetManager(dataset_dir=dataset_dir)
    import_result = mgr.import_annotations(
        source_dir=annotations_dir / "completed",
    )

    expander = EvalSuiteExpander(dataset_dir=dataset_dir)
    expansion = expander.expand_from_annotations(annotations_dir / "completed")
    coverage = expander.get_coverage_report()

    return {
        "triage_report": report,
        "annotated_count": annotated_count,
        "import_result": import_result,
        "expansion": expansion,
        "coverage": coverage,
        "final_metadata": mgr._read_metadata(),
        "dataset_dir": dataset_dir,
    }


class TestEndToEnd:
    """Test 1: Full cycle runs without errors."""

    def test_full_cycle_runs(self, tmp_path: Path) -> None:
        result = _run_full_cycle(tmp_path)

        assert result["triage_report"]["total_responses"] == 30
        assert result["triage_report"]["total_failures"] > 0
        assert result["annotated_count"] > 0
        assert result["import_result"]["imported"] > 0


class TestDatasetGrowth:
    """Test 2: Golden dataset grew."""

    def test_dataset_grew(self, tmp_path: Path) -> None:
        result = _run_full_cycle(tmp_path)

        meta = result["final_metadata"]
        assert meta["total_examples"] > 5  # Started with 5 seed examples


class TestEvalGeneration:
    """Test 3: New eval tests were generated."""

    def test_new_eval_tests(self, tmp_path: Path) -> None:
        result = _run_full_cycle(tmp_path)

        assert result["expansion"]["generated"] > 0


class TestReportCompleteness:
    """Test 4: Final report has all required sections."""

    def test_report_sections(self, tmp_path: Path) -> None:
        result = _run_full_cycle(tmp_path)

        # Triage report
        report = result["triage_report"]
        assert "period" in report
        assert "total_responses" in report
        assert "total_failures" in report
        assert "failure_rate" in report
        assert "by_category" in report

        # Coverage report
        coverage = result["coverage"]
        assert "failure_categories" in coverage
        assert "total_golden" in coverage
        assert "total_eval_tests" in coverage
        assert "gaps" in coverage

        # Metadata
        meta = result["final_metadata"]
        assert "version" in meta
        assert "total_examples" in meta
        assert "by_source" in meta
        assert "history" in meta
