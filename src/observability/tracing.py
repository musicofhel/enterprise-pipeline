from __future__ import annotations

import hashlib
import json
import subprocess
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from collections.abc import Generator

    from langfuse import Langfuse

logger = structlog.get_logger()

LOCAL_TRACE_DIR = Path("traces/local")


def _get_pipeline_version() -> str:
    """Get pipeline version from git SHA, fallback to 'dev'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "dev"


def _get_config_hash(config_path: str = "pipeline_config.yaml") -> str:
    """SHA256 hash of pipeline config file contents."""
    path = Path(config_path)
    if path.exists():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return "no-config"


class TracingService:
    def __init__(
        self,
        client: Langfuse | None = None,
        local_fallback: bool = True,
    ) -> None:
        self._client = client
        self._local_fallback = local_fallback
        self._pipeline_version = _get_pipeline_version()
        self._config_hash = _get_config_hash()

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @property
    def pipeline_version(self) -> str:
        return self._pipeline_version

    @property
    def config_hash(self) -> str:
        return self._config_hash

    def create_trace(
        self,
        name: str,
        user_id: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceContext:
        trace_metadata = {
            **(metadata or {}),
            "pipeline_version": self._pipeline_version,
            "config_hash": self._config_hash,
            "feature_flags": {"pipeline_variant": "control"},
        }

        if self.enabled:
            trace = self._client.trace(  # type: ignore[union-attr]
                name=name,
                user_id=user_id,
                session_id=session_id,
                metadata=trace_metadata,
            )
            return TraceContext(trace=trace, service=self, local_trace=None)

        if self._local_fallback:
            local_trace = LocalTrace(
                name=name,
                user_id=user_id,
                session_id=session_id,
                metadata=trace_metadata,
                pipeline_version=self._pipeline_version,
                config_hash=self._config_hash,
            )
            return TraceContext(trace=None, service=self, local_trace=local_trace)

        return TraceContext(trace=None, service=self, local_trace=None)

    def flush(self) -> None:
        if self._client:
            self._client.flush()


class LocalTrace:
    """Local JSON trace that produces the same schema as Langfuse."""

    def __init__(
        self,
        name: str,
        user_id: str,
        session_id: str | None,
        metadata: dict[str, Any],
        pipeline_version: str,
        config_hash: str,
    ) -> None:
        self.trace_id = str(uuid4())
        self.name = name
        self.timestamp = datetime.now(UTC).isoformat()
        self.user_id = user_id
        self.session_id = session_id or ""
        self.pipeline_version = pipeline_version
        self.config_hash = config_hash
        self.feature_flags = metadata.get("feature_flags", {})
        self.metadata = metadata
        self.spans: list[dict[str, Any]] = []
        self.scores: dict[str, Any] = {"faithfulness": None, "user_feedback": None}
        self.total_latency_ms: float = 0
        self.total_cost_usd: float = 0
        self._start_time = time.monotonic()

    def add_span(self, span_data: dict[str, Any]) -> None:
        self.spans.append(span_data)

    def set_score(self, key: str, value: Any) -> None:
        self.scores[key] = value

    def save(self) -> Path:
        """Write trace to local JSON file matching Langfuse schema."""
        self.total_latency_ms = (time.monotonic() - self._start_time) * 1000

        trace_data = {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "pipeline_version": self.pipeline_version,
            "config_hash": self.config_hash,
            "feature_flags": self.feature_flags,
            "spans": self.spans,
            "scores": self.scores,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "total_cost_usd": round(self.total_cost_usd, 4),
        }

        LOCAL_TRACE_DIR.mkdir(parents=True, exist_ok=True)
        trace_path = LOCAL_TRACE_DIR / f"{self.trace_id}.json"
        trace_path.write_text(json.dumps(trace_data, indent=2, default=str))
        logger.info("local_trace_saved", trace_id=self.trace_id, path=str(trace_path))
        return trace_path


class TraceContext:
    def __init__(
        self,
        trace: Any,
        service: TracingService,
        local_trace: LocalTrace | None = None,
    ) -> None:
        self._trace = trace
        self._service = service
        self._local_trace = local_trace

    @property
    def trace_id(self) -> str:
        if self._trace:
            return str(self._trace.id)
        if self._local_trace:
            return self._local_trace.trace_id
        return "no-trace"

    @contextmanager
    def span(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[SpanContext, None, None]:
        start_time = datetime.now(UTC)
        start_mono = time.monotonic()

        if self._trace:
            span = self._trace.span(name=name, metadata=metadata or {})
            ctx = SpanContext(span=span, name=name)
            try:
                yield ctx
            except Exception:
                span.update(metadata={"error": True})
                raise
            finally:
                span.end()
                if self._local_trace:
                    self._local_trace.add_span(ctx.to_dict(start_time, start_mono))
        else:
            ctx = SpanContext(span=None, name=name)
            try:
                yield ctx
            finally:
                if self._local_trace:
                    self._local_trace.add_span(ctx.to_dict(start_time, start_mono))

    @contextmanager
    def generation(
        self,
        name: str,
        model: str,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[GenerationContext, None, None]:
        start_time = datetime.now(UTC)
        start_mono = time.monotonic()

        if self._trace:
            gen = self._trace.generation(
                name=name,
                model=model,
                input=input,
                metadata=metadata or {},
            )
            ctx = GenerationContext(generation=gen, name=name, model=model)
            try:
                yield ctx
            finally:
                gen.end()
                if self._local_trace:
                    self._local_trace.add_span(ctx.to_dict(start_time, start_mono))
        else:
            ctx = GenerationContext(generation=None, name=name, model=model)
            try:
                yield ctx
            finally:
                if self._local_trace:
                    self._local_trace.add_span(ctx.to_dict(start_time, start_mono))

    def set_score(self, key: str, value: Any) -> None:
        """Set a trace-level score (e.g., faithfulness)."""
        if self._local_trace:
            self._local_trace.set_score(key, value)

    def save_local(self) -> Path | None:
        """Save local trace file. Returns path if saved, None if not local."""
        if self._local_trace:
            return self._local_trace.save()
        return None


class SpanContext:
    def __init__(self, span: Any, name: str = "") -> None:
        self._span = span
        self._name = name
        self._attributes: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self._attributes[key] = value
        if self._span:
            self._span.update(metadata={key: value})

    def set_output(self, output: Any) -> None:
        self._attributes["output"] = output
        if self._span:
            self._span.update(output=output)

    def to_dict(self, start_time: datetime, start_mono: float) -> dict[str, Any]:
        end_time = datetime.now(UTC)
        duration_ms = (time.monotonic() - start_mono) * 1000
        return {
            "name": self._name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_ms": round(duration_ms, 2),
            "attributes": dict(self._attributes),
        }


class GenerationContext:
    def __init__(
        self,
        generation: Any,
        name: str = "",
        model: str = "",
    ) -> None:
        self._generation = generation
        self._name = name
        self._model = model
        self._attributes: dict[str, Any] = {"model": model}
        self._usage: dict[str, int] = {}

    def set_output(self, output: Any, usage: dict[str, int] | None = None) -> None:
        self._attributes["output"] = output
        if usage:
            self._usage = usage
            self._attributes["tokens_in"] = usage.get("input", 0)
            self._attributes["tokens_out"] = usage.get("output", 0)
        if self._generation:
            update_kwargs: dict[str, Any] = {"output": output}
            if usage:
                update_kwargs["usage"] = usage
            self._generation.update(**update_kwargs)

    def to_dict(self, start_time: datetime, start_mono: float) -> dict[str, Any]:
        end_time = datetime.now(UTC)
        duration_ms = (time.monotonic() - start_mono) * 1000
        return {
            "name": self._name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_ms": round(duration_ms, 2),
            "attributes": dict(self._attributes),
        }
