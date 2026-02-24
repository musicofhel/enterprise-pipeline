from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.models.schemas import FeedbackRequest, FeedbackResponse

router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest) -> FeedbackResponse:
    raise HTTPException(
        status_code=501,
        detail="Feedback collection not yet implemented. Coming in Wave 3.",
    )
