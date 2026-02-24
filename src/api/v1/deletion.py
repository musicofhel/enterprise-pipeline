from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.delete("/users/{user_id}/data")
async def delete_user_data(user_id: str) -> dict[str, str]:
    raise HTTPException(
        status_code=501,
        detail="User data deletion not yet implemented. Coming in Wave 4.",
    )
