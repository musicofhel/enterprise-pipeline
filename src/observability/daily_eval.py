"""Daily Ragas eval runner — samples recent traces and runs quality metrics.

Runs faithfulness, context precision, and answer relevancy on a sample
of production traces. Saves reports to eval_results/daily/ and exports
metrics to Prometheus.
"""
from __future__ import annotations

import json
import os
import random
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from src.observability.metrics import (
    RAGAS_ANSWER_RELEVANCY_DAILY,
    RAGAS_CONTEXT_PRECISION_DAILY,
    RAGAS_EVAL_LAST_RUN_TIMESTAMP,
    RAGAS_EVAL_SAMPLE_SIZE,
    RAGAS_FAITHFULNESS_DAILY,
)

logger = structlog.get_logger()


class DailyEvalRunner:
    """Sample recent traces and run Ragas quality metrics."""

    def __init__(
        self,
        traces_dir: Path = Path("traces/local"),
        output_dir: Path = Path("eval_results/daily"),
        sample_size: int = 50,
        lookback_hours: int = 24,
    ) -> None:
        self._traces_dir = traces_dir
        self._output_dir = output_dir
        self._sample_size = sample_size
        self._lookback_hours = lookback_hours

    def sample_traces(self) -> list[dict[str, Any]]:
        """Sample N traces from the last lookback_hours."""
        if not self._traces_dir.exists():
            return []

        cutoff = datetime.now(UTC) - timedelta(hours=self._lookback_hours)
        recent: list[dict[str, Any]] = []

        for trace_path in self._traces_dir.glob("*.json"):
            try:
                data: dict[str, Any] = json.loads(trace_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            ts_str = data.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts < cutoff:
                    continue
            except (ValueError, TypeError):
                pass  # Include traces without valid timestamps

            # Must have query, context, and answer
            query = self._extract_query(data)
            contexts = self._extract_contexts(data)
            answer = self._extract_answer(data)

            if query and answer:
                recent.append({
                    "trace_id": data.get("trace_id", ""),
                    "query": query,
                    "contexts": contexts,
                    "answer": answer,
                })

        if len(recent) > self._sample_size:
            return random.sample(recent, self._sample_size)
        return recent

    @staticmethod
    def _extract_query(trace: dict[str, Any]) -> str:
        """Extract the user query from a trace."""
        for span in trace.get("spans", []):
            if span.get("name") == "generation":
                inp = span.get("attributes", {}).get("input")
                if isinstance(inp, str):
                    return inp
        return ""

    @staticmethod
    def _extract_contexts(trace: dict[str, Any]) -> list[str]:
        """Extract context chunks from a trace."""
        for span in trace.get("spans", []):
            if span.get("name") == "compression":
                output = span.get("attributes", {}).get("output")
                if isinstance(output, list):
                    return [str(c) for c in output]
        return []

    @staticmethod
    def _extract_answer(trace: dict[str, Any]) -> str:
        """Extract the generated answer from a trace."""
        for span in trace.get("spans", []):
            if span.get("name") == "generation":
                output = span.get("attributes", {}).get("output")
                if isinstance(output, str):
                    return output
        return ""

    def run(self) -> dict[str, Any]:
        """Run Ragas eval on sampled traces. Returns the report dict."""
        samples = self.sample_traces()

        if not samples:
            report = {
                "status": "insufficient_data",
                "sample_size": 0,
                "timestamp": datetime.now(UTC).isoformat(),
                "message": "No traces available for evaluation",
            }
            RAGAS_EVAL_SAMPLE_SIZE.set(0)
            self._save_report(report)
            return report

        # Check for API key
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            report = {
                "status": "skipped",
                "sample_size": len(samples),
                "timestamp": datetime.now(UTC).isoformat(),
                "message": "OPENROUTER_API_KEY not set — skipping Ragas eval",
            }
            RAGAS_EVAL_SAMPLE_SIZE.set(len(samples))
            self._save_report(report)
            return report

        # Run Ragas evaluation
        try:
            scores = self._run_ragas(samples, api_key)
        except Exception as e:
            logger.error("ragas_eval_failed", error=str(e))
            report = {
                "status": "error",
                "sample_size": len(samples),
                "timestamp": datetime.now(UTC).isoformat(),
                "error": str(e),
            }
            self._save_report(report)
            return report

        report = {
            "status": "completed",
            "sample_size": len(samples),
            "timestamp": datetime.now(UTC).isoformat(),
            "scores": scores,
        }

        # Update Prometheus
        now_ts = time.time()
        RAGAS_EVAL_SAMPLE_SIZE.set(len(samples))
        RAGAS_EVAL_LAST_RUN_TIMESTAMP.set(now_ts)
        if scores.get("faithfulness") is not None:
            RAGAS_FAITHFULNESS_DAILY.set(float(scores["faithfulness"]))  # type: ignore[arg-type]
        if scores.get("context_precision") is not None:
            RAGAS_CONTEXT_PRECISION_DAILY.set(float(scores["context_precision"]))  # type: ignore[arg-type]
        if scores.get("answer_relevancy") is not None:
            RAGAS_ANSWER_RELEVANCY_DAILY.set(float(scores["answer_relevancy"]))  # type: ignore[arg-type]

        self._save_report(report)
        logger.info("ragas_eval_completed", **scores, sample_size=len(samples))
        return report

    def _run_ragas(self, samples: list[dict[str, Any]], api_key: str) -> dict[str, float | None]:
        """Run Ragas metrics on the samples using OpenRouter."""
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import AnswerRelevancy, Faithfulness, LLMContextPrecisionWithoutReference

        llm = ChatOpenAI(
            model="anthropic/claude-haiku-4-5",
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        wrapped_llm = LangchainLLMWrapper(llm)

        ragas_samples = []
        for s in samples:
            ragas_samples.append(
                SingleTurnSample(
                    user_input=s["query"],
                    retrieved_contexts=s["contexts"] if s["contexts"] else ["No context available"],
                    response=s["answer"],
                )
            )

        dataset = EvaluationDataset(samples=ragas_samples)  # type: ignore[arg-type]

        metrics = [
            Faithfulness(llm=wrapped_llm),
            LLMContextPrecisionWithoutReference(llm=wrapped_llm),
            AnswerRelevancy(llm=wrapped_llm),
        ]

        result = evaluate(dataset=dataset, metrics=metrics)

        scores_df = result.to_pandas()  # type: ignore[union-attr]
        return {
            "faithfulness": round(float(scores_df["faithfulness"].mean()), 4)
            if "faithfulness" in scores_df.columns
            else None,
            "context_precision": round(
                float(scores_df["llm_context_precision_without_reference"].mean()), 4
            )
            if "llm_context_precision_without_reference" in scores_df.columns
            else None,
            "answer_relevancy": round(float(scores_df["answer_relevancy"].mean()), 4)
            if "answer_relevancy" in scores_df.columns
            else None,
        }

    def _save_report(self, report: dict[str, Any]) -> Path:
        """Save the eval report to disk."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        report_path = self._output_dir / f"{date_str}.json"
        report_path.write_text(json.dumps(report, indent=2, default=str))
        logger.info("ragas_report_saved", path=str(report_path))
        return report_path
