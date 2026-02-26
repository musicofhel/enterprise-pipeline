from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import require_permission
from src.api.deps import get_deletion_service
from src.models.rbac import Permission
from src.models.schemas import (
    DeletionRequest,
    DeletionResponse,
    DeletionStatus,
    DeletionStatusResponse,
    DeletionStepStatus,
    DeletionSummary,
)

if TYPE_CHECKING:
    from src.services.deletion_service import DeletionService

router = APIRouter()


@router.delete(
    "/users/{user_id}/data",
    response_model=DeletionResponse,
    status_code=202,
    dependencies=[Depends(require_permission(Permission.DELETE_USER_DATA))],
)
async def delete_user_data(
    user_id: str,
    request: DeletionRequest,
    deletion_service: DeletionService = Depends(get_deletion_service),
) -> DeletionResponse:
    """Request deletion of all data for a user (GDPR right-to-erasure)."""
    receipt = await deletion_service.delete_user_data(
        user_id=user_id,
        tenant_id=request.tenant_id,
        reason=request.reason,
    )
    return DeletionResponse(
        deletion_id=receipt.deletion_id,
        status=DeletionStatus(receipt.status),
        user_id=receipt.user_id,
    )


@router.get(
    "/deletions/{deletion_id}",
    response_model=DeletionStatusResponse,
    dependencies=[Depends(require_permission(Permission.DELETE_USER_DATA))],
)
async def get_deletion_status(
    deletion_id: str,
    deletion_service: DeletionService = Depends(get_deletion_service),
) -> DeletionStatusResponse:
    """Check the status of a deletion request."""
    receipt = deletion_service.get_deletion_status(deletion_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Deletion request not found")

    summary = DeletionSummary(
        vectors_deleted=receipt.vectors_deleted,
        traces_redacted=receipt.traces_redacted,
        feedback_deleted=receipt.feedback_deleted,
        steps={
            k: DeletionStepStatus(
                status=v.status,
                count=v.count,
                error=v.error,
                reason=v.reason,
            )
            for k, v in receipt.steps.items()
        },
    )
    return DeletionStatusResponse(
        deletion_id=receipt.deletion_id,
        status=DeletionStatus(receipt.status),
        user_id=receipt.user_id,
        summary=summary,
        completed_at=receipt.completed_at,
    )
