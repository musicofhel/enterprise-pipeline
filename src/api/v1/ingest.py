from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, File, Form, UploadFile

from src.api.deps import get_orchestrator
from src.models.schemas import IngestResponse

if TYPE_CHECKING:
    from src.pipeline.orchestrator import PipelineOrchestrator

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    tenant_id: str = Form(...),
    doc_type: str = Form("markdown"),
    source_url: str | None = Form(None),
    access_level: str = Form("internal"),
    orchestrator: PipelineOrchestrator = Depends(get_orchestrator),
) -> IngestResponse:
    # Write uploaded file to temp location
    suffix = Path(file.filename or "document").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = await orchestrator.ingest_file(
            file_path=tmp_path,
            user_id=user_id,
            tenant_id=tenant_id,
            doc_type=doc_type,
            source_url=source_url,
            access_level=access_level,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return IngestResponse(**result)
