"""
Documents API: upload (auditor+), list (RBAC), get, status, delete (auditor+).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status, UploadFile, File
from sqlalchemy import select

from app.db.models import Document
from app.dependencies import DbSession, CurrentUserPayload
from app.core.rbac import RequireAuditor
from app.services.storage.connector import get_storage_connector
from app.schemas.document import (
    DocumentListItem,
    DocumentDetail,
    DocumentUploadResponse,
    DocumentStatusResponse,
)
from tasks.ingest_task import ingest_document
from app.services.audit.logger import log as audit_log

router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {"pdf", "docx", "xlsx", "csv"}
MIME_TO_EXT = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/csv": "csv",
}
# Magic bytes (first few bytes) for validation
MAGIC: dict[str, bytes] = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",  # ZIP
    "xlsx": b"PK\x03\x04",  # ZIP
    "csv": None,  # any text
}


def _check_magic(data: bytes, ext: str) -> bool:
    if MAGIC[ext] is None:
        return True
    return data[: len(MAGIC[ext])] == MAGIC[ext]


def _validate_upload(content_type: str | None, data: bytes, filename: str) -> tuple[str, str]:
    """Returns (file_type, error_message). file_type if valid else error_message set."""
    ext = (filename.rsplit(".", 1)[-1].lower() if "." in filename else "") or ""
    if ext not in ALLOWED_EXTENSIONS:
        return "", f"Extension .{ext} not allowed. Use: pdf, docx, xlsx, csv"
    if len(data) > MAX_UPLOAD_BYTES:
        return "", "File exceeds 50 MB"
    mime_ext = MIME_TO_EXT.get((content_type or "").split(";")[0].strip())
    if mime_ext and mime_ext != ext:
        return "", f"MIME type does not match extension (.{ext})"
    if not _check_magic(data, ext):
        return "", "File content does not match extension (magic bytes)"
    return ext, ""


def _doc_can_access(doc: Document, role: str, user_id: str) -> bool:
    if role in (doc.allowed_roles or []):
        return True
    if doc.allowed_user_ids and user_id in doc.allowed_user_ids:
        return True
    return False


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    session: DbSession,
    payload: RequireAuditor,
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    """Upload file to storage, create Document row, enqueue Celery ingest task."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing filename")
    data = await file.read()
    file_type, err = _validate_upload(file.content_type, data, file.filename)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    tenant_id = payload["tenant_id"]
    user_id = payload["sub"]
    doc_id = str(uuid.uuid4())
    source_path = f"{tenant_id}/{doc_id}/{file.filename}"
    storage = get_storage_connector()
    storage.write_bytes(source_path, data)

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        uploaded_by=user_id,
        filename=file.filename,
        source_path=source_path,
        file_type=file_type,
        file_size_bytes=len(data),
        status="pending",
        chunk_count=0,
        allowed_roles=["viewer", "auditor", "admin"],
        allowed_user_ids=[],
    )
    session.add(doc)
    await audit_log(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        action="upload",
        document_ids_accessed=[doc_id],
    )
    await session.commit()
    ingest_document.delay(doc_id)
    return DocumentUploadResponse(
        document_id=doc_id,
        filename=file.filename,
        status="pending",
        message="Ingestion started",
    )


@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    session: DbSession,
    payload: CurrentUserPayload,
) -> list[DocumentListItem]:
    """List documents the current user can access (RBAC). Tenant from JWT only."""
    tenant_id = payload["tenant_id"]
    role = payload.get("role") or "viewer"
    user_id = payload.get("sub") or ""
    result = await session.execute(
        select(Document).where(
            Document.tenant_id == tenant_id,
            Document.status != "deleted",
        )
    )
    docs = [d for d in result.scalars().all() if _doc_can_access(d, role, user_id)]
    return [
        DocumentListItem(
            id=d.id,
            filename=d.filename,
            file_type=d.file_type,
            file_size_bytes=d.file_size_bytes,
            status=d.status,
            chunk_count=d.chunk_count,
            created_at=d.created_at,
            category=d.category,
            doc_date=d.doc_date,
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: str,
    session: DbSession,
    payload: CurrentUserPayload,
) -> DocumentDetail:
    """Get document metadata. RBAC-checked."""
    tenant_id = payload["tenant_id"]
    result = await session.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
            Document.status != "deleted",
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not _doc_can_access(doc, payload.get("role") or "viewer", payload.get("sub") or ""):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return DocumentDetail(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        status=doc.status,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
        category=doc.category,
        doc_date=doc.doc_date,
        source_path=doc.source_path,
        page_count=doc.page_count,
        allowed_roles=doc.allowed_roles or [],
        allowed_user_ids=doc.allowed_user_ids or [],
        updated_at=doc.updated_at,
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    session: DbSession,
    payload: CurrentUserPayload,
) -> DocumentStatusResponse:
    """Ingestion status. RBAC: user must have access to document."""
    tenant_id = payload["tenant_id"]
    result = await session.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not _doc_can_access(doc, payload.get("role") or "viewer", payload.get("sub") or ""):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return DocumentStatusResponse(
        document_id=doc.id,
        status=doc.status,
        chunk_count=doc.chunk_count,
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    session: DbSession,
    payload: RequireAuditor,
) -> dict[str, str]:
    """Soft delete: set status to deleted. Auditor+ only."""
    tenant_id = payload["tenant_id"]
    result = await session.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    doc.status = "deleted"
    await audit_log(
        session,
        tenant_id=tenant_id,
        user_id=payload["sub"],
        action="delete",
        document_ids_accessed=[document_id],
    )
    await session.commit()
    return {"message": "Document deleted"}
