"""Document ingestion endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException
import structlog

from evograph.models.domain import DocumentStatus
from evograph.models.api_schemas import DocumentUploadResponse, DocumentDetail

logger = structlog.get_logger()
router = APIRouter()


@router.post("", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    doc_id = str(uuid.uuid4())
    content = await file.read()

    # TODO: Save file to storage and dispatch Celery task
    logger.info("document_uploaded", doc_id=doc_id, filename=file.filename, size=len(content))

    return DocumentUploadResponse(
        id=doc_id,
        filename=file.filename,
        status=DocumentStatus.PENDING,
    )


@router.get("", response_model=list[DocumentDetail])
async def list_documents(
    skip: int = 0,
    limit: int = 20,
) -> list[DocumentDetail]:
    # TODO: Query from PostgreSQL
    return []


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(doc_id: str) -> DocumentDetail:
    # TODO: Query from PostgreSQL
    raise HTTPException(status_code=404, detail="Document not found")


@router.delete("/{doc_id}")
async def delete_document(doc_id: str) -> dict[str, str]:
    # TODO: Remove document and retract its facts from graph
    logger.info("document_deleted", doc_id=doc_id)
    return {"status": "deleted", "id": doc_id}
