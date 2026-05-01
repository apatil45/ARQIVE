"""
Document model: metadata for ingested files. Raw file stays in storage (S3/MinIO/local).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, String, Integer, ForeignKey, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.tenant import Tenant
    from app.db.models.user import User
    from app.db.models.chunk import Chunk


def _utc_now() -> datetime:
    from datetime import timezone
    return datetime.now(timezone.utc)


class Document(Base):
    """Document metadata. source_path points to storage; no raw text on ARQIVE node."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)  # pdf, docx, xlsx, csv
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doc_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending, indexed, failed
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    allowed_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # ["viewer","auditor","admin"]
    allowed_user_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # [] = role-only
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="documents")
    uploaded_by_user: Mapped["User"] = relationship("User", back_populates="documents_uploaded")
    chunks: Mapped[list["Chunk"]] = relationship("Chunk", back_populates="document")
