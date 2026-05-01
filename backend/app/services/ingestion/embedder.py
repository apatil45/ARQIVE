"""
Embedder: SentenceTransformer all-MiniLM-L6-v2 singleton, CPU only.
Load once at startup; never reload per request. Normalise for cosine similarity.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model: "SentenceTransformer | None" = None
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def get_embedder() -> "SentenceTransformer":
    """Singleton. Load on first use; device=cpu, cache from config."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        settings = get_settings()
        logger.info("Loading embedding model %s (CPU)...", EMBEDDING_MODEL_NAME)
        _model = SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            device="cpu",
            cache_folder=settings.EMBEDDING_CACHE_PATH,
        )
        logger.info("Embedding model loaded.")
    return _model


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Encode texts to 384-d normalised vectors. Batch for ingestion."""
    if not texts:
        return []
    model = get_embedder()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()


def embed_single(text: str) -> list[float]:
    """Single query embedding (batch_size=1)."""
    return embed_texts([text], batch_size=1)[0]
