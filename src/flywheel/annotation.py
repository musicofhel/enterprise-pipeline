"""Annotation pipeline for human review of failed responses.

Generates annotation tasks from triage reports, supports human submission,
and exports completed annotations to golden dataset format.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from src.models.audit import (
    AuditActor,
    AuditActorType,
    AuditEvent,
    AuditEventType,
    AuditResource,
    AuditResourceType,
)
from src.observability.metrics import (
    ANNOTATIONS_COMPLETED_TOTAL,
    ANNOTATIONS_EXPORTED_TOTAL,
    ANNOTATIONS_PENDING_TOTAL,
)

logger = structlog.get_logger()


class AnnotationService:
    """Manage annotation tasks from triage reports."""

    def __init__(
        self,
        annotations_dir: Path = Path("annotations"),
        audit_log: Any | None = None,
    ) -> None:
        self._pending_dir = annotations_dir / "pending"
        self._completed_dir = annotations_dir / "completed"
        self._audit_log = audit_log

    def generate_tasks(self, triage_report: dict[str, Any]) -> int:
        """Create annotation tasks from a triage report's top failures."""
        self._pending_dir.mkdir(parents=True, exist_ok=True)

        failures = triage_report.get("top_failures", [])
        count = 0

        for failure in failures:
            trace_id = failure.get("trace_id", "")
            if not trace_id:
                continue

            # Skip if already exists
            if (self._pending_dir / f"{trace_id}.json").exists():
                continue
            if (self._completed_dir / f"{trace_id}.json").exists():
                continue

            task = {
                "trace_id": trace_id,
                "query": failure.get("query", ""),
                "context": failure.get("context", []),
                "answer_given": failure.get("answer", ""),
                "faithfulness_score": failure.get("faithfulness_score"),
                "category": failure.get("category", "other"),
                "annotation": {
                    "correct_answer": None,
                    "failure_type": None,
                    "notes": None,
                    "annotator": None,
                    "annotated_at": None,
                },
            }

            path = self._pending_dir / f"{trace_id}.json"
            path.write_text(json.dumps(task, indent=2, default=str))
            count += 1

        self._update_gauges()
        logger.info("annotation_tasks_generated", count=count)
        return count

    def submit_annotation(
        self,
        trace_id: str,
        correct_answer: str,
        failure_type: str,
        notes: str | None = None,
        annotator: str = "human",
    ) -> bool:
        """Submit an annotation for a pending task."""
        pending_path = self._pending_dir / f"{trace_id}.json"
        if not pending_path.exists():
            logger.warning("annotation_not_found", trace_id=trace_id)
            return False

        task: dict[str, Any] = json.loads(pending_path.read_text())
        task["annotation"] = {
            "correct_answer": correct_answer,
            "failure_type": failure_type,
            "notes": notes,
            "annotator": annotator,
            "annotated_at": datetime.now(UTC).isoformat(),
        }

        # Move to completed
        self._completed_dir.mkdir(parents=True, exist_ok=True)
        completed_path = self._completed_dir / f"{trace_id}.json"
        completed_path.write_text(json.dumps(task, indent=2, default=str))
        pending_path.unlink()

        # Audit trail
        if self._audit_log:
            self._audit_log.log_event(
                AuditEvent(
                    event_type=AuditEventType.FEEDBACK,
                    actor=AuditActor(type=AuditActorType.USER, id=annotator),
                    resource=AuditResource(type=AuditResourceType.TRACE, id=trace_id),
                    details={
                        "action": "annotation_submitted",
                        "failure_type": failure_type,
                    },
                )
            )

        self._update_gauges()
        logger.info("annotation_submitted", trace_id=trace_id, failure_type=failure_type)
        return True

    def get_next_pending(self) -> dict[str, Any] | None:
        """Return the next pending annotation task."""
        if not self._pending_dir.exists():
            return None

        for path in sorted(self._pending_dir.glob("*.json")):
            try:
                return json.loads(path.read_text())  # type: ignore[no-any-return]
            except (json.JSONDecodeError, OSError):
                continue
        return None

    def get_pending_count(self) -> int:
        """Count pending annotation tasks."""
        if not self._pending_dir.exists():
            return 0
        return len(list(self._pending_dir.glob("*.json")))

    def get_completed_count(self) -> int:
        """Count completed annotation tasks."""
        if not self._completed_dir.exists():
            return 0
        return len(list(self._completed_dir.glob("*.json")))

    def export_to_golden_dataset(self, output_dir: Path) -> int:
        """Export completed annotations to golden dataset JSONL formats."""
        if not self._completed_dir.exists():
            return 0

        output_dir.mkdir(parents=True, exist_ok=True)
        promptfoo_path = output_dir / "promptfoo_tests.jsonl"
        deepeval_path = output_dir / "faithfulness_tests.jsonl"

        exported = 0
        promptfoo_lines: list[str] = []
        deepeval_lines: list[str] = []

        for path in sorted(self._completed_dir.glob("*.json")):
            try:
                task = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            annotation = task.get("annotation", {})
            correct_answer = annotation.get("correct_answer")
            if not correct_answer:
                continue

            # Promptfoo format
            promptfoo_entry = {
                "vars": {
                    "query": task.get("query", ""),
                    "context": "\n\n".join(task.get("context", [])) if task.get("context") else task.get("answer_given", ""),
                },
                "assert": [
                    {
                        "type": "python",
                        "value": "file://scripts/eval_assertions.py",
                    }
                ],
            }
            promptfoo_lines.append(json.dumps(promptfoo_entry, default=str))

            # DeepEval format
            deepeval_entry = {
                "id": f"annotated-{task.get('trace_id', '')}",
                "category": annotation.get("failure_type", task.get("category", "other")),
                "query": task.get("query", ""),
                "context": task.get("context", []),
                "expected_answer": correct_answer,
                "expected_faithfulness": 0.85,
                "source": "annotated_failures",
            }
            deepeval_lines.append(json.dumps(deepeval_entry, default=str))

            exported += 1

        # Append to existing files
        if promptfoo_lines:
            with open(promptfoo_path, "a") as f:
                f.write("\n".join(promptfoo_lines) + "\n")

        if deepeval_lines:
            with open(deepeval_path, "a") as f:
                f.write("\n".join(deepeval_lines) + "\n")

        ANNOTATIONS_EXPORTED_TOTAL.inc(exported)
        self._update_gauges()
        logger.info("annotations_exported", count=exported, output_dir=str(output_dir))
        return exported

    def _update_gauges(self) -> None:
        """Update Prometheus gauges for pending/completed counts."""
        ANNOTATIONS_PENDING_TOTAL.set(self.get_pending_count())
        ANNOTATIONS_COMPLETED_TOTAL.set(self.get_completed_count())
