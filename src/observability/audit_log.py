"""Immutable audit log service with local JSON fallback.

Follows the same local fallback pattern as TracingService — writes individual
JSON files under ``audit_logs/local/``.  No delete or update methods are
exposed, enforcing WORM (write-once, read-many) semantics at the API level.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from src.models.audit import AuditEvent, AuditEventType

logger = structlog.get_logger()

LOCAL_AUDIT_DIR = Path("audit_logs/local")


class AuditLogService:
    """Append-only audit log.

    No ``delete_event`` or ``update_event`` methods — WORM by design.
    """

    def __init__(self, storage_dir: Path = LOCAL_AUDIT_DIR) -> None:
        self._storage_dir = storage_dir

    def log_event(self, event: AuditEvent) -> str:
        """Persist an audit event.  Returns the event_id."""
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        path = self._storage_dir / f"{event.event_id}.json"
        path.write_text(json.dumps(event.model_dump(), indent=2, default=str))
        logger.info(
            "audit_event_logged",
            event_id=event.event_id,
            event_type=event.event_type,
            path=str(path),
        )
        return event.event_id

    def get_event(self, event_id: str) -> AuditEvent | None:
        """Retrieve a single event by ID."""
        path = self._storage_dir / f"{event_id}.json"
        if not path.exists():
            return None
        data: dict[str, Any] = json.loads(path.read_text())
        return AuditEvent(**data)

    def list_events(
        self,
        event_type: AuditEventType | None = None,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """List events with optional filtering."""
        if not self._storage_dir.exists():
            return []

        events: list[AuditEvent] = []
        for path in sorted(self._storage_dir.glob("*.json"), reverse=True):
            if len(events) >= limit:
                break
            try:
                data: dict[str, Any] = json.loads(path.read_text())
                event = AuditEvent(**data)
            except (json.JSONDecodeError, ValueError):
                logger.warning("corrupt_audit_event", path=str(path))
                continue

            if event_type and event.event_type != event_type:
                continue
            if tenant_id and event.tenant_id != tenant_id:
                continue
            events.append(event)

        return events
