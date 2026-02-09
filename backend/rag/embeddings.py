"""
Embedding generation using sentence-transformers
"""
from typing import List
from sentence_transformers import SentenceTransformer
import asyncio

from config import settings


class EmbeddingModel:
    """Local embedding model wrapper"""
    
    def __init__(self):
        """Initialize embedding model (lazy loading)"""
        self.model: SentenceTransformer = None
        self._model_loaded = False
    
    def _load_model(self):
        """Lazy load the embedding model"""
        if not self._model_loaded:
            # Load local sentence-transformers model
            self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
            self._model_loaded = True
    
    async def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        self._load_model()
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self.model.encode(text, normalize_embeddings=True).tolist()
        )
        return embedding
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts"""
        self._load_model()
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.model.encode(texts, normalize_embeddings=True).tolist()
        )
        return embeddings


