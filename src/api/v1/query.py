from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from src.api.auth import require_permission
from src.api.deps import get_orchestrator
from src.models.rbac import Permission
from src.models.schemas import QueryRequest, QueryResponse

if TYPE_CHECKING:
    from src.pipeline.orchestrator import PipelineOrchestrator

router = APIRouter()


@router.post(
    "/query",
    response_model=QueryResponse,
    dependencies=[Depends(require_permission(Permission.RUN_PIPELINE))],
)
async def query(
    request: QueryRequest,
    orchestrator: PipelineOrchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    return await orchestrator.query(request)
