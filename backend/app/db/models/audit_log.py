"""
Audit log model: append-only. No UPDATE or DELETE for app user (enforce at DB level).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Integer, Float, Text
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utc_now() -> datetime:
    from datetime import timezone
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """
    Immutable audit trail. REVOKE UPDATE, DELETE ON audit_log FROM arqive_app_user;
    """

    __tablename__ = "audit_log"
    __table_args__ = {"comment": "Append-only. App user must not have UPDATE/DELETE."}

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # query, upload, delete, login, logout, admin_action
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_ids_accessed: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    chunk_ids_accessed: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256(all fields) tamper detection
