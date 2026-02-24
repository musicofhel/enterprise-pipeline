from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from src.api.deps import get_orchestrator
from src.models.schemas import QueryRequest, QueryResponse

if TYPE_CHECKING:
    from src.pipeline.orchestrator import PipelineOrchestrator

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    orchestrator: PipelineOrchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    return await orchestrator.query(request)
