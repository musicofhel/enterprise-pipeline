"""Wave 4 exit criteria — compliance & data governance.

EC-1: Metadata enforcement on all vectors
EC-2: Deletion API completes end-to-end
EC-3: Audit log immutability
EC-4: Trace export
EC-5: Compliance RBAC
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from src.models.audit import (
    AuditActor,
    AuditActorType,
    AuditEvent,
    AuditEventType,
)
from src.models.metadata import ChunkMetadata, DocType
from src.models.rbac import ROLE_PERMISSIONS, PermissionChecker, Role
from src.observability.audit_log import AuditLogService
from src.observability.tracing import TracingService
from src.pipeline.retrieval.metadata_validator import (
    MetadataValidationError,
    validate_vector_metadata,
)
from src.services.deletion_service import DeletionService
from src.services.feedback_service import FeedbackService

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# EC-1: Metadata on all vectors
# ---------------------------------------------------------------------------


class TestEC1MetadataOnAllVectors:
    """Every vector upsert must include user_id, doc_id, and tenant_id."""

    def test_valid_metadata_passes(self) -> None:
        validate_vector_metadata(
            {"user_id": "u1", "doc_id": "d1", "tenant_id": "t1"}, "v1"
        )

    def test_missing_user_id_rejected(self) -> None:
        with pytest.raises(MetadataValidationError):
            validate_vector_metadata({"doc_id": "d1", "tenant_id": "t1"}, "v1")

    def test_missing_doc_id_rejected(self) -> None:
        with pytest.raises(MetadataValidationError):
            validate_vector_metadata({"user_id": "u1", "tenant_id": "t1"}, "v1")

    def test_missing_tenant_id_rejected(self) -> None:
        with pytest.raises(MetadataValidationError):
            validate_vector_metadata({"user_id": "u1", "doc_id": "d1"}, "v1")

    def test_chunk_metadata_model_has_required_fields(self) -> None:
        meta = ChunkMetadata(
            user_id="u1",
            tenant_id="t1",
            doc_id="d1",
            doc_type=DocType.MARKDOWN,
            chunk_index=0,
        )
        assert meta.user_id == "u1"
        assert meta.tenant_id == "t1"
        assert meta.doc_id == "d1"

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(MetadataValidationError):
            validate_vector_metadata(
                {"user_id": "", "doc_id": "d1", "tenant_id": "t1"}, "v1"
            )


# ---------------------------------------------------------------------------
# EC-2: Deletion API
# ---------------------------------------------------------------------------


class TestEC2DeletionAPI:
    """Deletion completes, receipt generated, verification passes, audit logged."""

    @pytest.fixture
    def mock_vector_store(self) -> AsyncMock:
        store = AsyncMock()
        store.delete_by_user.return_value = 3
        store.count_by_user.return_value = 0
        return store

    @pytest.fixture
    def mock_feedback_service(self) -> FeedbackService:
        from unittest.mock import MagicMock

        svc = MagicMock(spec=FeedbackService)
        svc.delete_feedback_for_user.return_value = 2
        return svc

    @pytest.fixture
    def svc(
        self, mock_vector_store: AsyncMock, mock_feedback_service: FeedbackService, tmp_path: Path
    ) -> DeletionService:
        audit = AuditLogService(storage_dir=tmp_path / "audit")
        tracing = TracingService(client=None, local_fallback=True)
        return DeletionService(
            vector_store=mock_vector_store,
            audit_log=audit,
            tracing=tracing,
            feedback_service=mock_feedback_service,
            storage_dir=tmp_path / "deletions",
        )

    @pytest.mark.asyncio
    async def test_deletion_completes(self, svc: DeletionService) -> None:
        receipt = await svc.delete_user_data("user-1", tenant_id="t1", reason="GDPR")
        assert receipt.status == "completed"

    @pytest.mark.asyncio
    async def test_receipt_persisted(self, svc: DeletionService, tmp_path: Path) -> None:
        receipt = await svc.delete_user_data("user-1", tenant_id="t1")
        path = tmp_path / "deletions" / f"{receipt.deletion_id}.json"
        assert path.exists()

    @pytest.mark.asyncio
    async def test_verification_passes(self, svc: DeletionService) -> None:
        await svc.delete_user_data("user-1", tenant_id="t1")
        assert await svc.verify_deletion("user-1") is True

    @pytest.mark.asyncio
    async def test_audit_logged(self, svc: DeletionService, tmp_path: Path) -> None:
        await svc.delete_user_data("user-1", tenant_id="t1", reason="GDPR")
        audit = AuditLogService(storage_dir=tmp_path / "audit")
        events = audit.list_events()
        assert any(e.event_type == AuditEventType.DELETION_REQUEST for e in events)


# ---------------------------------------------------------------------------
# EC-3: Audit log immutability
# ---------------------------------------------------------------------------


class TestEC3AuditLogImmutability:
    """No delete/update methods, events persist as JSON, no overwrite."""

    @pytest.fixture
    def svc(self, tmp_path: Path) -> AuditLogService:
        return AuditLogService(storage_dir=tmp_path / "audit")

    def test_no_delete_method(self, svc: AuditLogService) -> None:
        assert not hasattr(svc, "delete_event")

    def test_no_update_method(self, svc: AuditLogService) -> None:
        assert not hasattr(svc, "update_event")

    def test_events_persist_as_json(self, svc: AuditLogService, tmp_path: Path) -> None:
        event = AuditEvent(
            event_type=AuditEventType.CONFIG_CHANGE,
            actor=AuditActor(type=AuditActorType.ADMIN, id="admin-1"),
        )
        svc.log_event(event)
        path = tmp_path / "audit" / f"{event.event_id}.json"
        data = json.loads(path.read_text())
        assert data["event_type"] == "config_change"

    def test_second_write_does_not_corrupt(self, svc: AuditLogService) -> None:
        e1 = AuditEvent(
            event_type=AuditEventType.LLM_CALL,
            actor=AuditActor(type=AuditActorType.SYSTEM, id="sys"),
        )
        e2 = AuditEvent(
            event_type=AuditEventType.SAFETY_BLOCK,
            actor=AuditActor(type=AuditActorType.SYSTEM, id="sys"),
        )
        svc.log_event(e1)
        svc.log_event(e2)
        # Both retrievable independently
        assert svc.get_event(e1.event_id) is not None
        assert svc.get_event(e2.event_id) is not None


# ---------------------------------------------------------------------------
# EC-4: Trace export
# ---------------------------------------------------------------------------


class TestEC4TraceExport:
    """Local traces are exportable and match schema."""

    def test_local_traces_directory_exists_after_trace(self) -> None:
        svc = TracingService(client=None, local_fallback=True)
        ctx = svc.create_trace(name="test", user_id="u1")
        path = ctx.save_local()
        assert path is not None
        assert path.exists()

    def test_trace_matches_schema(self) -> None:
        svc = TracingService(client=None, local_fallback=True)
        ctx = svc.create_trace(name="test", user_id="u1")
        path = ctx.save_local()
        assert path is not None
        data = json.loads(path.read_text())
        required_keys = {
            "trace_id", "timestamp", "user_id", "session_id",
            "pipeline_version", "config_hash", "feature_flags",
            "spans", "scores",
        }
        assert required_keys.issubset(data.keys())


# ---------------------------------------------------------------------------
# EC-5: Compliance RBAC
# ---------------------------------------------------------------------------


class TestEC5ComplianceRBAC:
    """5 roles defined, correct permissions per role."""

    def test_five_roles_exist(self) -> None:
        assert len(Role) == 5

    def test_all_roles_mapped(self) -> None:
        for role in Role:
            assert role in ROLE_PERMISSIONS

    def test_deletion_restricted_to_security_and_compliance(self) -> None:
        for role in Role:
            checker = PermissionChecker(role)
            if role in (Role.SECURITY_ADMIN, Role.COMPLIANCE_OFFICER):
                assert checker.can_delete(), f"{role} should be able to delete"
            else:
                assert not checker.can_delete(), f"{role} should NOT be able to delete"

    def test_audit_read_restricted_to_security_and_compliance(self) -> None:
        for role in Role:
            checker = PermissionChecker(role)
            if role in (Role.SECURITY_ADMIN, Role.COMPLIANCE_OFFICER):
                assert checker.can_read_audit(), f"{role} should read audit"
            else:
                assert not checker.can_read_audit(), f"{role} should NOT read audit"
