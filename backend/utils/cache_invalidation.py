"""
Cache invalidation utilities
Provides a way to invalidate caches when document access changes
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Global RAG engine reference for cache invalidation
_rag_engine_instance: Optional[object] = None


def set_rag_engine(rag_engine):
    """Set the global RAG engine instance for cache invalidation"""
    global _rag_engine_instance
    _rag_engine_instance = rag_engine


def invalidate_user_document_cache(username: str):
    """
    Invalidate document access cache for a user
    Should be called when document access changes
    """
    global _rag_engine_instance
    if _rag_engine_instance and hasattr(_rag_engine_instance, '_cache_invalidation_set'):
        _rag_engine_instance._cache_invalidation_set.add(username)
        logger.info(f"Marked cache for invalidation: {username}")
    else:
        logger.warning(f"RAG engine not available for cache invalidation for user: {username}")
