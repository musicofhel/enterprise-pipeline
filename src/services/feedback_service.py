"""Feedback collection service.

Stores user feedback as local JSON files and creates audit trail entries.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from src.models.audit import (
    AuditActor,
    AuditActorType,
    AuditEvent,
    AuditEventType,
    AuditResource,
    AuditResourceType,
)

if TYPE_CHECKING:
    from src.observability.audit_log import AuditLogService

logger = structlog.get_logger()

LOCAL_FEEDBACK_DIR = Path("feedback/local")


class FeedbackService:
    """Persist and retrieve user feedback."""

    def __init__(
        self,
        audit_log: AuditLogService,
        storage_dir: Path = LOCAL_FEEDBACK_DIR,
    ) -> None:
        self._audit_log = audit_log
        self._storage_dir = storage_dir

    def record_feedback(
        self,
        trace_id: str,
        user_id: str,
        rating: str,
        correction: str | None = None,
        comment: str | None = None,
    ) -> str:
        """Store feedback and return the feedback_id."""
        feedback_id = str(uuid4())
        feedback_data: dict[str, Any] = {
            "feedback_id": feedback_id,
            "trace_id": trace_id,
            "user_id": user_id,
            "rating": rating,
            "correction": correction,
            "comment": comment,
            "created_at": datetime.now(UTC).isoformat(),
        }

        self._storage_dir.mkdir(parents=True, exist_ok=True)
        path = self._storage_dir / f"{feedback_id}.json"
        path.write_text(json.dumps(feedback_data, indent=2, default=str))

        # Audit trail
        self._audit_log.log_event(
            AuditEvent(
                event_type=AuditEventType.FEEDBACK,
                actor=AuditActor(type=AuditActorType.USER, id=user_id),
                resource=AuditResource(type=AuditResourceType.TRACE, id=trace_id),
                details={
                    "feedback_id": feedback_id,
                    "rating": rating,
                },
            )
        )

        logger.info("feedback_recorded", feedback_id=feedback_id, trace_id=trace_id)
        return feedback_id

    def get_feedback(self, feedback_id: str) -> dict[str, Any] | None:
        """Retrieve a single feedback entry."""
        path = self._storage_dir / f"{feedback_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())  # type: ignore[no-any-return]

    def list_feedback_for_user(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """List feedback entries for a given user."""
        if not self._storage_dir.exists():
            return []

        results: list[dict[str, Any]] = []
        for path in sorted(self._storage_dir.glob("*.json"), reverse=True):
            if len(results) >= limit:
                break
            try:
                data: dict[str, Any] = json.loads(path.read_text())
                if data.get("user_id") == user_id:
                    results.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def delete_feedback_for_user(self, user_id: str) -> int:
        """Delete all feedback for a user (right-to-deletion support)."""
        if not self._storage_dir.exists():
            return 0

        count = 0
        for path in self._storage_dir.glob("*.json"):
            try:
                data: dict[str, Any] = json.loads(path.read_text())
                if data.get("user_id") == user_id:
                    path.unlink()
                    count += 1
            except (json.JSONDecodeError, OSError):
                continue
        return count
