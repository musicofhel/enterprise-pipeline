"""Tests for annotation pipeline (Wave 7.3).

Covers task generation, submission, export, audit trail, and counts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.flywheel.annotation import AnnotationService
from src.observability.audit_log import AuditLogService


@pytest.fixture()
def annotations_dir(tmp_path: Path) -> Path:
    return tmp_path / "annotations"


@pytest.fixture()
def audit_log(tmp_path: Path) -> AuditLogService:
    return AuditLogService(storage_dir=tmp_path / "audit")


@pytest.fixture()
def service(annotations_dir: Path, audit_log: AuditLogService) -> AnnotationService:
    return AnnotationService(annotations_dir=annotations_dir, audit_log=audit_log)


def _make_triage_report(n: int = 10) -> dict[str, Any]:
    """Build a triage report with N top failures."""
    return {
        "period": {"start": "2026-02-18", "end": "2026-02-25"},
        "total_responses": 100,
        "total_failures": n,
        "failure_rate": n / 100,
        "by_category": {"hallucination": {"count": n, "example_trace_ids": []}},
        "clusters": [],
        "top_failures": [
            {
                "trace_id": f"trace-{i}",
                "query": f"Test query {i}",
                "answer": f"Test answer {i}",
                "faithfulness_score": 0.3 + i * 0.02,
                "category": "hallucination",
                "feedback": "negative",
            }
            for i in range(n)
        ],
    }


class TestTaskGeneration:
    """Test 1: Generate 10 annotation tasks. Assert 10 files in pending."""

    def test_generate_tasks(self, service: AnnotationService) -> None:
        report = _make_triage_report(10)
        count = service.generate_tasks(report)

        assert count == 10
        assert service.get_pending_count() == 10

    def test_no_duplicates(self, service: AnnotationService) -> None:
        report = _make_triage_report(5)
        service.generate_tasks(report)
        count2 = service.generate_tasks(report)

        assert count2 == 0  # All already exist
        assert service.get_pending_count() == 5


class TestSubmission:
    """Test 2: Submit 5 annotations, check counts."""

    def test_submit_moves_to_completed(self, service: AnnotationService) -> None:
        report = _make_triage_report(10)
        service.generate_tasks(report)

        for i in range(5):
            ok = service.submit_annotation(
                trace_id=f"trace-{i}",
                correct_answer=f"Correct answer for query {i}",
                failure_type="hallucination",
                notes=f"Note for {i}",
            )
            assert ok is True

        assert service.get_pending_count() == 5
        assert service.get_completed_count() == 5

    def test_submit_nonexistent_returns_false(self, service: AnnotationService) -> None:
        ok = service.submit_annotation(
            trace_id="nonexistent",
            correct_answer="x",
            failure_type="other",
        )
        assert ok is False


class TestExport:
    """Test 3: Export completed annotations to golden dataset."""

    def test_export_creates_jsonl(self, service: AnnotationService, tmp_path: Path) -> None:
        report = _make_triage_report(5)
        service.generate_tasks(report)

        for i in range(5):
            service.submit_annotation(
                trace_id=f"trace-{i}",
                correct_answer=f"Correct answer {i}",
                failure_type="hallucination",
            )

        output_dir = tmp_path / "golden"
        count = service.export_to_golden_dataset(output_dir)
        assert count == 5

        # Check Promptfoo JSONL
        promptfoo_path = output_dir / "promptfoo_tests.jsonl"
        assert promptfoo_path.exists()
        lines = promptfoo_path.read_text().strip().split("\n")
        assert len(lines) == 5
        entry = json.loads(lines[0])
        assert "vars" in entry
        assert "query" in entry["vars"]

        # Check DeepEval JSONL
        deepeval_path = output_dir / "faithfulness_tests.jsonl"
        assert deepeval_path.exists()
        lines = deepeval_path.read_text().strip().split("\n")
        assert len(lines) == 5
        entry = json.loads(lines[0])
        assert "expected_answer" in entry
        assert entry["source"] == "annotated_failures"


class TestAuditTrail:
    """Test 4: Assert annotation creates audit trail entries."""

    def test_audit_trail(
        self,
        service: AnnotationService,
        audit_log: AuditLogService,
    ) -> None:
        report = _make_triage_report(1)
        service.generate_tasks(report)

        service.submit_annotation(
            trace_id="trace-0",
            correct_answer="Fixed answer",
            failure_type="hallucination",
            annotator="reviewer-1",
        )

        # Check audit log has an entry
        events = audit_log.list_events(limit=10)
        annotation_events = [
            e for e in events
            if e.details.get("action") == "annotation_submitted"
        ]
        assert len(annotation_events) >= 1
        assert annotation_events[0].details["failure_type"] == "hallucination"


class TestCounts:
    """Test 5: Assert get_pending_count() and get_completed_count() are accurate."""

    def test_counts_accurate(self, service: AnnotationService) -> None:
        assert service.get_pending_count() == 0
        assert service.get_completed_count() == 0

        report = _make_triage_report(8)
        service.generate_tasks(report)
        assert service.get_pending_count() == 8
        assert service.get_completed_count() == 0

        for i in range(3):
            service.submit_annotation(
                trace_id=f"trace-{i}",
                correct_answer="x",
                failure_type="other",
            )

        assert service.get_pending_count() == 5
        assert service.get_completed_count() == 3
