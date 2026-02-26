"""Audit event models for immutable compliance logging.

Matches tech spec Section 2.3 — every auditable action produces an AuditEvent
with actor, resource, and event-type metadata.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class AuditEventType(StrEnum):
    """Types of auditable events."""

    LLM_CALL = "llm_call"
    SAFETY_BLOCK = "safety_block"
    DELETION_REQUEST = "deletion_request"
    CONFIG_CHANGE = "config_change"
    FEEDBACK = "feedback"
    EXPERIMENT_ASSIGNMENT = "experiment_assignment"


class AuditActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    ADMIN = "admin"


class AuditResourceType(StrEnum):
    TRACE = "trace"
    VECTOR = "vector"
    DOCUMENT = "document"
    PROMPT = "prompt"
    MODEL_CONFIG = "model_config"


class AuditActor(BaseModel):
    """Who performed the action."""

    type: AuditActorType
    id: str


class AuditResource(BaseModel):
    """What was acted upon."""

    type: AuditResourceType
    id: str


class AuditEvent(BaseModel):
    """Immutable audit log entry."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: AuditEventType
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    actor: AuditActor
    resource: AuditResource | None = None
    details: dict[str, object] = Field(default_factory=dict)
    tenant_id: str | None = None
