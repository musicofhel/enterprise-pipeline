from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Generator

    from langfuse import Langfuse

logger = structlog.get_logger()


class TracingService:
    def __init__(self, client: Langfuse | None = None) -> None:
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def create_trace(
        self,
        name: str,
        user_id: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceContext:
        if not self.enabled:
            return TraceContext(trace=None, service=self)

        trace = self._client.trace(  # type: ignore[union-attr]
            name=name,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
        )
        return TraceContext(trace=trace, service=self)

    def flush(self) -> None:
        if self._client:
            self._client.flush()


class TraceContext:
    def __init__(self, trace: Any, service: TracingService) -> None:
        self._trace = trace
        self._service = service

    @property
    def trace_id(self) -> str:
        if self._trace:
            return str(self._trace.id)
        return "no-trace"

    @contextmanager
    def span(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[SpanContext, None, None]:
        if not self._trace:
            yield SpanContext(span=None)
            return

        span = self._trace.span(name=name, metadata=metadata or {})
        ctx = SpanContext(span=span)
        try:
            yield ctx
        except Exception:
            span.update(metadata={"error": True})
            raise
        finally:
            span.end()

    @contextmanager
    def generation(
        self,
        name: str,
        model: str,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[GenerationContext, None, None]:
        if not self._trace:
            yield GenerationContext(generation=None)
            return

        gen = self._trace.generation(
            name=name,
            model=model,
            input=input,
            metadata=metadata or {},
        )
        ctx = GenerationContext(generation=gen)
        try:
            yield ctx
        finally:
            gen.end()


class SpanContext:
    def __init__(self, span: Any) -> None:
        self._span = span

    def set_attribute(self, key: str, value: Any) -> None:
        if self._span:
            self._span.update(metadata={key: value})

    def set_output(self, output: Any) -> None:
        if self._span:
            self._span.update(output=output)


class GenerationContext:
    def __init__(self, generation: Any) -> None:
        self._generation = generation

    def set_output(self, output: Any, usage: dict[str, int] | None = None) -> None:
        if self._generation:
            update_kwargs: dict[str, Any] = {"output": output}
            if usage:
                update_kwargs["usage"] = usage
            self._generation.update(**update_kwargs)
