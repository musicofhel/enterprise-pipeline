from __future__ import annotations

import time
from typing import Any

import structlog
import torch
from transformers import AutoModelForSequenceClassification

logger = structlog.get_logger()

# Module-level model cache — load once, reuse across requests.
_model_cache: dict[str, Any] = {}


def _get_model(model_name: str = "vectara/hallucination_evaluation_model") -> Any:
    """Load the HHEM model, caching it for reuse."""
    if model_name not in _model_cache:
        logger.info("hhem_model_loading", model=model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name, trust_remote_code=True
        )
        model.eval()
        _model_cache[model_name] = model
        logger.info("hhem_model_loaded", model=model_name)
    return _model_cache[model_name]


class HallucinationChecker:
    """Real-time hallucination detection using Vectara HHEM cross-encoder.

    Scores each (context_chunk, answer) pair for groundedness.
    Score range: 0.0 (hallucinated) to 1.0 (grounded).

    Thresholds (configurable via pipeline_config.yaml):
      >= threshold_pass: PASS — serve response
      threshold_warn to threshold_pass: WARN — serve with disclaimer
      < threshold_warn: FAIL — don't serve, return fallback

    Aggregation methods:
      max: Best-chunk — is the answer supported by at least one chunk?
           Most practical for RAG where retrieval returns mixed-relevance chunks.
      mean: Average across all pairs.
      min: Most conservative — overall score is the minimum across all pairs.
           Use when all context chunks must support the answer.
    """

    def __init__(
        self,
        model_name: str = "vectara/hallucination_evaluation_model",
        threshold_pass: float = 0.85,
        threshold_warn: float = 0.70,
        aggregation_method: str = "max",
    ) -> None:
        self._model_name = model_name
        self._threshold_pass = threshold_pass
        self._threshold_warn = threshold_warn
        if aggregation_method not in ("min", "mean", "max"):
            raise ValueError(f"Invalid aggregation_method: {aggregation_method}")
        self._aggregation_method = aggregation_method
        # Lazy load: model is loaded on first call
        self._model: Any = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            self._model = _get_model(self._model_name)
        return self._model

    async def check(
        self,
        answer: str,
        context: str | list[str],
    ) -> dict[str, Any]:
        """Score answer groundedness against context.

        Args:
            answer: The LLM-generated response.
            context: Either a single string or list of context chunks.

        Returns:
            dict with score, passed, level, latency_ms, model, per_chunk_scores.
        """
        start = time.monotonic()

        # Normalize context to list of chunks
        if isinstance(context, str):
            chunks = [c.strip() for c in context.split("\n") if c.strip()]
            if not chunks:
                chunks = [context] if context.strip() else []
        else:
            chunks = [c for c in context if c.strip()]

        # Empty context → fail
        if not chunks or not answer.strip():
            latency_ms = (time.monotonic() - start) * 1000
            logger.warning(
                "hallucination_check_empty_input",
                has_answer=bool(answer.strip()),
                num_chunks=len(chunks),
            )
            return {
                "score": 0.0,
                "passed": False,
                "level": "fail",
                "latency_ms": round(latency_ms, 2),
                "model": self._model_name,
                "per_chunk_scores": [],
            }

        model = self._ensure_model()

        # Build pairs: (context_chunk, answer) — HHEM expects (premise, hypothesis)
        pairs = [(chunk, answer) for chunk in chunks]

        # Batch inference
        with torch.no_grad():
            scores_tensor = model.predict(pairs)

        per_chunk_scores = scores_tensor.tolist()

        # Aggregate
        if self._aggregation_method == "max":
            overall_score = max(per_chunk_scores)
        elif self._aggregation_method == "mean":
            overall_score = sum(per_chunk_scores) / len(per_chunk_scores)
        else:  # min
            overall_score = min(per_chunk_scores)

        # Determine level
        if overall_score >= self._threshold_pass:
            level = "pass"
            passed = True
        elif overall_score >= self._threshold_warn:
            level = "warn"
            passed = True
        else:
            level = "fail"
            passed = False

        latency_ms = (time.monotonic() - start) * 1000

        logger.info(
            "hallucination_check_complete",
            score=round(overall_score, 4),
            level=level,
            num_chunks=len(chunks),
            aggregation=self._aggregation_method,
            latency_ms=round(latency_ms, 2),
        )

        return {
            "score": round(overall_score, 4),
            "passed": passed,
            "level": level,
            "latency_ms": round(latency_ms, 2),
            "model": self._model_name,
            "per_chunk_scores": [round(s, 4) for s in per_chunk_scores],
        }
