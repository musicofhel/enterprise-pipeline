"""Tests for TracingService with local JSON fallback.

These tests run WITHOUT a Langfuse server. The local fallback writes real
JSON trace files that match the tech spec schema (Section 2.2 of 04-technical-specs.md).
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime

import pytest

from src.observability.tracing import LOCAL_TRACE_DIR, TracingService

# Required span names per tech spec Section 2.2
REQUIRED_SPANS = [
    "input_safety",
    "query_routing",
    "retrieval",
    "compression",
    "generation",
    "hallucination_check",
]

# Required top-level fields per trace schema
REQUIRED_TRACE_FIELDS = [
    "trace_id",
    "timestamp",
    "user_id",
    "session_id",
    "pipeline_version",
    "config_hash",
    "feature_flags",
    "spans",
    "scores",
    "total_latency_ms",
    "total_cost_usd",
]


@pytest.fixture(autouse=True)
def _clean_traces():
    """Clean up trace files before and after each test."""
    if LOCAL_TRACE_DIR.exists():
        shutil.rmtree(LOCAL_TRACE_DIR)
    yield
    if LOCAL_TRACE_DIR.exists():
        shutil.rmtree(LOCAL_TRACE_DIR)


def test_local_trace_file_created():
    """Running a pipeline query creates a local trace file."""
    service = TracingService(client=None, local_fallback=True)
    trace = service.create_trace(
        name="test_query",
        user_id="test-user",
        session_id="test-session",
        metadata={"tenant_id": "test-tenant"},
    )

    with trace.span("input_safety") as span:
        span.set_attribute("passed", True)

    with trace.span("query_routing") as span:
        span.set_attribute("route", "rag_knowledge_base")

    path = trace.save_local()
    assert path is not None
    assert path.exists()
    assert path.suffix == ".json"


def test_trace_contains_all_required_fields():
    """Trace JSON has all fields from tech spec Section 2.2."""
    service = TracingService(client=None, local_fallback=True)
    trace = service.create_trace(
        name="test_query",
        user_id="user-123",
        session_id="session-456",
    )

    # Simulate a pipeline execution with all spans
    with trace.span("input_safety") as span:
        span.set_attribute("layer_1_result", "pass")
        span.set_attribute("pii_detected", False)

    with trace.span("query_routing") as span:
        span.set_attribute("route_selected", "rag_knowledge_base")
        span.set_attribute("confidence", 0.89)

    with trace.span("retrieval") as span:
        span.set_attribute("num_results_raw", 20)
        span.set_attribute("num_results_after_dedup", 14)

    with trace.span("compression") as span:
        span.set_attribute("tokens_before", 6200)
        span.set_attribute("tokens_after", 2400)
        span.set_attribute("compression_ratio", 0.61)
        span.set_attribute("method", "bm25_subscoring")

    with trace.generation("generation", model="anthropic/claude-sonnet-4-5") as gen:
        gen.set_output("Test answer", usage={"input": 2800, "output": 350})

    with trace.span("hallucination_check") as span:
        span.set_attribute("score", 0.94)
        span.set_attribute("passed", True)
        span.set_attribute("model", "vectara/hallucination_evaluation_model")

    trace.set_score("faithfulness", 0.94)
    path = trace.save_local()

    data = json.loads(path.read_text())

    for field in REQUIRED_TRACE_FIELDS:
        assert field in data, f"Missing required field: {field}"

    assert data["user_id"] == "user-123"
    assert data["session_id"] == "session-456"


def test_all_spans_have_timing():
    """Every span must have start_time, end_time, and duration_ms > 0."""
    service = TracingService(client=None, local_fallback=True)
    trace = service.create_trace(name="test", user_id="u1")

    for span_name in REQUIRED_SPANS:
        if span_name == "generation":
            with trace.generation(span_name, model="anthropic/claude-sonnet-4-5") as gen:
                gen.set_output("answer", usage={"input": 100, "output": 50})
        else:
            with trace.span(span_name) as span:
                span.set_attribute("test", True)

    path = trace.save_local()
    data = json.loads(path.read_text())

    for span_data in data["spans"]:
        assert "start_time" in span_data, f"Span {span_data['name']} missing start_time"
        assert "end_time" in span_data, f"Span {span_data['name']} missing end_time"
        assert "duration_ms" in span_data, f"Span {span_data['name']} missing duration_ms"
        assert span_data["duration_ms"] >= 0, (
            f"Span {span_data['name']} has negative duration"
        )
        # Validate ISO 8601 timestamps
        datetime.fromisoformat(span_data["start_time"])
        datetime.fromisoformat(span_data["end_time"])


def test_trace_includes_faithfulness_score():
    """Trace should include faithfulness_score from HHEM check."""
    service = TracingService(client=None, local_fallback=True)
    trace = service.create_trace(name="test", user_id="u1")

    with trace.span("hallucination_check") as span:
        span.set_attribute("score", 0.91)

    trace.set_score("faithfulness", 0.91)
    path = trace.save_local()
    data = json.loads(path.read_text())

    assert data["scores"]["faithfulness"] == 0.91
    assert data["scores"]["user_feedback"] is None  # Not set yet


def test_config_hash_is_valid_sha256():
    """config_hash should be a valid 64-char hex string (SHA256)."""
    service = TracingService(client=None, local_fallback=True)
    trace = service.create_trace(name="test", user_id="u1")
    path = trace.save_local()
    data = json.loads(path.read_text())

    config_hash = data["config_hash"]
    assert re.match(r"^[a-f0-9]{64}$", config_hash), (
        f"config_hash is not a valid SHA256: {config_hash}"
    )


def test_trace_schema_matches_tech_spec():
    """Full schema validation against Section 2.2 of 04-technical-specs.md."""
    service = TracingService(client=None, local_fallback=True)
    trace = service.create_trace(
        name="pipeline_query",
        user_id="user-abc",
        session_id="session-xyz",
    )

    # Full pipeline simulation
    with trace.span("input_safety") as span:
        span.set_attribute("layer_1_result", "pass")
        span.set_attribute("layer_2_result", "pass")
        span.set_attribute("layer_2_confidence", 0.97)
        span.set_attribute("pii_detected", False)
        span.set_attribute("pii_types", [])

    with trace.span("query_routing") as span:
        span.set_attribute("route_selected", "rag_knowledge_base")
        span.set_attribute("confidence", 0.89)
        span.set_attribute("all_route_scores", {"rag": 0.89, "sql": 0.12, "direct": 0.05})

    with trace.span("retrieval") as span:
        span.set_attribute("num_results_raw", 20)
        span.set_attribute("num_results_after_dedup", 14)
        span.set_attribute("num_results_after_rerank", 5)
        span.set_attribute("top_cosine_sim", 0.87)
        span.set_attribute("mean_cosine_sim", 0.72)

    with trace.span("compression") as span:
        span.set_attribute("tokens_before", 6200)
        span.set_attribute("tokens_after", 2400)
        span.set_attribute("compression_ratio", 0.61)
        span.set_attribute("method", "bm25_subscoring")

    with trace.generation("generation", model="anthropic/claude-sonnet-4-5") as gen:
        gen.set_output("Test answer about remote work policy.", usage={"input": 2800, "output": 350})

    with trace.span("hallucination_check") as span:
        span.set_attribute("model", "vectara/hhem-2.1")
        span.set_attribute("score", 0.94)
        span.set_attribute("passed", True)
        span.set_attribute("latency_ms", 85)

    trace.set_score("faithfulness", 0.94)
    path = trace.save_local()
    data = json.loads(path.read_text())

    # Validate top-level structure
    assert isinstance(data["trace_id"], str)
    assert isinstance(data["timestamp"], str)
    assert isinstance(data["pipeline_version"], str)
    assert isinstance(data["config_hash"], str)
    assert isinstance(data["feature_flags"], dict)
    assert isinstance(data["spans"], list)
    assert isinstance(data["scores"], dict)
    assert isinstance(data["total_latency_ms"], (int, float))
    assert isinstance(data["total_cost_usd"], (int, float))

    # Validate spans exist
    span_names = {s["name"] for s in data["spans"]}
    for required in REQUIRED_SPANS:
        assert required in span_names, f"Missing required span: {required}"

    # Validate scores
    assert "faithfulness" in data["scores"]
    assert "user_feedback" in data["scores"]
