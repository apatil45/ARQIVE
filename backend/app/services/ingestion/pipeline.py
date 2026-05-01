"""
Ingestion pipeline: parse -> chunk -> embed -> index (ChromaDB + chunk records for DB).
Entry point for Celery task. No raw text written to disk.
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.ingestion.parser import parse_document
from app.services.ingestion.chunker import chunk_pages
from app.services.ingestion.indexer import index_chunks

logger = logging.getLogger(__name__)


def run_ingestion(
    tenant_id: str,
    document_id: str,
    filename: str,
    file_type: str,
    data: bytes,
) -> list[dict[str, Any]]:
    """
    Parse, chunk, embed, and index. Returns chunk records for DB insert.
    Caller must: save_chunk_records(session, records) and update Document (status, chunk_count).
    """
    pages = parse_document(data, file_type)
    if not pages:
        logger.warning("No content extracted from %s", filename)
        return []
    chunks = chunk_pages(pages)
    if not chunks:
        logger.warning("No chunks produced from %s", filename)
        return []
    records = index_chunks(
        tenant_id=tenant_id,
        document_id=document_id,
        filename=filename,
        chunks=chunks,
    )
    return records
