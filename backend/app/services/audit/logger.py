"""
Append-only audit log writer. Row hash = SHA-256(all field values) for tamper detection.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _row_hash(data: dict[str, Any]) -> str:
    """SHA-256 of canonical JSON of all field values."""
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def log(
    session: AsyncSession,
    tenant_id: str,
    user_id: str,
    action: str,
    *,
    query_text: str | None = None,
    document_ids_accessed: list[str] | None = None,
    chunk_ids_accessed: list[str] | None = None,
    prompt_hash: str | None = None,
    response_hash: str | None = None,
    confidence_score: float | None = None,
    latency_ms: int | None = None,
    ip_address: str | None = None,
) -> None:
    """Append one audit log entry. Caller commits."""
    ts = _utc_now()
    entry_id = str(uuid.uuid4())
    data = {
        "id": entry_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "action": action,
        "timestamp": ts.isoformat(),
        "query_text": query_text,
        "document_ids_accessed": document_ids_accessed,
        "chunk_ids_accessed": chunk_ids_accessed,
        "prompt_hash": prompt_hash,
        "response_hash": response_hash,
        "confidence_score": confidence_score,
        "latency_ms": latency_ms,
        "ip_address": ip_address,
    }
    row_hash = _row_hash(data)
    record = AuditLog(
        id=entry_id,
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        timestamp=ts,
        query_text=query_text,
        document_ids_accessed=document_ids_accessed,
        chunk_ids_accessed=chunk_ids_accessed,
        prompt_hash=prompt_hash,
        response_hash=response_hash,
        confidence_score=confidence_score,
        latency_ms=latency_ms,
        ip_address=ip_address,
        row_hash=row_hash,
    )
    session.add(record)
