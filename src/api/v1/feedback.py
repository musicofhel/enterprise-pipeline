from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from src.api.auth import require_permission
from src.api.deps import get_feedback_service
from src.models.rbac import Permission
from src.models.schemas import FeedbackRequest, FeedbackResponse, FeedbackStatsResponse

if TYPE_CHECKING:
    from src.services.feedback_service import FeedbackService

router = APIRouter()


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    dependencies=[Depends(require_permission(Permission.WRITE_FEEDBACK))],
)
async def feedback(
    request: FeedbackRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackResponse:
    """Record user feedback for a trace."""
    feedback_id = feedback_service.record_feedback(
        trace_id=request.trace_id,
        user_id=request.user_id,
        rating=request.rating,
        correction=request.correction,
        comment=request.comment,
    )
    return FeedbackResponse(feedback_id=feedback_id, status="recorded")


@router.post(
    "/feedback/stats",
    response_model=FeedbackStatsResponse,
)
async def feedback_stats(
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackStatsResponse:
    """Return feedback stats for the last 7 days."""
    stats = feedback_service.get_feedback_stats(days=7)
    return FeedbackStatsResponse(**stats)
