from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI

from src.api.deps import get_orchestrator, get_pipeline_config, get_settings
from src.api.router import api_router
from src.observability.logging import setup_logging

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    settings = get_settings()
    config = get_pipeline_config()

    logger.info(
        "pipeline_starting",
        env=settings.pipeline_env,
        config_version=config.version,
    )

    # Ensure Qdrant collection exists
    try:
        orchestrator = get_orchestrator()
        await orchestrator._vector_store.ensure_collection()
        logger.info("qdrant_collection_ready")
    except Exception as e:
        logger.warning("qdrant_init_failed", error=str(e))

    yield

    logger.info("pipeline_shutting_down")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
    )

    app = FastAPI(
        title="Enterprise AI Pipeline",
        version="0.1.0",
        description="RAG pipeline with safety, observability, and compliance",
        lifespan=lifespan,
    )

    app.include_router(api_router)

    return app
