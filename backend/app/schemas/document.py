"""
Document request/response schemas.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class DocumentListItem(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    chunk_count: int
    created_at: datetime
    category: str | None = None
    doc_date: date | None = None


class DocumentDetail(DocumentListItem):
    source_path: str
    page_count: int | None = None
    allowed_roles: list[str]
    allowed_user_ids: list[str]
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str = "pending"
    message: str = "Ingestion started"


class DocumentStatusResponse(BaseModel):
    document_id: str
    status: str
    chunk_count: int
