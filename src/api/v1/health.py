from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from src.api.deps import get_orchestrator, get_tracing_service
from src.models.schemas import HealthResponse, ReadyResponse

if TYPE_CHECKING:
    from src.pipeline.orchestrator import PipelineOrchestrator

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


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
