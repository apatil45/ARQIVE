"""
ChromaDB vector database operations
REQUIRED: ChromaDB must be installed for optimal performance
"""
from typing import List, Dict, Optional
import uuid
import logging

from config import settings

# ChromaDB is now REQUIRED - no fallback
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:
    raise ImportError(
        "ChromaDB is required but not installed. "
        "Please install it with: pip install chromadb\n"
        "ChromaDB provides 10-100x faster vector search compared to the fallback implementation."
    )

logger = logging.getLogger(__name__)


class VectorDB:
    """ChromaDB wrapper for vector storage with optimized HNSW indexing"""
    
    def __init__(self):
        self.client: Optional[chromadb.ClientAPI] = None
        self.collection: Optional[chromadb.Collection] = None
    
    async def initialize(self):
        """Initialize ChromaDB client and collection with optimized settings"""
        # Use persistent client for local storage
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_PATH,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        collection_name = "documents"
        
        # Try to get existing collection first
        try:
            existing_collection = self.client.get_collection(name=collection_name)
            self.collection = existing_collection
            logger.info("ChromaDB collection found, using existing collection")
        except Exception as get_error:
            # Check if error is due to incompatible metadata
            error_str = str(get_error)
            if "Failed to parse hnsw parameters" in error_str or "InvalidArgumentError" in str(type(get_error).__name__):
                logger.warning(f"Existing collection has incompatible metadata: {get_error}")
                logger.info("Deleting and recreating collection with compatible metadata...")
                try:
                    # Delete the problematic collection
                    self.client.delete_collection(name=collection_name)
                    logger.info("Deleted collection with incompatible metadata")
                    
                    # Create new collection with compatible metadata
                    self.collection = self.client.create_collection(
                        name=collection_name,
                        metadata={
                            "hnsw:space": "cosine",  # Cosine similarity metric
                        }
                    )
                    logger.info("ChromaDB collection recreated with compatible metadata")
                    logger.warning("NOTE: All vector embeddings were deleted. You may need to re-upload documents.")
                except Exception as recreate_error:
                    logger.error(f"Failed to recreate collection: {recreate_error}")
                    raise
            elif "does not exist" in error_str.lower() or "not found" in error_str.lower():
                # Collection doesn't exist, create it
                logger.info("Collection not found, creating new one...")
                self.collection = self.client.create_collection(
                    name=collection_name,
                    metadata={
                        "hnsw:space": "cosine",  # Cosine similarity metric
                    }
                )
                logger.info("ChromaDB initialized with HNSW indexing (cosine similarity)")
            else:
                # Some other error, re-raise it
                logger.error(f"Failed to initialize ChromaDB: {get_error}")
                raise
    
    async def add_documents(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict],
        ids: Optional[List[str]] = None
    ):
        """
        Add documents to vector database
        """
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]
        
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        return ids
    
    async def query(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        filter_dict: Optional[Dict] = None
    ) -> Dict:
        """
        Query vector database for similar documents using HNSW approximate nearest neighbor search
        filter_dict can contain user-based or document-based filters
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_dict if filter_dict else None
        )
        
        return {
            "ids": results["ids"][0],
            "documents": results["documents"][0],
            "metadatas": results["metadatas"][0],
            "distances": results["distances"][0]
        }
    
    async def delete_documents(self, document_ids: List[str]):
        """Delete documents by IDs"""
        self.collection.delete(ids=document_ids)
    
    async def get_collection_stats(self) -> Dict:
        """Get statistics about the collection"""
        count = self.collection.count()
        return {"document_count": count}


