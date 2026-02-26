"""Data retention checker.

Scans local trace, feedback, and audit log directories for entries that
have exceeded their configured retention periods.  Supports dry-run mode.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from pathlib import Path

from src.observability.tracing import LOCAL_TRACE_DIR
from src.services.feedback_service import LOCAL_FEEDBACK_DIR

logger = structlog.get_logger()


class RetentionChecker:
    """Find and purge data that exceeds retention TTLs."""

    def __init__(
        self,
        traces_days: int = 90,
        feedback_days: int = 365,
    ) -> None:
        self._traces_days = traces_days
        self._feedback_days = feedback_days

    def find_expired_traces(self) -> list[Path]:
        """Return paths of trace files older than retention period."""
        return self._find_expired(LOCAL_TRACE_DIR, self._traces_days)

    def find_expired_feedback(self) -> list[Path]:
        """Return paths of feedback files older than retention period."""
        return self._find_expired(LOCAL_FEEDBACK_DIR, self._feedback_days)

    def purge_expired(self, dry_run: bool = True) -> dict[str, Any]:
        """Purge expired data.  Returns summary of actions taken.

        When ``dry_run=True`` (default), no files are deleted — only a
        report of what *would* be deleted is returned.
        """
        expired_traces = self.find_expired_traces()
        expired_feedback = self.find_expired_feedback()

        deleted_traces = 0
        deleted_feedback = 0

        if not dry_run:
            for path in expired_traces:
                try:
                    path.unlink()
                    deleted_traces += 1
                except OSError:
                    logger.warning("retention_delete_failed", path=str(path))

            for path in expired_feedback:
                try:
                    path.unlink()
                    deleted_feedback += 1
                except OSError:
                    logger.warning("retention_delete_failed", path=str(path))

        summary: dict[str, Any] = {
            "dry_run": dry_run,
            "expired_traces": len(expired_traces),
            "expired_feedback": len(expired_feedback),
            "deleted_traces": deleted_traces,
            "deleted_feedback": deleted_feedback,
        }
        logger.info("retention_check_complete", **summary)
        return summary

    @staticmethod
    def _find_expired(directory: Path, max_age_days: int) -> list[Path]:
        """Scan a directory of JSON files and return those past their TTL."""
        if not directory.exists():
            return []

        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        expired: list[Path] = []

        for path in directory.glob("*.json"):
            try:
                data: dict[str, Any] = json.loads(path.read_text())
                # Support both 'timestamp' (traces/audit) and 'created_at' (feedback)
                ts_str = data.get("timestamp") or data.get("created_at")
                if not ts_str:
                    continue
                # Handle timezone-aware and naive datetimes
                ts = datetime.fromisoformat(str(ts_str))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if ts < cutoff:
                    expired.append(path)
            except (json.JSONDecodeError, ValueError, OSError):
                continue

        return expired
