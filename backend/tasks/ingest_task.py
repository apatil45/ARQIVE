"""
Document ingestion Celery task: read from storage, run pipeline, write ChromaDB + DB.
Uses sync SQLAlchemy in worker.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure app is on path when worker runs
_backend = Path(__file__).resolve().parents[1]
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from sqlalchemy import select
from sqlalchemy.orm import Session

from tasks.celery_app import celery_app
from app.db.sync_session import get_sync_session
from app.db.models import Document, Chunk
from app.services.storage.connector import get_storage_connector
from app.services.ingestion.pipeline import run_ingestion

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _save_chunks_sync(session: Session, records: list[dict]) -> None:
    for r in records:
        chunk = Chunk(
            id=r["id"],
            document_id=r["document_id"],
            tenant_id=r["tenant_id"],
            chunk_index=r["chunk_index"],
            page_number=r["page_number"],
            text_preview=r["text_preview"],
            token_count=r["token_count"],
            embedding_model=r["embedding_model"],
        )
        session.add(chunk)


@celery_app.task(bind=True)
def ingest_document(self, document_id: str) -> dict:
    """
    Load document, read from storage, run ingestion, update DB.
    Sets status to indexed or failed.
    """
    session = get_sync_session()
    try:
        doc = session.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
        if not doc:
            logger.error("Document not found: %s", document_id)
            return {"status": "failed", "document_id": document_id, "error": "document_not_found"}
        if doc.status == "indexed":
            return {"status": "indexed", "document_id": document_id, "chunk_count": doc.chunk_count}

        storage = get_storage_connector()
        try:
            data = storage.read_bytes(doc.source_path)
        except FileNotFoundError as e:
            logger.exception("Storage read failed for %s: %s", doc.source_path, e)
            doc.status = "failed"
            session.commit()
            return {"status": "failed", "document_id": document_id, "error": "file_not_found"}

        try:
            records = run_ingestion(
                tenant_id=doc.tenant_id,
                document_id=doc.id,
                filename=doc.filename,
                file_type=doc.file_type,
                data=data,
            )
        except Exception as e:
            logger.exception("Ingestion failed for %s: %s", document_id, e)
            doc.status = "failed"
            session.commit()
            return {"status": "failed", "document_id": document_id, "error": str(e)}

        _save_chunks_sync(session, records)
        doc.status = "indexed"
        doc.chunk_count = len(records)
        session.commit()
        logger.info("Ingested document %s: %s chunks", document_id, len(records))
        return {"status": "indexed", "document_id": document_id, "chunk_count": len(records)}
    finally:
        session.close()
