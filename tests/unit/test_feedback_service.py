"""Tests for FeedbackService."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from src.observability.audit_log import AuditLogService
from src.services.feedback_service import FeedbackService


@pytest.fixture
def audit_service(tmp_path: Path) -> AuditLogService:
    return AuditLogService(storage_dir=tmp_path / "audit")


@pytest.fixture
def feedback_service(audit_service: AuditLogService, tmp_path: Path) -> FeedbackService:
    return FeedbackService(audit_log=audit_service, storage_dir=tmp_path / "feedback")


class TestFeedbackService:
    def test_record_feedback_returns_id(self, feedback_service: FeedbackService) -> None:
        fid = feedback_service.record_feedback("trace-1", "user-1", "positive")
        assert fid  # non-empty UUID string

    def test_record_feedback_creates_file(
        self, feedback_service: FeedbackService, tmp_path: Path
    ) -> None:
        fid = feedback_service.record_feedback("trace-1", "user-1", "positive")
        assert (tmp_path / "feedback" / f"{fid}.json").exists()

    def test_get_feedback_round_trip(self, feedback_service: FeedbackService) -> None:
        fid = feedback_service.record_feedback(
            "trace-1", "user-1", "negative", correction="should be X", comment="wrong"
        )
        data = feedback_service.get_feedback(fid)
        assert data is not None
        assert data["trace_id"] == "trace-1"
        assert data["rating"] == "negative"
        assert data["correction"] == "should be X"

    def test_record_feedback_creates_audit_event(
        self, feedback_service: FeedbackService, audit_service: AuditLogService
    ) -> None:
        feedback_service.record_feedback("trace-1", "user-1", "positive")
        events = audit_service.list_events()
        assert len(events) == 1
        assert events[0].event_type.value == "feedback"

    def test_delete_feedback_for_user(self, feedback_service: FeedbackService) -> None:
        feedback_service.record_feedback("trace-1", "user-1", "positive")
        feedback_service.record_feedback("trace-2", "user-1", "negative")
        feedback_service.record_feedback("trace-3", "user-2", "positive")

        deleted = feedback_service.delete_feedback_for_user("user-1")
        assert deleted == 2

        remaining = feedback_service.list_feedback_for_user("user-2")
        assert len(remaining) == 1
