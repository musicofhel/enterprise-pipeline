from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from qdrant_client import AsyncQdrantClient

from src.api.deps import get_orchestrator, get_pipeline_config, get_settings, get_tracing_service
from src.models.schemas import (
    HealthResponse,
    QdrantServiceStatus,
    ReadyResponse,
    ServiceStatuses,
)
from src.observability.metrics import get_metrics_text
from src.pipeline.retrieval.vector_store import COLLECTION_NAME

if TYPE_CHECKING:
    from src.config.pipeline_config import PipelineConfig
    from src.config.settings import Settings
    from src.pipeline.orchestrator import PipelineOrchestrator

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Detailed health check with service status."""
    settings = get_settings()
    config = get_pipeline_config()

    qdrant_status = await _check_qdrant(settings)
    openrouter_status = _check_configured(settings.openrouter_api_key.get_secret_value())
    cohere_status = _check_configured(settings.cohere_api_key.get_secret_value())
    lakera_status = _check_configured(settings.lakera_api_key.get_secret_value())
    langfuse_status = _check_langfuse(settings, config)

    overall = "healthy"
    if isinstance(qdrant_status, str) or qdrant_status.status != "connected":
        overall = "degraded"

    return HealthResponse(
        status=overall,
        services=ServiceStatuses(
            qdrant=qdrant_status,
            openrouter=openrouter_status,
            cohere=cohere_status,
            lakera=lakera_status,
            langfuse=langfuse_status,
        ),
        version=config.version,
    )


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=get_metrics_text(), media_type="text/plain; charset=utf-8")


@router.get("/ready", response_model=ReadyResponse)
async def ready(
    orchestrator: PipelineOrchestrator = Depends(get_orchestrator),
) -> ReadyResponse:
    qdrant_ok = await orchestrator._vector_store.is_healthy()

    # Langfuse health is best-effort
    langfuse_status = "connected"
    tracing = get_tracing_service()
    if not tracing.enabled:
        langfuse_status = "disabled"

    return ReadyResponse(
        status="ready" if qdrant_ok else "degraded",
        qdrant="connected" if qdrant_ok else "disconnected",
        langfuse=langfuse_status,
    )


async def _check_qdrant(settings: Settings) -> QdrantServiceStatus:
    """Check Qdrant connectivity and collection info."""
    try:
        client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key.get_secret_value() or None,
        )
        collections = await client.get_collections()
        existing = [c.name for c in collections.collections]

        if COLLECTION_NAME in existing:
            info = await client.get_collection(COLLECTION_NAME)
            return QdrantServiceStatus(
                status="connected",
                collection=COLLECTION_NAME,
                vectors=info.points_count,
            )
        return QdrantServiceStatus(status="connected", collection=None, vectors=0)
    except Exception:
        return QdrantServiceStatus(status="disconnected")


def _check_configured(key: str) -> str:
    """Check if an API key is configured."""
    return "configured" if key else "not_configured"


def _check_langfuse(settings: Settings, config: PipelineConfig) -> str:
    """Check Langfuse configuration status."""
    if not config.observability.langfuse_enabled:
        return "disabled"
    if settings.langfuse_public_key and settings.langfuse_secret_key.get_secret_value():
        return "configured"
    return "not_configured"
