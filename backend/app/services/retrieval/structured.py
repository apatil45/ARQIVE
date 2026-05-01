"""
Structured (metadata) search: filter chunks by document category, date, etc.
Returns chunk ids + metadata for RRF merge. Uses DB only.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document


async def structured_search(
    session: AsyncSession,
    tenant_id: str,
    allowed_document_ids: list[str],
    category: str | None = None,
    doc_date_from: str | None = None,
    doc_date_to: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Filter chunks by document metadata. Returns list of {id, document_id, filename, page_number, score=1.0}
    for RRF (no text here; text comes from semantic or DB join).
    """
    if not allowed_document_ids:
        return []
    q = (
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.tenant_id == tenant_id,
            Chunk.document_id.in_(allowed_document_ids),
        )
    )
    if category:
        q = q.where(Document.category == category)
    if doc_date_from:
        q = q.where(Document.doc_date >= doc_date_from)
    if doc_date_to:
        q = q.where(Document.doc_date <= doc_date_to)
    q = q.limit(limit)
    result = await session.execute(q)
    rows = result.all()
    return [
        {
            "id": c.id,
            "document_id": c.document_id,
            "filename": d.filename,
            "page_number": c.page_number,
            "text": c.text_preview,
            "score": 1.0,
        }
        for c, d in rows
    ]
