"""Right-to-deletion service.

Coordinates vector deletion, trace redaction, feedback deletion, and audit
logging.  Each step is tracked independently so partial completions are
visible in the receipt.
"""
from __future__ import annotations

import asyncio
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
    from src.observability.tracing import TracingService
    from src.pipeline.retrieval.vector_store import VectorStore
    from src.services.feedback_service import FeedbackService

logger = structlog.get_logger()

LOCAL_DELETION_DIR = Path("deletions/local")


class DeletionStepResult:
    """Outcome of a single deletion step."""

    def __init__(self, status: str = "pending", count: int = 0) -> None:
        self.status = status
        self.count = count
        self.error: str | None = None
        self.reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status, "count": self.count}
        if self.error:
            d["error"] = self.error
        if self.reason:
            d["reason"] = self.reason
        return d


class DeletionReceipt:
    """Internal record of a deletion request and its outcome."""

    def __init__(
        self,
        deletion_id: str,
        user_id: str,
        tenant_id: str,
        reason: str,
    ) -> None:
        self.deletion_id = deletion_id
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.reason = reason
        self.status: str = "processing"
        self.vectors_deleted: int = 0
        self.traces_redacted: int = 0
        self.feedback_deleted: int = 0
        self.steps: dict[str, DeletionStepResult] = {}
        self.created_at: str = datetime.now(UTC).isoformat()
        self.completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "deletion_id": self.deletion_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "reason": self.reason,
            "status": self.status,
            "vectors_deleted": self.vectors_deleted,
            "traces_redacted": self.traces_redacted,
            "feedback_deleted": self.feedback_deleted,
            "steps": {k: v.to_dict() for k, v in self.steps.items()},
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class DeletionService:
    """Orchestrates right-to-deletion across all data stores."""

    def __init__(
        self,
        vector_store: VectorStore,
        audit_log: AuditLogService,
        tracing: TracingService,
        feedback_service: FeedbackService,
        storage_dir: Path = LOCAL_DELETION_DIR,
    ) -> None:
        self._vector_store = vector_store
        self._audit_log = audit_log
        self._tracing = tracing
        self._feedback_service = feedback_service
        self._storage_dir = storage_dir

    async def delete_user_data(
        self,
        user_id: str,
        tenant_id: str,
        reason: str = "",
    ) -> DeletionReceipt:
        """Delete all data for a user.  Returns a DeletionReceipt."""
        deletion_id = str(uuid4())
        receipt = DeletionReceipt(
            deletion_id=deletion_id,
            user_id=user_id,
            tenant_id=tenant_id,
            reason=reason,
        )

        any_failed = False

        # Step 1: Delete vectors
        step_vectors = DeletionStepResult()
        try:
            step_vectors.count = await self._vector_store.delete_by_user(user_id)
            step_vectors.status = "success"
            receipt.vectors_deleted = step_vectors.count
        except Exception as exc:
            step_vectors.status = "failed"
            step_vectors.error = str(exc)
            any_failed = True
            logger.exception("deletion_vectors_failed", user_id=user_id)
        receipt.steps["vectors"] = step_vectors

        # Step 2: Redact traces (run in thread to avoid blocking event loop)
        step_traces = DeletionStepResult()
        try:
            step_traces.count = await asyncio.to_thread(self._redact_user_traces, user_id)
            step_traces.status = "success"
            receipt.traces_redacted = step_traces.count
        except Exception as exc:
            step_traces.status = "failed"
            step_traces.error = str(exc)
            any_failed = True
            logger.exception("deletion_traces_failed", user_id=user_id)
        receipt.steps["traces"] = step_traces

        # Step 3: Delete feedback
        step_feedback = DeletionStepResult()
        try:
            step_feedback.count = await asyncio.to_thread(
                self._feedback_service.delete_feedback_for_user, user_id
            )
            step_feedback.status = "success"
            receipt.feedback_deleted = step_feedback.count
        except Exception as exc:
            step_feedback.status = "failed"
            step_feedback.error = str(exc)
            any_failed = True
            logger.exception("deletion_feedback_failed", user_id=user_id)
        receipt.steps["feedback"] = step_feedback

        # Determine overall status
        all_failed = all(s.status == "failed" for s in receipt.steps.values())
        if all_failed:
            receipt.status = "failed"
        elif any_failed:
            receipt.status = "partial"
        else:
            receipt.status = "completed"
        receipt.completed_at = datetime.now(UTC).isoformat()

        # Audit log entry — always written, even on failure
        self._audit_log.log_event(
            AuditEvent(
                event_type=AuditEventType.DELETION_REQUEST,
                actor=AuditActor(type=AuditActorType.USER, id=user_id),
                resource=AuditResource(type=AuditResourceType.VECTOR, id=user_id),
                details={
                    "deletion_id": deletion_id,
                    "reason": reason,
                    "status": receipt.status,
                    "vectors_deleted": receipt.vectors_deleted,
                    "traces_redacted": receipt.traces_redacted,
                    "feedback_deleted": receipt.feedback_deleted,
                    "steps": {k: v.to_dict() for k, v in receipt.steps.items()},
                },
                tenant_id=tenant_id,
            )
        )

        # Persist receipt
        self._save_receipt(receipt)

        logger.info(
            "deletion_completed",
            deletion_id=deletion_id,
            user_id=user_id,
            status=receipt.status,
        )
        return receipt

    def get_deletion_status(self, deletion_id: str) -> DeletionReceipt | None:
        """Look up a deletion receipt by ID."""
        path = self._storage_dir / f"{deletion_id}.json"
        if not path.exists():
            return None
        data: dict[str, Any] = json.loads(path.read_text())
        receipt = DeletionReceipt(
            deletion_id=data["deletion_id"],
            user_id=data["user_id"],
            tenant_id=data.get("tenant_id", ""),
            reason=data.get("reason", ""),
        )
        receipt.status = data["status"]
        receipt.vectors_deleted = data.get("vectors_deleted", 0)
        receipt.traces_redacted = data.get("traces_redacted", 0)
        receipt.feedback_deleted = data.get("feedback_deleted", 0)
        receipt.created_at = data["created_at"]
        receipt.completed_at = data.get("completed_at")
        # Restore steps
        for step_name, step_data in data.get("steps", {}).items():
            sr = DeletionStepResult(
                status=step_data.get("status", "unknown"),
                count=step_data.get("count", 0),
            )
            sr.error = step_data.get("error")
            sr.reason = step_data.get("reason")
            receipt.steps[step_name] = sr
        return receipt

    async def verify_deletion(self, user_id: str) -> bool:
        """Verify no remaining vectors exist for user."""
        count = await self._vector_store.count_by_user(user_id)
        return count == 0

    def _redact_user_traces(self, user_id: str) -> int:
        """Redact user data from local trace files."""
        from src.observability.tracing import LOCAL_TRACE_DIR

        if not LOCAL_TRACE_DIR.exists():
            return 0

        count = 0
        for trace_path in LOCAL_TRACE_DIR.glob("*.json"):
            try:
                data: dict[str, Any] = json.loads(trace_path.read_text())
                if data.get("user_id") == user_id:
                    data["user_id"] = "[REDACTED]"
                    data["session_id"] = "[REDACTED]"
                    trace_path.write_text(json.dumps(data, indent=2, default=str))
                    count += 1
            except (json.JSONDecodeError, OSError):
                continue
        return count

    def _save_receipt(self, receipt: DeletionReceipt) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        path = self._storage_dir / f"{receipt.deletion_id}.json"
        path.write_text(json.dumps(receipt.to_dict(), indent=2, default=str))
