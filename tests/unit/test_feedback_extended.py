"""Tests for extended FeedbackService (Wave 7.1).

Covers feedback stats, trace linking, context storage, Prometheus metrics,
and feedback rate calculation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.observability.audit_log import AuditLogService
from src.observability.metrics import (
    FEEDBACK_CORRECTION_RECEIVED_TOTAL,
    FEEDBACK_RECEIVED_TOTAL,
)
from src.services.feedback_service import FeedbackService


@pytest.fixture()
def feedback_dir(tmp_path: Path) -> Path:
    return tmp_path / "feedback"


@pytest.fixture()
def audit_log(tmp_path: Path) -> AuditLogService:
    return AuditLogService(storage_dir=tmp_path / "audit")


@pytest.fixture()
def service(audit_log: AuditLogService, feedback_dir: Path) -> FeedbackService:
    return FeedbackService(audit_log=audit_log, storage_dir=feedback_dir)


def _reset_metrics() -> None:
    """Reset feedback counters for test isolation."""
    # Clear counter samples by recreating — simpler: just read deltas
    pass


class TestFeedbackStats:
    """Test 1: Submit 10 feedback events, assert stats are correct."""

    def test_feedback_stats_counts(self, service: FeedbackService) -> None:
        # Record 10 responses for rate calculation
        for _ in range(10):
            service.record_response()

        # 7 positive, 3 negative, 1 with correction
        for i in range(7):
            service.record_feedback(
                trace_id=f"trace-{i}",
                user_id=f"user-{i}",
                rating="positive",
            )
        for i in range(7, 10):
            correction = "Correct answer is X" if i == 9 else None
            service.record_feedback(
                trace_id=f"trace-{i}",
                user_id=f"user-{i}",
                rating="negative",
                correction=correction,
            )

        stats = service.get_feedback_stats(days=7)
        assert stats["feedback_received"] == 10
        assert stats["positive"] == 7
        assert stats["negative"] == 3
        assert stats["with_correction"] == 1
        assert stats["period"] == "last_7_days"


class TestTraceLinking:
    """Test 2: Assert each feedback event links to a valid trace_id."""

    def test_feedback_linked_to_trace(self, service: FeedbackService) -> None:
        trace_ids = [f"trace-{i}" for i in range(5)]
        feedback_ids = []
        for tid in trace_ids:
            fid = service.record_feedback(
                trace_id=tid,
                user_id="user-1",
                rating="positive",
            )
            feedback_ids.append(fid)

        for fid, expected_tid in zip(feedback_ids, trace_ids, strict=True):
            fb = service.get_feedback(fid)
            assert fb is not None
            assert fb["trace_id"] == expected_tid

    def test_list_feedback_for_trace(self, service: FeedbackService) -> None:
        service.record_feedback(trace_id="t1", user_id="u1", rating="positive")
        service.record_feedback(trace_id="t1", user_id="u2", rating="negative")
        service.record_feedback(trace_id="t2", user_id="u1", rating="positive")

        t1_feedback = service.list_feedback_for_trace("t1")
        assert len(t1_feedback) == 2
        assert all(fb["trace_id"] == "t1" for fb in t1_feedback)


class TestContextStorage:
    """Test 3: Assert feedback events contain query, answer, route, faithfulness_score."""

    def test_feedback_stores_context(self, service: FeedbackService) -> None:
        fid = service.record_feedback(
            trace_id="trace-42",
            user_id="user-1",
            rating="negative",
            query="What is the company vacation policy?",
            answer="Employees get unlimited PTO.",
            route="rag_knowledge_base",
            faithfulness_score=0.42,
            correction="Employees get 20 days PTO per year.",
        )

        fb = service.get_feedback(fid)
        assert fb is not None
        assert fb["query"] == "What is the company vacation policy?"
        assert fb["answer"] == "Employees get unlimited PTO."
        assert fb["route"] == "rag_knowledge_base"
        assert fb["faithfulness_score"] == 0.42
        assert fb["correction"] == "Employees get 20 days PTO per year."


class TestPrometheusMetrics:
    """Test 4: Assert Prometheus metrics increment correctly."""

    def test_feedback_metrics_increment(self, service: FeedbackService) -> None:
        # Get baseline values
        pos_before = FEEDBACK_RECEIVED_TOTAL.labels(rating="positive")._value.get()
        neg_before = FEEDBACK_RECEIVED_TOTAL.labels(rating="negative")._value.get()
        corr_before = FEEDBACK_CORRECTION_RECEIVED_TOTAL._value.get()

        service.record_feedback(trace_id="t1", user_id="u1", rating="positive")
        service.record_feedback(trace_id="t2", user_id="u2", rating="negative")
        service.record_feedback(
            trace_id="t3", user_id="u3", rating="negative",
            correction="Fixed answer",
        )

        pos_after = FEEDBACK_RECEIVED_TOTAL.labels(rating="positive")._value.get()
        neg_after = FEEDBACK_RECEIVED_TOTAL.labels(rating="negative")._value.get()
        corr_after = FEEDBACK_CORRECTION_RECEIVED_TOTAL._value.get()

        assert pos_after - pos_before == 1
        assert neg_after - neg_before == 2
        assert corr_after - corr_before == 1


class TestFeedbackRate:
    """Test 5: Assert feedback_rate calculation is correct."""

    def test_feedback_rate(self, service: FeedbackService) -> None:
        # 10 responses, 2 feedback events → rate = 0.2
        for _ in range(10):
            service.record_response()

        service.record_feedback(trace_id="t1", user_id="u1", rating="positive")
        service.record_feedback(trace_id="t2", user_id="u2", rating="negative")

        stats = service.get_feedback_stats(days=7)
        assert stats["total_responses"] == 10
        assert stats["feedback_received"] == 2
        assert stats["feedback_rate"] == 0.2

    def test_feedback_rate_zero_responses(self, service: FeedbackService) -> None:
        stats = service.get_feedback_stats(days=7)
        assert stats["feedback_rate"] == 0.0
        assert stats["total_responses"] == 0
