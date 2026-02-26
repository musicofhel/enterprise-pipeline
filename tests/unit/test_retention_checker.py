"""Tests for RetentionChecker."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from src.services.retention_checker import RetentionChecker


def _write_json(directory: Path, filename: str, timestamp: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(json.dumps({"timestamp": timestamp, "created_at": timestamp}))
    return path


@pytest.fixture
def traces_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "traces" / "local"
    monkeypatch.setattr("src.services.retention_checker.LOCAL_TRACE_DIR", d)
    return d


@pytest.fixture
def feedback_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "feedback" / "local"
    monkeypatch.setattr("src.services.retention_checker.LOCAL_FEEDBACK_DIR", d)
    return d


class TestRetentionChecker:
    def test_find_expired_traces(self, traces_dir: Path) -> None:
        old = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        recent = datetime.now(UTC).isoformat()
        _write_json(traces_dir, "old.json", old)
        _write_json(traces_dir, "recent.json", recent)

        checker = RetentionChecker(traces_days=90)
        expired = checker.find_expired_traces()
        assert len(expired) == 1
        assert expired[0].name == "old.json"

    def test_find_expired_feedback(self, feedback_dir: Path) -> None:
        old = (datetime.now(UTC) - timedelta(days=400)).isoformat()
        _write_json(feedback_dir, "old.json", old)

        checker = RetentionChecker(feedback_days=365)
        expired = checker.find_expired_feedback()
        assert len(expired) == 1

    def test_purge_dry_run(self, traces_dir: Path) -> None:
        old = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        _write_json(traces_dir, "old.json", old)

        checker = RetentionChecker(traces_days=90)
        summary = checker.purge_expired(dry_run=True)
        assert summary["dry_run"] is True
        assert summary["expired_traces"] == 1
        assert summary["deleted_traces"] == 0
        # File still exists
        assert (traces_dir / "old.json").exists()

    def test_purge_actual(self, traces_dir: Path) -> None:
        old = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        _write_json(traces_dir, "old.json", old)

        checker = RetentionChecker(traces_days=90)
        summary = checker.purge_expired(dry_run=False)
        assert summary["deleted_traces"] == 1
        assert not (traces_dir / "old.json").exists()

    def test_empty_directories(self, traces_dir: Path, feedback_dir: Path) -> None:
        checker = RetentionChecker()
        assert checker.find_expired_traces() == []
        assert checker.find_expired_feedback() == []

    def test_no_expiry_within_retention(self, traces_dir: Path) -> None:
        recent = datetime.now(UTC).isoformat()
        _write_json(traces_dir, "recent.json", recent)

        checker = RetentionChecker(traces_days=90)
        assert checker.find_expired_traces() == []
