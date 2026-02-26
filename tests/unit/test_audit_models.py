"""Tests for audit event models."""
from __future__ import annotations

from src.models.audit import (
    AuditActor,
    AuditActorType,
    AuditEvent,
    AuditEventType,
    AuditResource,
    AuditResourceType,
)


class TestAuditEventType:
    def test_all_event_types_exist(self) -> None:
        expected = {
            "llm_call", "safety_block", "deletion_request",
            "config_change", "feedback", "experiment_assignment",
        }
        assert {e.value for e in AuditEventType} == expected

    def test_event_type_is_string(self) -> None:
        assert str(AuditEventType.LLM_CALL) == "llm_call"


class TestAuditEvent:
    def test_create_minimal_event(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.LLM_CALL,
            actor=AuditActor(type=AuditActorType.SYSTEM, id="pipeline-1"),
        )
        assert event.event_id  # auto-generated UUID
        assert event.timestamp  # auto-generated
        assert event.event_type == AuditEventType.LLM_CALL
        assert event.actor.type == AuditActorType.SYSTEM
        assert event.resource is None

    def test_create_full_event(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.DELETION_REQUEST,
            actor=AuditActor(type=AuditActorType.USER, id="user-42"),
            resource=AuditResource(type=AuditResourceType.VECTOR, id="vec-1"),
            details={"reason": "GDPR request"},
            tenant_id="tenant-a",
        )
        assert event.resource is not None
        assert event.resource.type == AuditResourceType.VECTOR
        assert event.details["reason"] == "GDPR request"
        assert event.tenant_id == "tenant-a"
