"""Tests for AuditLogService."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from src.models.audit import (
    AuditActor,
    AuditActorType,
    AuditEvent,
    AuditEventType,
    AuditResource,
    AuditResourceType,
)
from src.observability.audit_log import AuditLogService


@pytest.fixture
def audit_service(tmp_path: Path) -> AuditLogService:
    return AuditLogService(storage_dir=tmp_path / "audit")


def _make_event(
    event_type: AuditEventType = AuditEventType.LLM_CALL,
    tenant_id: str | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_type=event_type,
        actor=AuditActor(type=AuditActorType.SYSTEM, id="test"),
        resource=AuditResource(type=AuditResourceType.TRACE, id="trace-1"),
        tenant_id=tenant_id,
    )


class TestAuditLogService:
    def test_log_event_creates_file(self, audit_service: AuditLogService, tmp_path: Path) -> None:
        event = _make_event()
        event_id = audit_service.log_event(event)
        assert (tmp_path / "audit" / f"{event_id}.json").exists()

    def test_log_event_returns_event_id(self, audit_service: AuditLogService) -> None:
        event = _make_event()
        event_id = audit_service.log_event(event)
        assert event_id == event.event_id

    def test_get_event_round_trip(self, audit_service: AuditLogService) -> None:
        event = _make_event()
        audit_service.log_event(event)
        retrieved = audit_service.get_event(event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == event.event_id
        assert retrieved.event_type == event.event_type

    def test_get_event_not_found(self, audit_service: AuditLogService) -> None:
        assert audit_service.get_event("nonexistent") is None

    def test_list_events_returns_all(self, audit_service: AuditLogService) -> None:
        for _ in range(3):
            audit_service.log_event(_make_event())
        events = audit_service.list_events()
        assert len(events) == 3

    def test_list_events_filter_by_type(self, audit_service: AuditLogService) -> None:
        audit_service.log_event(_make_event(AuditEventType.LLM_CALL))
        audit_service.log_event(_make_event(AuditEventType.DELETION_REQUEST))
        events = audit_service.list_events(event_type=AuditEventType.DELETION_REQUEST)
        assert len(events) == 1
        assert events[0].event_type == AuditEventType.DELETION_REQUEST

    def test_list_events_filter_by_tenant(self, audit_service: AuditLogService) -> None:
        audit_service.log_event(_make_event(tenant_id="tenant-a"))
        audit_service.log_event(_make_event(tenant_id="tenant-b"))
        events = audit_service.list_events(tenant_id="tenant-a")
        assert len(events) == 1
        assert events[0].tenant_id == "tenant-a"

    def test_no_delete_method(self, audit_service: AuditLogService) -> None:
        """WORM semantics — no delete or update methods should exist."""
        assert not hasattr(audit_service, "delete_event")
        assert not hasattr(audit_service, "update_event")
