"""Feedback collection service.

Stores user feedback as local JSON files and creates audit trail entries.
Extended in Wave 7 to capture query context and compute feedback stats.
"""
from __future__ import annotations

import json
from collections import deque
from datetime import UTC, datetime, timedelta
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
from src.observability.metrics import (
    FEEDBACK_CORRECTION_RECEIVED_TOTAL,
    FEEDBACK_RATE,
    FEEDBACK_RECEIVED_TOTAL,
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
        # Rolling window for feedback rate calculation
        self._response_timestamps: deque[datetime] = deque()
        self._feedback_timestamps: deque[datetime] = deque()
        self._rate_window = timedelta(days=7)

    def record_response(self) -> None:
        """Track that a pipeline response was served (for feedback rate)."""
        now = datetime.now(UTC)
        self._response_timestamps.append(now)
        self._trim_window()
        self._update_feedback_rate()

    def record_feedback(
        self,
        trace_id: str,
        user_id: str,
        rating: str,
        correction: str | None = None,
        comment: str | None = None,
        query: str | None = None,
        answer: str | None = None,
        route: str | None = None,
        faithfulness_score: float | None = None,
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
            "query": query,
            "answer": answer,
            "route": route,
            "faithfulness_score": faithfulness_score,
            "created_at": datetime.now(UTC).isoformat(),
        }

        self._storage_dir.mkdir(parents=True, exist_ok=True)
        path = self._storage_dir / f"{feedback_id}.json"
        path.write_text(json.dumps(feedback_data, indent=2, default=str))

        # Prometheus metrics
        FEEDBACK_RECEIVED_TOTAL.labels(rating=rating).inc()
        if correction:
            FEEDBACK_CORRECTION_RECEIVED_TOTAL.inc()

        # Track for feedback rate
        self._feedback_timestamps.append(datetime.now(UTC))
        self._trim_window()
        self._update_feedback_rate()

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

    def get_feedback_stats(self, days: int = 7) -> dict[str, Any]:
        """Compute feedback stats over a time period."""
        if not self._storage_dir.exists():
            return {
                "total_responses": len(self._response_timestamps),
                "feedback_received": 0,
                "feedback_rate": 0.0,
                "positive": 0,
                "negative": 0,
                "with_correction": 0,
                "period": f"last_{days}_days",
            }

        cutoff = datetime.now(UTC) - timedelta(days=days)
        positive = 0
        negative = 0
        with_correction = 0
        total = 0

        for path in self._storage_dir.glob("*.json"):
            try:
                data: dict[str, Any] = json.loads(path.read_text())
                created_at = data.get("created_at", "")
                if created_at and created_at >= cutoff.isoformat():
                    total += 1
                    if data.get("rating") == "positive":
                        positive += 1
                    elif data.get("rating") == "negative":
                        negative += 1
                    if data.get("correction"):
                        with_correction += 1
            except (json.JSONDecodeError, OSError):
                continue

        response_count = len(self._response_timestamps)
        rate = total / response_count if response_count > 0 else 0.0

        return {
            "total_responses": response_count,
            "feedback_received": total,
            "feedback_rate": round(rate, 4),
            "positive": positive,
            "negative": negative,
            "with_correction": with_correction,
            "period": f"last_{days}_days",
        }

    def list_feedback_for_trace(self, trace_id: str) -> list[dict[str, Any]]:
        """List all feedback entries for a given trace."""
        if not self._storage_dir.exists():
            return []

        results: list[dict[str, Any]] = []
        for path in self._storage_dir.glob("*.json"):
            try:
                data: dict[str, Any] = json.loads(path.read_text())
                if data.get("trace_id") == trace_id:
                    results.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def _trim_window(self) -> None:
        """Remove timestamps outside the rolling window."""
        cutoff = datetime.now(UTC) - self._rate_window
        while self._response_timestamps and self._response_timestamps[0] < cutoff:
            self._response_timestamps.popleft()
        while self._feedback_timestamps and self._feedback_timestamps[0] < cutoff:
            self._feedback_timestamps.popleft()

    def _update_feedback_rate(self) -> None:
        """Update the Prometheus feedback_rate gauge."""
        responses = len(self._response_timestamps)
        feedbacks = len(self._feedback_timestamps)
        rate = feedbacks / responses if responses > 0 else 0.0
        FEEDBACK_RATE.set(rate)
