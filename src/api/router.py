from __future__ import annotations

from fastapi import APIRouter

from src.api.v1 import deletion, feedback, health, ingest, query

api_router = APIRouter()

# Health endpoints at root level
api_router.include_router(health.router, tags=["health"])

# V1 API endpoints
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(query.router, tags=["query"])
v1_router.include_router(ingest.router, tags=["ingest"])
v1_router.include_router(feedback.router, tags=["feedback"])
v1_router.include_router(deletion.router, tags=["deletion"])

api_router.include_router(v1_router)
