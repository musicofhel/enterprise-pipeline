"""Failure triage workflow.

Scans production traces, classifies failures by pattern, clusters similar
failures using embedding similarity, and produces a weekly triage report.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()

# Default classification thresholds (configurable)
DEFAULT_THRESHOLDS = {
    "retrieval_score_low": 0.4,
    "faithfulness_low": 0.7,
    "retrieval_score_ok": 0.6,
    "route_confidence_low": 0.3,
    "compression_ratio_high": 0.8,
    "retrieval_score_mid": 0.5,
}

FAILURE_CATEGORIES = [
    "retrieval_failure",
    "hallucination",
    "wrong_route",
    "context_gap",
    "compression_loss",
    "other",
]


class FailureTriageService:
    """Scan traces, classify failures, cluster, and produce triage reports."""

    def __init__(
        self,
        traces_dir: Path = Path("traces/local"),
        thresholds: dict[str, float] | None = None,
        embed_fn: Any | None = None,
    ) -> None:
        self._traces_dir = traces_dir
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._embed_fn = embed_fn

    def scan_traces(self, days: int = 7) -> list[dict[str, Any]]:
        """Load all traces from the last N days."""
        if not self._traces_dir.exists():
            return []

        cutoff = datetime.now(UTC) - timedelta(days=days)
        traces: list[dict[str, Any]] = []

        for path in self._traces_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                ts = data.get("timestamp", "")
                if ts and ts >= cutoff.isoformat():
                    traces.append(data)
            except (json.JSONDecodeError, OSError):
                continue

        return traces

    def _extract_trace_features(self, trace: dict[str, Any]) -> dict[str, Any]:
        """Extract classification-relevant features from a trace."""
        spans = {s["name"]: s for s in trace.get("spans", [])}
        scores = trace.get("scores", {})

        # Retrieval features
        retrieval_span = spans.get("retrieval", {})
        retrieval_attrs = retrieval_span.get("attributes", {})
        result_scores = retrieval_attrs.get("result_scores", [])
        result_count = retrieval_attrs.get("num_results_after_rerank",
                       retrieval_attrs.get("num_results_raw", 0))
        retrieval_scores_mean = float(np.mean(result_scores)) if result_scores else 0.0
        skipped_retrieval = retrieval_attrs.get("skipped", False)

        # Compression features
        compression_span = spans.get("compression", {})
        comp_attrs = compression_span.get("attributes", {})
        compression_ratio = comp_attrs.get("compression_ratio", 0.0)

        # Hallucination features
        hall_span = spans.get("hallucination_check", {})
        hall_attrs = hall_span.get("attributes", {})
        faithfulness_score = scores.get("faithfulness")
        if faithfulness_score is None:
            faithfulness_score = hall_attrs.get("score")

        # Route features
        route_span = spans.get("query_routing", {})
        route_attrs = route_span.get("attributes", {})
        route = route_attrs.get("route", "unknown")
        route_confidence = route_attrs.get("confidence", 1.0)

        # Feedback (if stored in trace)
        feedback = scores.get("user_feedback")

        return {
            "trace_id": trace.get("trace_id", ""),
            "query": trace.get("metadata", {}).get("query", ""),
            "retrieval_scores_mean": retrieval_scores_mean,
            "result_count": result_count,
            "faithfulness_score": faithfulness_score,
            "compression_ratio": compression_ratio,
            "route": route,
            "route_confidence": route_confidence if route_confidence is not None else 1.0,
            "feedback": feedback,
            "skipped_retrieval": skipped_retrieval,
        }

    def classify_failure(self, features: dict[str, Any]) -> str | None:
        """Classify a trace into a failure category. Returns None if not a failure."""
        t = self._thresholds
        faith = features.get("faithfulness_score")
        ret_mean = features.get("retrieval_scores_mean", 0.0)
        result_count = features.get("result_count", 0)
        feedback = features.get("feedback")
        route_conf = features.get("route_confidence", 1.0)
        comp_ratio = features.get("compression_ratio", 0.0)
        skipped = features.get("skipped_retrieval", False)

        # Skip traces with no generation (direct_llm skips retrieval)
        if skipped:
            return None

        is_failure = False

        # Negative feedback always counts
        if feedback == "negative":
            is_failure = True

        # Low faithfulness
        if faith is not None and faith < t["faithfulness_low"]:
            is_failure = True

        # No results
        if result_count == 0 and not skipped:
            is_failure = True

        if not is_failure:
            return None

        # Classification logic
        if ret_mean < t["retrieval_score_low"] or result_count == 0:
            return "retrieval_failure"

        if faith is not None and faith < t["faithfulness_low"] and ret_mean > t["retrieval_score_ok"]:
            return "hallucination"

        if feedback == "negative" and route_conf < t["route_confidence_low"]:
            return "wrong_route"

        if result_count > 0 and comp_ratio > t["compression_ratio_high"]:
            return "compression_loss"

        if ret_mean > t["retrieval_score_mid"] and (faith is None or faith > t["faithfulness_low"]):
            return "context_gap"

        return "other"

    def cluster_failures(
        self,
        failures: list[dict[str, Any]],
        threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Cluster failures by query embedding similarity."""
        if not failures or self._embed_fn is None:
            return []

        queries = [f.get("query", "") or f.get("trace_id", "") for f in failures]

        # Get embeddings
        try:
            embeddings = self._embed_fn(queries)
            if isinstance(embeddings, list) and len(embeddings) > 0:
                embeddings = np.array(embeddings)
            else:
                return []
        except Exception:
            logger.warning("clustering_failed", reason="embedding error")
            return []

        # Simple greedy clustering
        n = len(embeddings)
        assigned = [-1] * n
        cluster_id = 0

        # Normalize for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normed = embeddings / norms

        for i in range(n):
            if assigned[i] >= 0:
                continue
            assigned[i] = cluster_id
            for j in range(i + 1, n):
                if assigned[j] >= 0:
                    continue
                sim = float(np.dot(normed[i], normed[j]))
                if sim >= threshold:
                    assigned[j] = cluster_id
            cluster_id += 1

        # Build cluster objects
        clusters_map: dict[int, list[int]] = defaultdict(list)
        for idx, cid in enumerate(assigned):
            clusters_map[cid].append(idx)

        clusters = []
        for cid, indices in sorted(clusters_map.items()):
            if len(indices) < 2:
                continue  # Skip singletons
            rep_idx = indices[0]
            clusters.append({
                "cluster_id": cid,
                "size": len(indices),
                "representative_query": queries[rep_idx],
                "category": failures[rep_idx].get("category", "unknown"),
                "trace_ids": [failures[i]["trace_id"] for i in indices],
            })

        return clusters

    def triage(self, days: int = 7) -> dict[str, Any]:
        """Run full triage: scan → classify → cluster → report."""
        traces = self.scan_traces(days=days)

        if not traces:
            now = datetime.now(UTC)
            start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
            end = now.strftime("%Y-%m-%d")
            return {
                "period": {"start": start, "end": end},
                "total_responses": 0,
                "total_failures": 0,
                "failure_rate": 0.0,
                "by_category": {},
                "clusters": [],
                "top_failures": [],
            }

        failures: list[dict[str, Any]] = []
        by_category: dict[str, dict[str, Any]] = {cat: {"count": 0, "example_trace_ids": []} for cat in FAILURE_CATEGORIES}

        for trace in traces:
            features = self._extract_trace_features(trace)
            category = self.classify_failure(features)

            if category is not None:
                failure_entry = {
                    **features,
                    "category": category,
                    "answer": self._extract_answer(trace),
                }
                failures.append(failure_entry)
                by_category[category]["count"] += 1
                if len(by_category[category]["example_trace_ids"]) < 3:
                    by_category[category]["example_trace_ids"].append(features["trace_id"])

        # Remove empty categories
        by_category = {k: v for k, v in by_category.items() if v["count"] > 0}

        # Cluster
        clusters = self.cluster_failures(failures)

        # Top failures sorted by lowest faithfulness
        top_failures = sorted(
            failures,
            key=lambda f: float(f["faithfulness_score"]) if f.get("faithfulness_score") is not None else float("inf"),
        )[:10]

        now = datetime.now(UTC)
        start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")
        failure_rate = len(failures) / len(traces) if traces else 0.0

        report = {
            "period": {"start": start, "end": end},
            "total_responses": len(traces),
            "total_failures": len(failures),
            "failure_rate": round(failure_rate, 4),
            "by_category": by_category,
            "clusters": clusters,
            "top_failures": [
                {
                    "trace_id": f["trace_id"],
                    "query": f.get("query", ""),
                    "answer": f.get("answer", ""),
                    "faithfulness_score": f.get("faithfulness_score"),
                    "category": f["category"],
                    "feedback": f.get("feedback"),
                }
                for f in top_failures
            ],
        }

        return report

    def _extract_answer(self, trace: dict[str, Any]) -> str:
        """Extract the LLM answer from a trace's generation span."""
        for span in trace.get("spans", []):
            if span.get("name") == "generation":
                return str(span.get("attributes", {}).get("output", ""))
        return ""
