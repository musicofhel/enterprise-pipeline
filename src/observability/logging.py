from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "console",
    pipeline_version: str = "dev",
) -> None:
    """Configure structlog with JSON or console output.

    Args:
        log_level: Python log level name (DEBUG, INFO, WARNING, ERROR).
        log_format: "json" for production (machine-readable), "console" for development.
        pipeline_version: Auto-bound to every log event.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _add_pipeline_version(pipeline_version),
    ]

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))


def _add_pipeline_version(version: str) -> structlog.types.Processor:
    """Create a processor that adds pipeline_version to every log event."""

    def processor(
        logger: structlog.types.WrappedLogger,
        method_name: str,
        event_dict: structlog.types.EventDict,
    ) -> structlog.types.EventDict:
        event_dict.setdefault("pipeline_version", version)
        return event_dict

    return processor


def bind_trace_context(trace_id: str, user_id: str) -> None:
    """Bind trace_id and user_id to the current context.

    All subsequent log calls in this context will include these fields.
    Call this at the start of each pipeline request.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id, user_id=user_id)


def clear_trace_context() -> None:
    """Clear the trace context after request completes."""
    structlog.contextvars.clear_contextvars()
