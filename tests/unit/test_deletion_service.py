"""Tests for DeletionService."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from src.observability.audit_log import AuditLogService
from src.observability.tracing import TracingService
from src.services.deletion_service import DeletionReceipt, DeletionService
from src.services.feedback_service import FeedbackService


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    store = AsyncMock()
    store.delete_by_user.return_value = 5
    store.count_by_user.return_value = 0
    return store


@pytest.fixture
def audit_service(tmp_path: Path) -> AuditLogService:
    return AuditLogService(storage_dir=tmp_path / "audit")


@pytest.fixture
def tracing_service() -> TracingService:
    return TracingService(client=None, local_fallback=True)


@pytest.fixture
def mock_feedback_service() -> MagicMock:
    svc = MagicMock(spec=FeedbackService)
    svc.delete_feedback_for_user.return_value = 3
    return svc


@pytest.fixture
def deletion_service(
    mock_vector_store: AsyncMock,
    audit_service: AuditLogService,
    tracing_service: TracingService,
    mock_feedback_service: MagicMock,
    tmp_path: Path,
) -> DeletionService:
    return DeletionService(
        vector_store=mock_vector_store,
        audit_log=audit_service,
        tracing=tracing_service,
        feedback_service=mock_feedback_service,
        storage_dir=tmp_path / "deletions",
    )


class TestDeletionReceipt:
    def test_initial_status_is_processing(self) -> None:
        receipt = DeletionReceipt(
            deletion_id="d1", user_id="u1", tenant_id="t1", reason="test"
        )
        assert receipt.status == "processing"

    def test_to_dict_roundtrip(self) -> None:
        receipt = DeletionReceipt(
            deletion_id="d1", user_id="u1", tenant_id="t1", reason="test"
        )
        data = receipt.to_dict()
        assert data["deletion_id"] == "d1"
        assert data["user_id"] == "u1"
        assert data["tenant_id"] == "t1"
        assert data["status"] == "processing"


class TestDeletionService:
    @pytest.mark.asyncio
    async def test_delete_user_data_returns_receipt(
        self, deletion_service: DeletionService
    ) -> None:
        receipt = await deletion_service.delete_user_data(
            "user-1", tenant_id="t1", reason="GDPR"
        )
        assert receipt.user_id == "user-1"
        assert receipt.tenant_id == "t1"
        assert receipt.status == "completed"
        assert receipt.deletion_id

    @pytest.mark.asyncio
    async def test_delete_user_data_calls_vector_store(
        self, deletion_service: DeletionService, mock_vector_store: AsyncMock
    ) -> None:
        await deletion_service.delete_user_data("user-1", tenant_id="t1")
        mock_vector_store.delete_by_user.assert_awaited_once_with("user-1")

    @pytest.mark.asyncio
    async def test_delete_user_data_creates_audit_event(
        self, deletion_service: DeletionService, audit_service: AuditLogService
    ) -> None:
        await deletion_service.delete_user_data(
            "user-1", tenant_id="t1", reason="test"
        )
        events = audit_service.list_events()
        assert len(events) == 1
        assert events[0].event_type.value == "deletion_request"
        assert events[0].tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_delete_user_data_persists_receipt(
        self, deletion_service: DeletionService, tmp_path: Path
    ) -> None:
        receipt = await deletion_service.delete_user_data("user-1", tenant_id="t1")
        path = tmp_path / "deletions" / f"{receipt.deletion_id}.json"
        assert path.exists()

    @pytest.mark.asyncio
    async def test_get_deletion_status(self, deletion_service: DeletionService) -> None:
        receipt = await deletion_service.delete_user_data("user-1", tenant_id="t1")
        retrieved = deletion_service.get_deletion_status(receipt.deletion_id)
        assert retrieved is not None
        assert retrieved.deletion_id == receipt.deletion_id
        assert retrieved.status == "completed"

    @pytest.mark.asyncio
    async def test_get_deletion_status_not_found(self, deletion_service: DeletionService) -> None:
        assert deletion_service.get_deletion_status("nonexistent") is None

    @pytest.mark.asyncio
    async def test_verify_deletion_no_remaining(self, deletion_service: DeletionService) -> None:
        assert await deletion_service.verify_deletion("user-1") is True

    @pytest.mark.asyncio
    async def test_verify_deletion_data_remains(
        self, deletion_service: DeletionService, mock_vector_store: AsyncMock
    ) -> None:
        mock_vector_store.count_by_user.return_value = 3
        assert await deletion_service.verify_deletion("user-1") is False

    @pytest.mark.asyncio
    async def test_failed_vector_deletion_sets_partial_status(
        self, deletion_service: DeletionService, mock_vector_store: AsyncMock
    ) -> None:
        """When only vectors fail, status is partial (traces+feedback succeed)."""
        mock_vector_store.delete_by_user.side_effect = RuntimeError("Qdrant down")
        receipt = await deletion_service.delete_user_data("user-1", tenant_id="t1")
        assert receipt.status == "partial"
        assert receipt.steps["vectors"].status == "failed"
        assert receipt.steps["traces"].status == "success"
        assert receipt.steps["feedback"].status == "success"

    @pytest.mark.asyncio
    async def test_all_failed_sets_failed_status(
        self,
        deletion_service: DeletionService,
        mock_vector_store: AsyncMock,
        mock_feedback_service: MagicMock,
    ) -> None:
        """When all steps fail, status is failed."""
        mock_vector_store.delete_by_user.side_effect = RuntimeError("down")
        mock_feedback_service.delete_feedback_for_user.side_effect = RuntimeError("down")
        # Trace redaction won't fail unless we make LOCAL_TRACE_DIR unreadable,
        # so we patch _redact_user_traces directly
        deletion_service._redact_user_traces = MagicMock(side_effect=RuntimeError("down"))
        receipt = await deletion_service.delete_user_data("user-1", tenant_id="t1")
        assert receipt.status == "failed"

    @pytest.mark.asyncio
    async def test_trace_redaction(
        self, deletion_service: DeletionService, tmp_path: Path
    ) -> None:
        """Test that user traces are redacted."""
        from src.observability.tracing import LOCAL_TRACE_DIR

        # Create a fake trace file
        LOCAL_TRACE_DIR.mkdir(parents=True, exist_ok=True)
        trace_data = {"trace_id": "t1", "user_id": "user-1", "session_id": "s1"}
        (LOCAL_TRACE_DIR / "t1.json").write_text(json.dumps(trace_data))

        receipt = await deletion_service.delete_user_data("user-1", tenant_id="t1")
        assert receipt.traces_redacted >= 1

        # Verify redaction
        redacted = json.loads((LOCAL_TRACE_DIR / "t1.json").read_text())
        assert redacted["user_id"] == "[REDACTED]"
        assert redacted["session_id"] == "[REDACTED]"

    @pytest.mark.asyncio
    async def test_feedback_deletion(
        self, deletion_service: DeletionService, mock_feedback_service: MagicMock
    ) -> None:
        """Test that feedback is deleted for the user."""
        receipt = await deletion_service.delete_user_data("user-1", tenant_id="t1")
        mock_feedback_service.delete_feedback_for_user.assert_called_once_with("user-1")
        assert receipt.feedback_deleted == 3
        assert receipt.steps["feedback"].status == "success"

    @pytest.mark.asyncio
    async def test_vectors_deleted_count(
        self, deletion_service: DeletionService, mock_vector_store: AsyncMock
    ) -> None:
        """vectors_deleted reflects the count returned by VectorStore."""
        mock_vector_store.delete_by_user.return_value = 12
        receipt = await deletion_service.delete_user_data("user-1", tenant_id="t1")
        assert receipt.vectors_deleted == 12
        assert receipt.steps["vectors"].count == 12
