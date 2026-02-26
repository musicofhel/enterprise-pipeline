"""Tests for failure triage (Wave 7.2).

Covers classification, clustering, report structure, sorting, and empty state.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.flywheel.failure_triage import FailureTriageService


def _make_trace(
    trace_id: str | None = None,
    faithfulness: float | None = None,
    retrieval_scores: list[float] | None = None,
    result_count: int | None = None,
    feedback: str | None = None,
    route_confidence: float = 0.9,
    compression_ratio: float = 0.5,
    route: str = "rag_knowledge_base",
    query: str = "test query",
    answer: str = "test answer",
) -> dict[str, Any]:
    """Build a synthetic trace matching the local trace schema."""
    tid = trace_id or str(uuid4())
    r_scores = retrieval_scores or [0.8, 0.75, 0.7]
    rc = result_count if result_count is not None else len(r_scores)

    return {
        "trace_id": tid,
        "timestamp": datetime.now(UTC).isoformat(),
        "user_id": "user-1",
        "session_id": "",
        "pipeline_version": "test",
        "config_hash": "test",
        "feature_flags": {"pipeline_variant": "control"},
        "metadata": {"query": query},
        "spans": [
            {
                "name": "query_routing",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "duration_ms": 1.0,
                "attributes": {"route": route, "confidence": route_confidence},
            },
            {
                "name": "retrieval",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "duration_ms": 50.0,
                "attributes": {
                    "result_scores": r_scores,
                    "num_results_after_rerank": rc,
                    "skipped": False,
                },
            },
            {
                "name": "compression",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "duration_ms": 5.0,
                "attributes": {"compression_ratio": compression_ratio},
            },
            {
                "name": "generation",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "duration_ms": 200.0,
                "attributes": {"output": answer, "model": "test-model"},
            },
            {
                "name": "hallucination_check",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": datetime.now(UTC).isoformat(),
                "duration_ms": 100.0,
                "attributes": {"score": faithfulness, "passed": (faithfulness or 0) > 0.7},
            },
        ],
        "scores": {
            "faithfulness": faithfulness,
            "user_feedback": feedback,
        },
        "total_latency_ms": 400.0,
        "total_cost_usd": 0.01,
    }


def _write_traces(traces_dir: Path, traces: list[dict[str, Any]]) -> None:
    traces_dir.mkdir(parents=True, exist_ok=True)
    for t in traces:
        path = traces_dir / f"{t['trace_id']}.json"
        path.write_text(json.dumps(t, indent=2, default=str))


class TestClassification:
    """Test 1: Create 50 synthetic traces with known failure patterns, assert correct classification."""

    def test_classify_known_patterns(self, tmp_path: Path) -> None:
        traces_dir = tmp_path / "traces"
        traces: list[dict[str, Any]] = []
        expected: dict[str, int] = {
            "retrieval_failure": 0,
            "hallucination": 0,
            "context_gap": 0,
            "wrong_route": 0,
            "compression_loss": 0,
        }

        # 10 retrieval failures — low scores, few results
        for i in range(10):
            traces.append(_make_trace(
                trace_id=f"ret-fail-{i}",
                faithfulness=0.3,
                retrieval_scores=[0.1, 0.2],
                result_count=2,
            ))
            expected["retrieval_failure"] += 1

        # 10 hallucinations — good retrieval, low faithfulness
        for i in range(10):
            traces.append(_make_trace(
                trace_id=f"halluc-{i}",
                faithfulness=0.4,
                retrieval_scores=[0.8, 0.75, 0.7],
                result_count=3,
            ))
            expected["hallucination"] += 1

        # 10 context gaps — good retrieval, ok faithfulness, but negative feedback
        for i in range(10):
            traces.append(_make_trace(
                trace_id=f"ctx-gap-{i}",
                faithfulness=0.8,
                retrieval_scores=[0.7, 0.65, 0.6],
                result_count=3,
                feedback="negative",
            ))
            expected["context_gap"] += 1

        # 5 wrong routes — negative feedback, low route confidence
        for i in range(5):
            traces.append(_make_trace(
                trace_id=f"wrong-route-{i}",
                faithfulness=0.3,
                retrieval_scores=[0.1, 0.15],
                result_count=2,
                feedback="negative",
                route_confidence=0.1,
            ))
            # Low retrieval scores → classified as retrieval_failure first
            expected["retrieval_failure"] += 1

        # 5 compression losses — high compression ratio, negative feedback
        for i in range(5):
            traces.append(_make_trace(
                trace_id=f"comp-loss-{i}",
                faithfulness=0.5,
                retrieval_scores=[0.5, 0.45],
                result_count=2,
                compression_ratio=0.9,
                feedback="negative",
            ))

        # 10 successes — high everything
        for i in range(10):
            traces.append(_make_trace(
                trace_id=f"success-{i}",
                faithfulness=0.95,
                retrieval_scores=[0.9, 0.85, 0.8],
                result_count=3,
            ))

        _write_traces(traces_dir, traces)

        service = FailureTriageService(traces_dir=traces_dir)
        report = service.triage(days=7)

        # Should have identified failures (not all 50 — successes excluded)
        assert report["total_responses"] == 50
        assert report["total_failures"] > 0
        assert report["total_failures"] < 50  # 10 successes should not be failures
        assert "retrieval_failure" in report["by_category"]
        assert "hallucination" in report["by_category"]
        assert report["by_category"]["retrieval_failure"]["count"] >= 10
        assert report["by_category"]["hallucination"]["count"] >= 10


class TestClustering:
    """Test 2: Assert clustering groups similar queries together."""

    def test_clusters_similar_queries(self, tmp_path: Path) -> None:
        traces_dir = tmp_path / "traces"

        german_tax_queries = [
            "What are the tax implications for remote workers in Germany?",
            "How are taxes calculated for German remote employees?",
            "German tax rules for people working from home",
            "Remote work taxation in Germany explained",
            "Tax requirements for German home office workers",
        ]
        japan_visa_queries = [
            "How to get a work visa in Japan?",
            "Japan work visa application process",
            "Requirements for Japanese work permit",
            "Applying for employment visa in Japan",
            "Japan visa for foreign workers",
        ]

        traces = []
        for q in german_tax_queries:
            traces.append(_make_trace(
                faithfulness=0.3,
                retrieval_scores=[0.2, 0.15],
                query=q,
            ))
        for q in japan_visa_queries:
            traces.append(_make_trace(
                faithfulness=0.3,
                retrieval_scores=[0.2, 0.15],
                query=q,
            ))

        _write_traces(traces_dir, traces)

        # Use a simple mock embedding function that groups by keyword
        def mock_embed(texts: list[str]) -> list[list[float]]:
            embeddings = []
            for t in texts:
                t_lower = t.lower()
                if "german" in t_lower or "germany" in t_lower:
                    # Orthogonal direction for German queries
                    embeddings.append([1.0] * 192 + [0.0] * 192)
                elif "japan" in t_lower or "japanese" in t_lower:
                    # Orthogonal direction for Japan queries
                    embeddings.append([0.0] * 192 + [1.0] * 192)
                else:
                    embeddings.append([0.5] * 384)
            return embeddings

        service = FailureTriageService(traces_dir=traces_dir, embed_fn=mock_embed)
        report = service.triage(days=7)

        # Should form 2 clusters
        assert len(report["clusters"]) == 2
        cluster_sizes = sorted([c["size"] for c in report["clusters"]])
        assert cluster_sizes == [5, 5]


class TestReportStructure:
    """Test 3: Assert the report contains all required fields."""

    def test_report_fields(self, tmp_path: Path) -> None:
        traces_dir = tmp_path / "traces"
        traces = [_make_trace(faithfulness=0.3, retrieval_scores=[0.1])]
        _write_traces(traces_dir, traces)

        service = FailureTriageService(traces_dir=traces_dir)
        report = service.triage(days=7)

        assert "period" in report
        assert "start" in report["period"]
        assert "end" in report["period"]
        assert "total_responses" in report
        assert "total_failures" in report
        assert "failure_rate" in report
        assert "by_category" in report
        assert "clusters" in report
        assert "top_failures" in report


class TestTopFailuresSorting:
    """Test 4: Assert top_failures are sorted by severity (lowest faithfulness first)."""

    def test_sorted_by_faithfulness(self, tmp_path: Path) -> None:
        traces_dir = tmp_path / "traces"
        traces = [
            _make_trace(trace_id="high", faithfulness=0.65, retrieval_scores=[0.8, 0.7]),
            _make_trace(trace_id="low", faithfulness=0.2, retrieval_scores=[0.8, 0.7]),
            _make_trace(trace_id="mid", faithfulness=0.4, retrieval_scores=[0.8, 0.7]),
        ]
        _write_traces(traces_dir, traces)

        service = FailureTriageService(traces_dir=traces_dir)
        report = service.triage(days=7)

        scores = [f["faithfulness_score"] for f in report["top_failures"]]
        assert scores == sorted(scores)


class TestEmptyState:
    """Test 5: With no traces → report says period had 0 responses."""

    def test_empty_traces(self, tmp_path: Path) -> None:
        traces_dir = tmp_path / "empty_traces"

        service = FailureTriageService(traces_dir=traces_dir)
        report = service.triage(days=7)

        assert report["total_responses"] == 0
        assert report["total_failures"] == 0
        assert report["failure_rate"] == 0.0
        assert report["by_category"] == {}
        assert report["clusters"] == []
        assert report["top_failures"] == []
