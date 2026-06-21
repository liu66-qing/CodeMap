"""Document ingestion endpoints: file upload, URL, and Douyin video."""

from __future__ import annotations

import uuid
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
import structlog

from codegraph.api.security import require_admin_api_key, require_confirmation
from codegraph.models.domain import DocumentStatus
from codegraph.models.api_schemas import DocumentUploadResponse, DocumentDetail

logger = structlog.get_logger()
router = APIRouter()

UPLOAD_DIR = Path(tempfile.gettempdir()) / "pulsegraph_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class URLIngestRequest(BaseModel):
    url: str


class DouyinIngestRequest(BaseModel):
    douyin_url: str


@router.post("", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    doc_id = str(uuid.uuid4())
    content = await file.read()

    file_path = UPLOAD_DIR / f"{doc_id}_{file.filename}"
    file_path.write_bytes(content)

    from codegraph.tasks.ingestion_tasks import ingest_document_task
    ingest_document_task.delay(doc_id, str(file_path))

    logger.info("document_uploaded", doc_id=doc_id, filename=file.filename, size=len(content))
    return DocumentUploadResponse(
        id=doc_id,
        filename=file.filename,
        status=DocumentStatus.PROCESSING,
    )


@router.post("/url", response_model=DocumentUploadResponse)
async def ingest_from_url(req: URLIngestRequest) -> DocumentUploadResponse:
    """Fetch content from a news URL and process it."""
    doc_id = str(uuid.uuid4())

    from codegraph.tasks.ingestion_tasks import ingest_url_task
    ingest_url_task.delay(doc_id, req.url)

    logger.info("url_ingestion_started", doc_id=doc_id, url=req.url)
    return DocumentUploadResponse(
        id=doc_id,
        filename=f"url_{doc_id[:8]}.txt",
        status=DocumentStatus.PROCESSING,
    )


@router.post("/douyin", response_model=DocumentUploadResponse)
async def ingest_from_douyin(req: DouyinIngestRequest) -> DocumentUploadResponse:
    """Extract content from a Douyin video link and process it."""
    doc_id = str(uuid.uuid4())

    from codegraph.tasks.ingestion_tasks import ingest_douyin_task
    ingest_douyin_task.delay(doc_id, req.douyin_url)

    logger.info("douyin_ingestion_started", doc_id=doc_id, url=req.douyin_url)
    return DocumentUploadResponse(
        id=doc_id,
        filename=f"douyin_{doc_id[:8]}.txt",
        status=DocumentStatus.PROCESSING,
    )


@router.get("", response_model=list[DocumentDetail])
async def list_documents(skip: int = 0, limit: int = 20) -> list[DocumentDetail]:
    return []


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(doc_id: str) -> DocumentDetail:
    raise HTTPException(status_code=404, detail="Document not found")


@router.delete("/{doc_id}", dependencies=[Depends(require_admin_api_key)])
async def delete_document(doc_id: str, confirmation: str = "") -> dict[str, str]:
    require_confirmation(confirmation, f"DELETE_DOCUMENT:{doc_id}")
    logger.info("document_deleted", doc_id=doc_id)
    return {"status": "deleted", "id": doc_id}
