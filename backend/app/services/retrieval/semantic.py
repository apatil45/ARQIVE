"""
Semantic search via ChromaDB. ACL checked BEFORE retrieval (where document_id in allowed_ids).
One collection per tenant; top_k=10 from ChromaDB, caller reranks to 5.
"""
from __future__ import annotations

import logging
from typing import Any

import chromadb

from app.config import get_settings
from app.services.ingestion.embedder import embed_single

logger = logging.getLogger(__name__)


def _collection_name(tenant_id: str) -> str:
    safe = str(tenant_id).replace("-", "_").lower()
    return f"arqive_{safe}"


def semantic_search(
    tenant_id: str,
    query: str,
    allowed_document_ids: list[str],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Vector search. Only chunks from allowed_document_ids (RBAC).
    Returns list of {id, document_id, document (text), metadata, distance}.
    """
    if not allowed_document_ids:
        return []
    settings = get_settings()
    import os
    os.makedirs(settings.CHROMA_PERSIST_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_PATH)
    coll_name = _collection_name(tenant_id)
    try:
        collection = client.get_collection(name=coll_name)
    except Exception:
        return []
    query_embedding = embed_single(query)
    # ChromaDB where: document_id in allowed list (ACL before retrieval)
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, 100),
        where={"document_id": {"$in": allowed_document_ids}},
        include=["documents", "metadatas", "distances"],
    )
    out: list[dict[str, Any]] = []
    ids_raw = result.get("ids") or [[]]
    docs_raw = result.get("documents") or [[]]
    metadatas_raw = result.get("metadatas") or [[]]
    distances_raw = result.get("distances") or [[]]
    ids = ids_raw[0] if ids_raw else []
    docs = docs_raw[0] if docs_raw else []
    metadatas = metadatas_raw[0] if metadatas_raw else []
    distances = distances_raw[0] if distances_raw else []
    for i, ch_id in enumerate(ids):
        # ChromaDB returns distance (lower = more similar). Convert to similarity if needed.
        dist = distances[i] if i < len(distances) else 0.0
        similarity = 1.0 / (1.0 + dist) if dist is not None else 0.0
        meta = metadatas[i] if i < len(metadatas) else {}
        out.append({
            "id": ch_id,
            "document_id": meta.get("document_id", ""),
            "filename": meta.get("filename", ""),
            "page_number": meta.get("page_number", 0),
            "text": docs[i] if i < len(docs) else "",
            "score": similarity,
            "distance": dist,
        })
    return out
