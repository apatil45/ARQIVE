"""
Indexer: write chunks to ChromaDB (PersistentClient) and to DB (Chunk rows).
Same chunk id in both for joins. One collection per tenant: arqive_{tenant_id}.
"""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

import chromadb

from app.config import get_settings
from app.services.ingestion.chunker import ChunkResult
from app.services.ingestion.embedder import EMBEDDING_MODEL_NAME, embed_texts

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _collection_name(tenant_id: str) -> str:
    """ChromaDB collection name: lowercase, alphanumeric + underscore."""
    safe = str(tenant_id).replace("-", "_").lower()
    return f"arqive_{safe}"


def index_chunks(
    tenant_id: str,
    document_id: str,
    filename: str,
    chunks: list[ChunkResult],
) -> list[dict]:
    """
    Embed chunks, add to ChromaDB and return chunk records for DB insert.
    Does not touch DB — caller commits Chunk rows and updates Document.
    Returns list of dicts: id, document_id, tenant_id, chunk_index, page_number, text_preview, token_count, embedding_model, text (full for ChromaDB).
    """
    if not chunks:
        return []
    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts, batch_size=32)
    settings = get_settings()
    path = settings.CHROMA_PERSIST_PATH
    import os
    os.makedirs(path, exist_ok=True)
    client = chromadb.PersistentClient(path=path)
    coll_name = _collection_name(tenant_id)
    collection = client.get_or_create_collection(name=coll_name, metadata={"description": "ARQIVE tenant chunks"})

    ids: list[str] = []
    documents_for_chroma: list[str] = []
    metadatas: list[dict] = []
    records: list[dict] = []

    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        ch_id = str(uuid.uuid4())
        ids.append(ch_id)
        documents_for_chroma.append(chunk.text)
        metadatas.append({
            "document_id": document_id,
            "tenant_id": tenant_id,
            "page_number": chunk.page_number,
            "filename": filename[:500],
        })
        preview = (chunk.text[:200] + "…") if len(chunk.text) > 200 else chunk.text
        records.append({
            "id": ch_id,
            "document_id": document_id,
            "tenant_id": tenant_id,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "text_preview": preview,
            "token_count": chunk.token_count,
            "embedding_model": EMBEDDING_MODEL_NAME,
            "text": chunk.text,
        })

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents_for_chroma,
        metadatas=metadatas,
    )
    logger.info("Indexed %s chunks for document %s into %s", len(ids), document_id, coll_name)
    return records


async def save_chunk_records(session: "AsyncSession", records: list[dict]) -> None:
    """Insert Chunk rows from index_chunks() output. Caller must commit."""
    from app.db.models import Chunk
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
