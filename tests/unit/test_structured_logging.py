"""Tests for structured logging.

Verifies that:
1. All log output is valid JSON (when configured for JSON mode)
2. Every log line has required fields: timestamp, level, event, trace_id
3. No print() statements exist in src/
4. The full lifecycle of events appears in order
"""
from __future__ import annotations

import json
from pathlib import Path

from src.observability.logging import bind_trace_context, clear_trace_context, setup_logging


def test_json_log_output_is_valid_json(capsys):
    """All log output in JSON mode must be parseable JSON."""
    import structlog

    setup_logging(log_level="DEBUG", log_format="json", pipeline_version="test-v1")

    logger = structlog.get_logger("test")
    bind_trace_context(trace_id="trace-123", user_id="user-456")

    logger.info("pipeline.request.received", query="test query")
    logger.info("pipeline.safety.checked", passed=True, latency_ms=1)
    logger.info("pipeline.routing.completed", route="rag_knowledge_base", confidence=0.89)
    logger.info("pipeline.request.completed", total_latency_ms=42, fallback=False)

    clear_trace_context()

    captured = capsys.readouterr()
    lines = [line.strip() for line in captured.out.strip().split("\n") if line.strip()]

    assert len(lines) >= 4, f"Expected at least 4 log lines, got {len(lines)}"

    for line in lines:
        parsed = json.loads(line)  # Will raise if not valid JSON
        assert "event" in parsed, f"Log line missing 'event': {line}"
        assert "timestamp" in parsed, f"Log line missing 'timestamp': {line}"
        assert "level" in parsed, f"Log line missing 'level': {line}"


def test_trace_id_bound_to_all_log_lines(capsys):
    """Every log line after bind_trace_context should have trace_id."""
    import structlog

    setup_logging(log_level="DEBUG", log_format="json", pipeline_version="test-v1")

    logger = structlog.get_logger("test_trace_binding")
    bind_trace_context(trace_id="trace-abc-123", user_id="user-xyz")

    logger.info("test_event_1")
    logger.info("test_event_2")

    clear_trace_context()

    captured = capsys.readouterr()
    lines = [line.strip() for line in captured.out.strip().split("\n") if line.strip()]

    for line in lines:
        parsed = json.loads(line)
        assert parsed.get("trace_id") == "trace-abc-123", (
            f"Expected trace_id='trace-abc-123', got '{parsed.get('trace_id')}' in: {line}"
        )
        assert parsed.get("user_id") == "user-xyz"


def test_pipeline_version_in_logs(capsys):
    """pipeline_version should appear in every log line."""
    import structlog

    setup_logging(log_level="DEBUG", log_format="json", pipeline_version="abc1234")

    logger = structlog.get_logger("test_version")
    logger.info("test_event")

    captured = capsys.readouterr()
    lines = [line.strip() for line in captured.out.strip().split("\n") if line.strip()]
    assert len(lines) >= 1

    parsed = json.loads(lines[0])
    assert parsed.get("pipeline_version") == "abc1234"


def test_no_print_statements_in_src():
    """No print() statements should exist in src/ directory."""
    src_dir = Path("src")
    violations = []

    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text()
        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            # Skip comments and strings
            if stripped.startswith("#"):
                continue
            if "print(" in stripped and not stripped.startswith(("'", '"', "#")):
                violations.append(f"{py_file}:{i}: {stripped}")

    assert not violations, (
        "Found print() statements in src/:\n" + "\n".join(violations)
    )
