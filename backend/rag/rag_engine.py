"""
RAG Engine: Retrieval + LLM generation
"""
from typing import Dict, List, Optional, AsyncGenerator
from ollama import Client
import hashlib
import json
from collections import OrderedDict
import asyncio
import time
import re

from config import settings
from db.vector import VectorDB
from rag.embeddings import EmbeddingModel
from rag.chunker import Chunker
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from db.sqlite import SQLiteDB

logger = logging.getLogger(__name__)

# Import constants from config (backward compatible aliases)
OLLAMA_CONTEXT_LIMIT = settings.OLLAMA_CONTEXT_LIMIT
PROMPT_TEMPLATE_TOKENS = settings.PROMPT_TEMPLATE_TOKENS
RESERVE_FOR_RESPONSE = settings.RESERVE_FOR_RESPONSE
MAX_CONTEXT_TOKENS = settings.MAX_CONTEXT_TOKENS


class RAGEngine:
    """RAG pipeline: retrieve relevant chunks and generate answer with LLM"""
    
    def __init__(self, vector_db: VectorDB, sqlite_db: Optional["SQLiteDB"] = None):
        """
        Initialize RAG Engine with audit-aware capabilities
        """
        self.vector_db = vector_db
        self.embedding_model = EmbeddingModel()
        self.ollama_client = Client(host=settings.OLLAMA_BASE_URL)
        # Cache for query embeddings (LRU cache, max 1000 entries)
        # Using OrderedDict for proper LRU behavior
        self._embedding_cache: OrderedDict[str, List[float]] = OrderedDict()
        self._max_cache_size = settings.EMBEDDING_CACHE_SIZE
        self._cache_lock = asyncio.Lock()  # Thread-safe cache operations
        # SQLite DB instance (optional, will create if not provided)
        self._sqlite_db = sqlite_db
        # Cache for user document access (username -> set of document IDs, TTL: 5 minutes)
        self._user_doc_cache: Dict[str, tuple] = {}  # {username: (doc_ids, expiry_time)}
        self._doc_cache_ttl = settings.USER_DOC_CACHE_TTL
        # Cache invalidation: track which users need cache refresh
        self._cache_invalidation_set: set = set()  # Set of usernames whose cache should be invalidated
        # Cache for full query results (query + username -> full result, TTL: 1 hour)
        self._query_result_cache: OrderedDict[str, Dict] = OrderedDict()
        self._query_result_cache_size = settings.QUERY_RESULT_CACHE_SIZE
        self._query_result_cache_ttl = settings.QUERY_RESULT_CACHE_TTL
        
        # GPU detection and hardware-aware configuration
        self.gpu_available = self._detect_gpu()
        self._configure_for_hardware()
        
        # Audit-aware components (industry-standard enhancements)
        self.query_classifier = QueryClassifier()
        self.audit_prompt_builder = AuditPromptBuilder()
        
        logger.info(f"RAG Engine initialized. GPU available: {self.gpu_available}")
    
    def _detect_gpu(self) -> bool:
        """Detect if GPU is available for Ollama"""
        # Method 1: Check Ollama's system info (most reliable)
        try:
            import httpx
            response = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/version", timeout=5)
            if response.status_code == 200:
                version_info = response.json()
                # Check for GPU info in version response
                if "gpu" in str(version_info).lower() or "cuda" in str(version_info).lower():
                    logger.info("GPU detected via Ollama version info")
                    return True
        except Exception as e:
            logger.debug(f"Could not check Ollama version: {e}")
        
        # Method 2: Check if CUDA is available (NVIDIA GPU)
        try:
            import torch
            if torch.cuda.is_available():
                logger.info(f"CUDA GPU detected: {torch.cuda.get_device_name(0)}")
                return True
        except ImportError:
            logger.debug("PyTorch not installed, skipping CUDA check")
        except Exception as e:
            logger.debug(f"CUDA check failed: {e}")
        
        # Method 3: Check for Metal (Apple Silicon GPU)
        try:
            import platform
            if platform.system() == "Darwin":  # macOS
                # Check if Metal is available (Apple Silicon)
                import subprocess
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "Apple" in result.stdout and ("M1" in result.stdout or "M2" in result.stdout or "M3" in result.stdout):
                    logger.info("Apple Silicon GPU (Metal) detected")
                    return True
        except Exception as e:
            logger.debug(f"Metal check failed: {e}")
        
        # Method 4: Check Ollama model details (fallback)
        try:
            models = self.ollama_client.list()
            for model in models.get("models", []):
                details = model.get("details", {})
                backend = str(details.get("backend", "")).lower()
                if "gpu" in backend or "cuda" in backend or "metal" in backend:
                    logger.info("GPU detected via Ollama model backend")
                    return True
        except Exception as e:
            logger.debug(f"Could not check Ollama models: {e}")
        
        logger.info("GPU not detected, using CPU-optimized settings")
        return False
    
    def _configure_for_hardware(self):
        """Configure timeouts and limits based on available hardware"""
        if self.gpu_available:
            self.ollama_timeout = settings.OLLAMA_TIMEOUT_GPU
            self.max_context_tokens = settings.MAX_CONTEXT_TOKENS_GPU
            self.max_response_tokens = settings.MAX_RESPONSE_TOKENS_GPU
        else:
            self.ollama_timeout = settings.OLLAMA_TIMEOUT_CPU
            self.max_context_tokens = settings.MAX_CONTEXT_TOKENS
            self.max_response_tokens = settings.MAX_RESPONSE_TOKENS_CPU
    
    def _sanitize_query(self, query: str) -> str:
        """
        Comprehensive query sanitization to prevent prompt injection attacks
        """
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        
        # Remove control characters and null bytes
        query = ''.join(c for c in query if c.isprintable() or c.isspace())
        query = query.replace('\x00', '')
        
        # Detect injection patterns
        injection_patterns = [
            r'ignore\s+previous\s+instructions',
            r'forget\s+everything',
            r'system\s*:',
            r'<\|.*?\|>',  # Special tokens like <|system|>
            r'\[INST\].*?\[/INST\]',  # Llama instruction tokens
            r'###\s*(system|assistant|user)\s*:',  # ChatML format
            r'<\|im_start\|>',  # ChatML start tokens
            r'<\|im_end\|>',  # ChatML end tokens
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                logger.warning(f"Potential prompt injection attempt detected: {pattern}")
                raise ValueError("Invalid query format detected. Please rephrase your question.")
        
        # Limit length (prevent extremely long queries)
        max_length = 1000
        if len(query) > max_length:
            logger.warning(f"Query truncated from {len(query)} to {max_length} characters")
            query = query[:max_length]
        
        # Remove excessive whitespace
        query = ' '.join(query.split())
        
        # Ensure query is not empty after sanitization
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        return query.strip()
    
    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for query"""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()
    
    def _get_query_result_cache_key(self, query: str, username: str) -> str:
        """Generate cache key for query result (includes username)"""
        combined = f"{username}:{query.lower().strip()}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _get_cached_query_result(self, query: str, username: str) -> Optional[Dict]:
        """Get cached query result if available"""
        cache_key = self._get_query_result_cache_key(query, username)
        if cache_key in self._query_result_cache:
            cached_data = self._query_result_cache[cache_key]
            # Check TTL
            if time.time() < cached_data.get("expiry_time", 0):
                # Move to end (most recently used)
                self._query_result_cache.pop(cache_key)
                self._query_result_cache[cache_key] = cached_data
                logger.info(f"Query result cache HIT for user {username}")
                return cached_data.get("result")
            else:
                # Expired, remove it
                self._query_result_cache.pop(cache_key)
        return None
    
    def _cache_query_result(self, query: str, username: str, result: Dict):
        """Cache query result with TTL"""
        cache_key = self._get_query_result_cache_key(query, username)
        # If cache is full, remove oldest entry
        if len(self._query_result_cache) >= self._query_result_cache_size:
            self._query_result_cache.popitem(last=False)  # Remove oldest
        # Add new entry
        self._query_result_cache[cache_key] = {
            "result": result,
            "expiry_time": time.time() + self._query_result_cache_ttl
        }
        logger.info(f"Query result cached for user {username}")
    
    def _is_simple_fact_query(self, query: str) -> bool:
        """
        Detect if query is a simple fact extraction query (not analytical).
        Uses general heuristics instead of hardcoded patterns.
        
        Simple fact queries:
        - Short queries (<= 6 words)
        - Start with question words (what, who, when, where, which)
        - Don't contain analytical verbs (explain, analyze, compare, describe, summarize)
        - Don't contain "why" or "how" (usually analytical)
        """
        query_lower = query.lower().strip()
        query_words = query_lower.split()
        query_length = len(query_words)
        
        # Very short queries are likely fact extraction
        if query_length <= 3:
            return True
        
        # Short queries (4-6 words) that start with fact question words
        fact_question_words = ["what", "who", "when", "where", "which"]
        analytical_verbs = ["explain", "analyze", "compare", "describe", "summarize", "discuss", "evaluate"]
        analytical_question_words = ["why", "how"]
        
        # Check if starts with fact question word
        starts_with_fact_word = any(query_lower.startswith(word + " ") or query_lower == word for word in fact_question_words)
        
        # Check if contains analytical terms
        contains_analytical = any(verb in query_lower for verb in analytical_verbs) or \
                             any(word in query_lower for word in analytical_question_words)
        
        # Simple fact query: short, starts with fact word, no analytical terms
        if query_length <= 6 and starts_with_fact_word and not contains_analytical:
            return True
        
        # Very short queries without analytical terms are likely fact extraction
        if query_length <= 4 and not contains_analytical:
            return True
        
        return False
    
    def _calculate_adaptive_max_results(self, query: str, default_max: int = 5) -> int:
        """
        Calculate adaptive max_results based on query complexity.
        AGGRESSIVE OPTIMIZATION for CPU inference:
        - Simple queries -> 1-2 chunks (minimal for fast response)
        - Complex queries -> 2-3 chunks (reduced from 4-5)
        - Medium queries -> 2 chunks (reduced from 5)
        """
        query_lower = query.lower().strip()
        query_length = len(query.split())
        
        # Simple queries: yes/no, single word, very short
        simple_patterns = ["yes", "no", "what is", "who is", "when", "where", "how many"]
        is_simple = any(query_lower.startswith(pattern) for pattern in simple_patterns) or query_length <= 3
        
        # Complex queries: long, multiple questions, "explain", "compare", "analyze"
        complex_patterns = ["explain", "compare", "analyze", "describe", "summarize", "why", "how does"]
        is_complex = any(pattern in query_lower for pattern in complex_patterns) or query_length > 15
        
        if is_simple:
            return min(2, default_max)  # AGGRESSIVE: 1-2 chunks for simple queries (was 3)
        elif is_complex:
            return min(3, default_max)  # AGGRESSIVE: 2-3 chunks for complex queries (was 5)
        else:
            return min(2, default_max)  # AGGRESSIVE: 2 chunks for medium (was 5)
    
    def _select_best_chunks(
        self,
        documents: List[str],
        metadatas: List[Dict],
        distances: List[float],
        max_results: int
    ) -> tuple[List[str], List[Dict]]:
        """
        PHASE 1 IMPROVEMENT 2: Select best chunks with diversity and quality
        
        Prioritizes:
        1. Highest similarity scores
        2. Diversity (max 1 chunk per document when possible)
        3. Quality (ensures we have enough context)
        """
        if not documents or len(documents) == 0:
            return [], []
        
        # Convert distances to similarities
        similarities = [1 - d for d in distances] if distances else [1.0] * len(documents)
        
        # Ensure we have similarities for all documents
        while len(similarities) < len(documents):
            similarities.append(1.0)
        
        # Create (doc, metadata, similarity) tuples
        candidates = list(zip(documents, metadatas, similarities))
        
        # Sort by similarity (highest first)
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        selected = []
        selected_doc_ids = set()
        
        # First pass: Select diverse sources (prefer different documents)
        for doc, metadata, sim in candidates:
            doc_id = metadata.get("document_id")
            
            # If we haven't seen this document yet, or we need more chunks
            if doc_id not in selected_doc_ids or len(selected) < max_results:
                selected.append((doc, metadata, sim))
                if doc_id:
                    selected_doc_ids.add(doc_id)
                
                if len(selected) >= max_results:
                    break
        
        # If we still need more chunks and have duplicates available, add best remaining
        if len(selected) < max_results:
            for doc, metadata, sim in candidates:
                if (doc, metadata, sim) not in selected:
                    selected.append((doc, metadata, sim))
                    if len(selected) >= max_results:
                        break
        
        # Sort selected by similarity again (in case we added duplicates)
        selected.sort(key=lambda x: x[2], reverse=True)
        
        # Return only top max_results
        selected = selected[:max_results]
        
        logger.info(
            f"Selected {len(selected)} chunks from {len(candidates)} candidates "
            f"(diverse sources: {len(selected_doc_ids)}, avg similarity: {sum(s[2] for s in selected) / len(selected):.3f})"
        )
        
        return [s[0] for s in selected], [s[1] for s in selected]
    
    async def _get_cached_embedding(self, query: str) -> Optional[List[float]]:
        """Get cached embedding if available (moves to end for LRU)"""
        async with self._cache_lock:
            cache_key = self._get_cache_key(query)
            if cache_key in self._embedding_cache:
                # Move to end (most recently used)
                embedding = self._embedding_cache.pop(cache_key)
                self._embedding_cache[cache_key] = embedding
                return embedding
            return None
    
    async def _cache_embedding(self, query: str, embedding: List[float]):
        """Cache embedding (with proper LRU eviction)"""
        async with self._cache_lock:
            cache_key = self._get_cache_key(query)
            # If key exists, remove it first (will be re-added at end)
            if cache_key in self._embedding_cache:
                self._embedding_cache.pop(cache_key)
            # If cache is full, remove oldest (first) entry
            elif len(self._embedding_cache) >= self._max_cache_size:
                self._embedding_cache.popitem(last=False)  # Remove oldest (FIFO)
            # Add new entry at end (most recently used)
            self._embedding_cache[cache_key] = embedding
    
    async def query(
        self,
        query: str,
        username: str,
        max_results: int = 2  # Reduced default from 5 for faster processing
    ) -> Dict:
        """
        Execute RAG query:
        1. Sanitize query (prevent prompt injection)
        2. Check query result cache (fastest path)
        3. Embed query (with caching)
        4. Retrieve relevant chunks (filtered by user access)
        5. Generate answer using Ollama
        6. Return answer with citations
        """
        # SECURITY: Sanitize query first to prevent prompt injection
        query = self._sanitize_query(query)
        
        # OPTIMIZATION 1: Check query result cache first (biggest performance win)
        cached_result = self._get_cached_query_result(query, username)
        if cached_result is not None:
            logger.info(f"Returning cached query result for user {username}")
            return cached_result
        
        # OPTIMIZATION 2: Adaptive max_results based on query complexity
        adaptive_max = self._calculate_adaptive_max_results(query, max_results)
        if adaptive_max != max_results:
            logger.info(f"Adaptive max_results: {max_results} -> {adaptive_max} (query complexity)")
            max_results = adaptive_max
        
        # Check cache for query embedding
        query_embedding = await self._get_cached_embedding(query)
        if query_embedding is None:
            # Generate query embedding
            query_embedding = await self.embedding_model.embed(query)
            # Cache it
            await self._cache_embedding(query, query_embedding)
        
        # Build filter for user-based access control
        # Users can only query documents they uploaded or have explicit access to
        # Get list of document IDs user has access to (with caching)
        if self._sqlite_db is None:
            from db.sqlite import SQLiteDB
            self._sqlite_db = SQLiteDB()
            await self._sqlite_db.initialize()
        
        # Check cache for user's accessible document IDs
        current_time = time.time()
        accessible_doc_ids = None
        
        if username in self._user_doc_cache:
            cached_ids, expiry_time = self._user_doc_cache[username]
            if current_time < expiry_time:
                accessible_doc_ids = cached_ids
        
        # If not in cache or expired, fetch from database
        if accessible_doc_ids is None:
            # Use optimized method that only fetches IDs, not full documents
            accessible_doc_ids = await self._sqlite_db.get_user_document_ids(username)
            # Cache for 5 minutes
            self._user_doc_cache[username] = (accessible_doc_ids, current_time + self._doc_cache_ttl)
        
        # Build filter for user-based access control
        # ChromaDB requires at least 2 conditions for $or, so we use direct filter when only one condition
        # We'll post-filter by document_id access after retrieval
        filter_dict = {
            "uploaded_by": username
        }
        
        # Note: ChromaDB doesn't support IN queries directly for document_id filtering
        # So we filter by uploaded_by at vector DB level and post-filter by document_id in results
        
        # OPTIMIZATION 3: Pre-filter by document IDs before vector search
        # Only search in documents user has access to (much faster for large databases)
        # If we have accessible_doc_ids, we can filter at vector DB level
        # For SimpleVectorDB, we'll still need post-filtering, but we can reduce n_results
        
        # Calculate how many results to fetch based on accessible documents
        # If user has access to many docs, fetch more; if few, fetch fewer
        accessible_doc_count = len(accessible_doc_ids) if accessible_doc_ids else 0
        if accessible_doc_count > 0:
            # Fetch more results if user has access to many documents
            # But cap at reasonable limit to avoid over-fetching
            fetch_multiplier = min(3.0, max(1.5, accessible_doc_count / 50))
            n_results_to_fetch = int(max_results * fetch_multiplier)
        else:
            # No accessible documents, but still fetch some in case
            n_results_to_fetch = max_results * 2
        
        # Retrieve relevant chunks
        results = await self.vector_db.query(
            query_embedding=query_embedding,
            n_results=n_results_to_fetch,
            filter_dict=filter_dict
        )
        
        # Handle both SimpleVectorDB (nested) and ChromaDB (flat) formats
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        
        if isinstance(documents, list) and len(documents) > 0:
            # Check if nested (SimpleVectorDB) or flat (ChromaDB)
            if isinstance(documents[0], list):
                documents = documents[0]  # Unwrap nested list
                metadatas = metadatas[0] if isinstance(metadatas, list) and len(metadatas) > 0 and isinstance(metadatas[0], list) else metadatas
            # else: already flat
        else:
            documents = []
            metadatas = []
        
        # Post-filter by document access: only keep chunks from accessible documents
        filtered_documents = []
        filtered_metadatas = []
        for i, doc in enumerate(documents):
            metadata = metadatas[i] if i < len(metadatas) else {}
            doc_id = metadata.get("document_id")
            # Allow if user uploaded it OR has explicit access
            if metadata.get("uploaded_by") == username or (doc_id and doc_id in accessible_doc_ids):
                filtered_documents.append(doc)
                filtered_metadatas.append(metadata)
            if len(filtered_documents) >= max_results:
                break
        
        documents = filtered_documents
        metadatas = filtered_metadatas
        
        # PHASE 1 IMPROVEMENT 1: Similarity threshold filtering
        # Filter out chunks with low similarity scores to improve relevance
        # Classification-based threshold (industry-standard)
        query_classification_prelim = self.query_classifier.classify(query, user_role=user_role or username)
        retrieval_strategy_prelim = self.query_classifier.get_retrieval_strategy(query_classification_prelim)
        
        # Use strategy threshold if available, otherwise use default
        if retrieval_strategy_prelim.get('similarity_threshold'):
            SIMILARITY_THRESHOLD = retrieval_strategy_prelim['similarity_threshold']
        else:
            # Fallback to legacy detection
            is_metadata_query_prelim = self._is_metadata_query(query, metadatas)
            if is_metadata_query_prelim:
                SIMILARITY_THRESHOLD = 0.3  # Lower threshold for metadata queries
            else:
                SIMILARITY_THRESHOLD = settings.SIMILARITY_THRESHOLD  # Cosine similarity (0-1, higher = stricter)
        all_distances = results.get("distances", [])
        
        # Map distances to filtered documents (after access filtering)
        filtered_distances = []
        if all_distances and len(all_distances) > 0:
            # Get original documents before access filtering to map distances correctly
            original_docs = results.get("documents", [])
            if isinstance(original_docs, list) and len(original_docs) > 0:
                if isinstance(original_docs[0], list):
                    original_docs = original_docs[0]
            
            # Map filtered documents back to their distances
            for i, doc in enumerate(documents):
                # Find this doc in original list
                try:
                    orig_idx = original_docs.index(doc)
                    if orig_idx < len(all_distances):
                        filtered_distances.append(all_distances[orig_idx])
                    else:
                        filtered_distances.append(1.0)
                except ValueError:
                    # Doc not found in original (shouldn't happen), use default
                    filtered_distances.append(1.0)
        
        # Now filter by similarity threshold
        if filtered_distances and len(filtered_distances) > 0:
            filtered_by_similarity = []
            filtered_metadatas_by_sim = []
            filtered_distances_by_sim = []
            
            for i, doc in enumerate(documents):
                distance = filtered_distances[i] if i < len(filtered_distances) else 1.0
                similarity = 1 - distance  # Convert distance to similarity
                
                if similarity >= SIMILARITY_THRESHOLD:
                    filtered_by_similarity.append(doc)
                    filtered_metadatas_by_sim.append(metadatas[i])
                    filtered_distances_by_sim.append(distance)
                else:
                    logger.debug(f"Filtered out chunk {i+1} with similarity {similarity:.3f} (threshold: {SIMILARITY_THRESHOLD})")
            
            if filtered_by_similarity:
                documents = filtered_by_similarity
                metadatas = filtered_metadatas_by_sim
                filtered_distances = filtered_distances_by_sim
                logger.info(f"Similarity filtering: {len(filtered_by_similarity)}/{len(filtered_documents)} chunks passed threshold")
            else:
                # If all chunks filtered out, use best one anyway
                logger.warning(f"All chunks filtered by similarity threshold. Using best match anyway.")
        
        # PHASE 1 IMPROVEMENT 2: Better chunk selection with diversity
        # Ensure we get diverse sources and prioritize highest similarity
        documents, metadatas = self._select_best_chunks(
            documents, metadatas, 
            filtered_distances if filtered_distances else [], 
            max_results
        )
        
        if not documents or len(documents) == 0:
            return {
                "answer": "I couldn't find any relevant information in the documents.",
                "citations": [],
                "sources": []
            }
        
        # Build context from retrieved chunks with token limit awareness
        # OPTIMIZATION 4: Smart early stopping - AGGRESSIVE for CPU inference
        chunker = Chunker()
        context_chunks = []
        total_context_tokens = 0
        # Use config values for thresholds
        min_context_tokens = settings.MIN_CONTEXT_TOKENS
        target_context_tokens = settings.TARGET_CONTEXT_TOKENS
        max_chunk_length = settings.MAX_CHUNK_LENGTH_TOKENS
        
        # Detect query type early for context building
        is_simple_fact = self._is_simple_fact_query(query)
        is_metadata_query = self._is_metadata_query(query, metadatas)
        
        for i, chunk in enumerate(documents):
            # AGGRESSIVE: Truncate chunks if they're too long
            chunk_tokens_original = chunker._count_tokens(chunk)
            if chunk_tokens_original > max_chunk_length:
                # Truncate chunk to max length
                chunk_words = chunk.split()
                # Approximate: 1 token ≈ 0.75 words, so truncate to ~600 words
                max_words = int(max_chunk_length * 0.75)
                chunk = " ".join(chunk_words[:max_words]) + "..."
                logger.info(f"Truncated chunk {i+1} from {chunk_tokens_original} to ~{max_chunk_length} tokens")
            
            # Include filename in context for title queries
            metadata = metadatas[i] if i < len(metadatas) else {}
            filename = metadata.get("filename", "")
            
            # For simple fact queries, include filename as hint
            if is_simple_fact and filename:
                chunk_text = f"[Doc{i+1} - {filename}]: {chunk}"
            else:
                chunk_text = f"[Doc{i+1}]: {chunk}"  # Shorter prefix to save tokens
            chunk_tokens = chunker._count_tokens(chunk_text)
            
            # AGGRESSIVE early stopping: stop much earlier for CPU speed
            if (total_context_tokens >= min_context_tokens and 
                total_context_tokens + chunk_tokens > target_context_tokens):
                logger.info(
                    f"Early stopping: Have {total_context_tokens} tokens (target: {target_context_tokens}), "
                    f"using {len(context_chunks)} chunks"
                )
                break
            
            # Hard limit: never exceed MAX_CONTEXT_TOKENS
            if total_context_tokens + chunk_tokens > MAX_CONTEXT_TOKENS:
                logger.warning(
                    f"Context limit reached. Using {len(context_chunks)} chunks "
                    f"({total_context_tokens} tokens) instead of {len(documents)} chunks"
                )
                break
            
            context_chunks.append(chunk_text)
            total_context_tokens += chunk_tokens
        
        context = "\n\n".join(context_chunks)
        
        # Log context size for debugging
        query_tokens = chunker._count_tokens(query)
        estimated_prompt_tokens = total_context_tokens + query_tokens + PROMPT_TEMPLATE_TOKENS
        logger.info(
            f"Prompt size: {estimated_prompt_tokens} tokens "
            f"(context: {total_context_tokens}, query: {query_tokens}, template: {PROMPT_TEMPLATE_TOKENS})"
        )
        
        if estimated_prompt_tokens > OLLAMA_CONTEXT_LIMIT:
            logger.warning(
                f"Warning: Estimated prompt ({estimated_prompt_tokens} tokens) exceeds "
                f"Ollama limit ({OLLAMA_CONTEXT_LIMIT} tokens). Truncation may occur."
            )
        
        # INDUSTRY-STANDARD: Classify query and get retrieval strategy (after retrieval)
        query_classification = self.query_classifier.classify(query, user_role=user_role or username)
        query_type = query_classification['type']
        retrieval_strategy = self.query_classifier.get_retrieval_strategy(query_classification)
        
        # Get document metadata for prompt enhancement
        document_metadata = None
        if self._sqlite_db and metadatas:
            # Try to get document metadata from first chunk's document
            first_doc_id = metadatas[0].get('document_id') if metadatas else None
            if first_doc_id:
                try:
                    # Get document metadata from SQLite
                    doc_metadata = await self._sqlite_db.get_document_metadata(first_doc_id)
                    if doc_metadata and doc_metadata.get('metadata', {}).get('audit_metadata'):
                        document_metadata = doc_metadata['metadata']['audit_metadata']
                except Exception as e:
                    logger.debug(f"Could not fetch document metadata: {e}")
        
        # Use audit-aware prompts if query is classified (industry-standard)
        use_audit_prompts = getattr(settings, 'USE_AUDIT_CHUNKER', True) and query_type != QueryType.GENERAL
        
        # Legacy detection (for backward compatibility)
        is_simple_fact = self._is_simple_fact_query(query)
        is_metadata_query = self._is_metadata_query(query, metadatas)
        
        if use_audit_prompts:
            # Build specialized audit prompt
            prompt = self.audit_prompt_builder.build_prompt(
                query=query,
                context=context,
                query_type=query_type,
                user_role=user_role,
                document_metadata=document_metadata
            )
        elif is_metadata_query:
            # Special handling for document metadata queries
            # Extract document titles/filenames from metadata
            doc_titles = []
            for i, metadata in enumerate(metadatas):
                filename = metadata.get("filename", "")
                doc_id = metadata.get("document_id", "")
                if filename:
                    doc_titles.append(f"Document {i+1} (ID: {doc_id}): {filename}")
            
            if doc_titles:
                prompt = f"""You are answering a question about document metadata (titles, filenames, etc.).

Available Documents:
{chr(10).join(doc_titles)}

Question: {query}

Instructions:
- Answer ONLY using the document titles/filenames listed above
- If asking for "title" or "name", provide the filename(s) from the list
- If asking about a specific document, match it by ID or position
- Be direct and concise
- If the question cannot be answered from the document list, say: "I cannot find that information in the available documents."

Answer:"""
            else:
                # Fallback to context-based answer
                prompt = f"""Answer the question using the context below.

Context:
{context}

Question: {query}

Answer:"""
        elif is_simple_fact:
            # Direct prompt for simple fact extraction
            prompt = f"""Read the question carefully, then find the answer in the context below.

Question: {query}

Context:
{context}

Instructions:
1. Understand what the question is asking for
2. Search the context for information that directly answers the question
3. Extract the exact answer from the context
4. If the answer is found, state it directly without extra text
5. If not found, say: "The information is not available in the provided documents."
6. Do not include random text that doesn't answer the question

Answer:"""
        else:
            # Standard prompt for complex questions (fallback if audit prompts not used)
            prompt = f"""You are a precise document analysis assistant. Read the question carefully, then answer using ONLY the provided context.

Question: {query}

Context:
{context}

Guidelines:
1. First, understand what the question is asking for
2. Search the context for relevant information
3. Base your answer STRICTLY on the context above
4. If the context doesn't contain enough information, state: "Based on the provided documents, I cannot find sufficient information to answer this question."
5. Cite sources using [Doc1], [Doc2], etc. when referencing specific information
6. Be accurate and concise
7. If multiple documents provide conflicting information, mention both perspectives
8. Do not include random text that doesn't answer the question

Answer:"""
        
        # Call Ollama
        try:
            # Ollama client generate is synchronous, but we'll run it in executor
            import asyncio
            loop = asyncio.get_event_loop()
            
            # Hardware-aware timeout and options
            def generate_response():
                try:
                    return self.ollama_client.generate(
                        model=settings.OLLAMA_MODEL,
                        prompt=prompt,
                        stream=False,
                        options={
                            'timeout': self.ollama_timeout * 1000,  # Convert to milliseconds
                            'num_predict': self.max_response_tokens,  # Hardware-aware response length
                            'temperature': 0.7,
                        }
                    )
                except Exception as e:
                    logger.error(f"Ollama generate error: {e}")
                    raise
            
            # Hardware-aware timeout (30s for GPU, 120s for CPU)
            response = await asyncio.wait_for(
                loop.run_in_executor(None, generate_response),
                timeout=float(self.ollama_timeout)
            )
            
            # Extract response - Ollama returns different formats depending on version
            if isinstance(response, dict):
                answer = response.get("response", response.get("text", "No response generated"))
            elif hasattr(response, "response"):
                answer = response.response
            else:
                answer = str(response)
                
            # Clean up the answer
            if not answer or answer.strip() == "":
                answer = "I couldn't generate a response. Please try rephrasing your question."
                
        except asyncio.TimeoutError:
            timeout_msg = f"{self.ollama_timeout} seconds"
            gpu_msg = "Consider using GPU for faster inference" if not self.gpu_available else ""
            logger.error(f"Ollama generation timed out after {timeout_msg}")
            answer = f"⚠️ Query timed out after {timeout_msg}. {'CPU inference is very slow. ' if not self.gpu_available else ''}\n\nSuggestions:\n- Try a simpler, shorter query\n- Use fewer documents\n{gpu_msg}\n- Check Ollama: `ollama list`\n\nYour query was processed but Ollama took too long to respond."
        except ConnectionError as e:
            logger.error(f"Ollama connection error: {e}")
            answer = f"⚠️ Cannot connect to Ollama. Please ensure Ollama is running:\n\n1. Start Ollama: `ollama serve`\n2. Verify model is installed: `ollama list`\n3. Install model if needed: `ollama pull {settings.OLLAMA_MODEL}`\n\nError: {str(e)}"
        except Exception as e:
            logger.error(f"Ollama generation error: {e}", exc_info=True)
            error_msg = str(e)
            if "model" in error_msg.lower() or "not found" in error_msg.lower():
                answer = f"⚠️ Model '{settings.OLLAMA_MODEL}' not found. Please install it:\n\n`ollama pull {settings.OLLAMA_MODEL}`\n\nThen try your query again."
            else:
                answer = f"⚠️ Error generating response: {error_msg}\n\nPlease ensure:\n- Ollama is running at {settings.OLLAMA_BASE_URL}\n- Model '{settings.OLLAMA_MODEL}' is installed\n- Check Ollama logs for details"
        
        # Use filtered metadatas (already processed above)
        
        citations = []
        sources = []
        for i, metadata in enumerate(metadatas):
            citations.append({
                "chunk_index": i,
                "document_id": metadata.get("document_id"),
                "filename": metadata.get("filename"),
                "reference": f"[Document {i+1}]"
            })
            if metadata.get("filename") not in sources:
                sources.append(metadata.get("filename"))
        
        # OPTIMIZATION 1 (continued): Cache the query result before returning
        result = {
            "answer": answer,
            "citations": citations,
            "sources": sources
        }
        
        # Cache the result for future queries (only cache successful results, not errors)
        if not answer.startswith("⚠️"):
            self._cache_query_result(query, username, result)
        
        return result
    
    async def query_stream(
        self,
        query: str,
        username: str,
        max_results: int = 2  # Reduced default from 5 for faster processing
    ) -> AsyncGenerator[str, None]:
        """
        Execute RAG query with streaming response
        Yields Server-Sent Events (SSE) format chunks
        Note: Streaming queries don't use result caching (they're meant to stream)
        """
        import asyncio
        
        # SECURITY: Sanitize query first to prevent prompt injection
        query = self._sanitize_query(query)
        
        # OPTIMIZATION 2: Adaptive max_results based on query complexity
        adaptive_max = self._calculate_adaptive_max_results(query, max_results)
        if adaptive_max != max_results:
            logger.info(f"Streaming: Adaptive max_results: {max_results} -> {adaptive_max}")
            max_results = adaptive_max
        
        # Check cache for query embedding
        query_embedding = await self._get_cached_embedding(query)
        if query_embedding is None:
            # Generate query embedding
            query_embedding = await self.embedding_model.embed(query)
            # Cache it
            await self._cache_embedding(query, query_embedding)
        
        # Build filter for user-based access control
        # Get list of document IDs user has access to
        if self._sqlite_db is None:
            from db.sqlite import SQLiteDB
            self._sqlite_db = SQLiteDB()
            await self._sqlite_db.initialize()
        
        # Check cache for user's accessible document IDs
        current_time = time.time()
        accessible_doc_ids = None
        
        if username in self._user_doc_cache:
            cached_ids, expiry_time = self._user_doc_cache[username]
            if current_time < expiry_time:
                accessible_doc_ids = cached_ids
        
        # If not in cache or expired, fetch from database
        if accessible_doc_ids is None:
            accessible_doc_ids = await self._sqlite_db.get_user_document_ids(username)
            # Cache for 5 minutes
            self._user_doc_cache[username] = (accessible_doc_ids, current_time + self._doc_cache_ttl)
        
        # Build filter for user-based access control
        # ChromaDB requires at least 2 conditions for $or, so we use direct filter when only one condition
        filter_dict = {
            "uploaded_by": username
        }
        
        # OPTIMIZATION 3: Pre-filter by document IDs before vector search
        accessible_doc_count = len(accessible_doc_ids) if accessible_doc_ids else 0
        if accessible_doc_count > 0:
            fetch_multiplier = min(3.0, max(1.5, accessible_doc_count / 50))
            n_results_to_fetch = int(max_results * fetch_multiplier)
        else:
            n_results_to_fetch = max_results * 2
        
        # Retrieve relevant chunks
        results = await self.vector_db.query(
            query_embedding=query_embedding,
            n_results=n_results_to_fetch,
            filter_dict=filter_dict
        )
        
        # Handle document formats
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        
        if isinstance(documents, list) and len(documents) > 0:
            if isinstance(documents[0], list):
                documents = documents[0]
                metadatas = metadatas[0] if isinstance(metadatas, list) and len(metadatas) > 0 and isinstance(metadatas[0], list) else metadatas
        else:
            documents = []
            metadatas = []
        
        # Post-filter by document access
        filtered_documents = []
        filtered_metadatas = []
        for i, doc in enumerate(documents):
            metadata = metadatas[i] if i < len(metadatas) else {}
            doc_id = metadata.get("document_id")
            if metadata.get("uploaded_by") == username or (doc_id and doc_id in accessible_doc_ids):
                filtered_documents.append(doc)
                filtered_metadatas.append(metadata)
            if len(filtered_documents) >= max_results:
                break
        
        documents = filtered_documents
        metadatas = filtered_metadatas
        
        # PHASE 1 IMPROVEMENT 1: Similarity threshold filtering (streaming)
        SIMILARITY_THRESHOLD = settings.SIMILARITY_THRESHOLD  # Cosine similarity (0-1, higher = more similar)
        distances = results.get("distances", [])
        
        if distances and len(distances) > 0:
            if len(distances) >= len(documents):
                filtered_by_similarity = []
                filtered_metadatas_by_sim = []
                
                for i, doc in enumerate(documents):
                    distance = distances[i] if i < len(distances) else 1.0
                    similarity = 1 - distance
                    
                    if similarity >= SIMILARITY_THRESHOLD:
                        filtered_by_similarity.append(doc)
                        filtered_metadatas_by_sim.append(metadatas[i])
                
                if filtered_by_similarity:
                    documents = filtered_by_similarity
                    metadatas = filtered_metadatas_by_sim
                    logger.info(f"Streaming: Similarity filtering: {len(filtered_by_similarity)}/{len(filtered_documents)} chunks passed")
        
        # PHASE 1 IMPROVEMENT 2: Better chunk selection with diversity (streaming)
        documents, metadatas = self._select_best_chunks(
            documents, metadatas,
            results.get("distances", []),
            max_results
        )
        
        citations = []
        sources = []
        for i, metadata in enumerate(metadatas):
            citations.append({
                "chunk_index": i,
                "document_id": metadata.get("document_id"),
                "filename": metadata.get("filename"),
                "reference": f"[Document {i+1}]"
            })
            if metadata.get("filename") not in sources:
                sources.append(metadata.get("filename"))
        
        # Send metadata first
        yield f"data: {json.dumps({'type': 'metadata', 'citations': citations, 'sources': sources})}\n\n"
        
        if not documents or len(documents) == 0:
            yield f"data: {json.dumps({'type': 'done', 'text': 'I could not find any relevant information in the documents.'})}\n\n"
            return
        
        # Send a status message that we're starting generation
        yield f"data: {json.dumps({'type': 'status', 'text': 'Generating response... This may take a while on CPU.'})}\n\n"
        
        # Build context with token limit awareness - AGGRESSIVE for CPU inference
        # OPTIMIZATION 4: Smart early stopping - AGGRESSIVE for CPU inference
        chunker = Chunker()
        context_chunks = []
        total_context_tokens = 0
        # Use config values for thresholds
        min_context_tokens = settings.MIN_CONTEXT_TOKENS
        target_context_tokens = settings.TARGET_CONTEXT_TOKENS
        max_chunk_length = settings.MAX_CHUNK_LENGTH_TOKENS
        
        # Detect query type early for context building (streaming)
        is_simple_fact = self._is_simple_fact_query(query)
        is_metadata_query = self._is_metadata_query(query, metadatas)
        
        for i, chunk in enumerate(documents):
            # AGGRESSIVE: Truncate chunks if they're too long
            chunk_tokens_original = chunker._count_tokens(chunk)
            if chunk_tokens_original > max_chunk_length:
                chunk_words = chunk.split()
                max_words = int(max_chunk_length * 0.75)
                chunk = " ".join(chunk_words[:max_words]) + "..."
                logger.info(f"Streaming: Truncated chunk {i+1} from {chunk_tokens_original} to ~{max_chunk_length} tokens")
            
            # Include filename in context for title queries (streaming)
            metadata = metadatas[i] if i < len(metadatas) else {}
            filename = metadata.get("filename", "")
            
            # For simple fact queries, include filename as hint
            if is_simple_fact and filename:
                chunk_text = f"[Doc{i+1} - {filename}]: {chunk}"
            else:
                chunk_text = f"[Doc{i+1}]: {chunk}"  # Shorter prefix
            chunk_tokens = chunker._count_tokens(chunk_text)
            
            # AGGRESSIVE early stopping
            if (total_context_tokens >= min_context_tokens and 
                total_context_tokens + chunk_tokens > target_context_tokens):
                logger.info(
                    f"Streaming: Early stopping: Have {total_context_tokens} tokens (target: {target_context_tokens}), "
                    f"using {len(context_chunks)} chunks"
                )
                break
            
            # Hard limit
            if total_context_tokens + chunk_tokens > MAX_CONTEXT_TOKENS:
                logger.warning(
                    f"Streaming: Context limit reached. Using {len(context_chunks)} chunks "
                    f"({total_context_tokens} tokens) instead of {len(documents)} chunks"
                )
                break
            
            context_chunks.append(chunk_text)
            total_context_tokens += chunk_tokens
        
        context = "\n\n".join(context_chunks)
        
        # Log context size
        query_tokens = chunker._count_tokens(query)
        estimated_prompt_tokens = total_context_tokens + query_tokens + PROMPT_TEMPLATE_TOKENS
        logger.info(
            f"Streaming prompt size: {estimated_prompt_tokens} tokens "
            f"(context: {total_context_tokens}, query: {query_tokens})"
        )
        
        # IMPROVED: Better prompt engineering with query type detection (streaming)
        is_metadata_query = self._is_metadata_query(query, metadatas)
        
        if is_metadata_query:
            # Special handling for document metadata queries
            doc_titles = []
            for i, metadata in enumerate(metadatas):
                filename = metadata.get("filename", "")
                doc_id = metadata.get("document_id", "")
                if filename:
                    doc_titles.append(f"Document {i+1} (ID: {doc_id}): {filename}")
            
            if doc_titles:
                prompt = f"""You are answering a question about document metadata (titles, filenames, etc.).

Available Documents:
{chr(10).join(doc_titles)}

Question: {query}

Instructions:
- Answer ONLY using the document titles/filenames listed above
- If asking for "title" or "name", provide the filename(s) from the list
- Be direct and concise
- If the question cannot be answered from the document list, say: "I cannot find that information in the available documents."

Answer:"""
            else:
                prompt = f"""Answer the question using the context below.

Context:
{context}

Question: {query}

Answer:"""
        elif is_simple_fact:
            # Direct prompt for simple fact extraction
            prompt = f"""Answer the question directly and concisely using ONLY the context below.

Context:
{context}

Question: {query}

Instructions:
- Extract the exact answer from the context
- If the answer is in the context, state it directly
- If not found, say: "The information is not available in the provided documents."
- Do not add explanations unless asked

Answer:"""
        else:
            # Standard prompt for complex questions
            prompt = f"""You are a precise document analysis assistant. Answer the question using ONLY the provided context.

Context:
{context}

Question: {query}

Guidelines:
1. Base your answer STRICTLY on the context above
2. If the context doesn't contain enough information, state: "Based on the provided documents, I cannot find sufficient information to answer this question."
3. Cite sources using [Doc1], [Doc2], etc. when referencing specific information
4. Be accurate and concise
5. If multiple documents provide conflicting information, mention both perspectives

Answer:"""
        
        # Stream from Ollama
        try:
            # Use a queue to bridge sync Ollama stream to async generator
            import queue
            import threading
            
            q = queue.Queue()
            error_occurred = threading.Event()
            error_message = [None]
            
            def stream_ollama():
                """Stream from Ollama in a separate thread"""
                try:
                    logger.info(f"Starting Ollama stream (model: {settings.OLLAMA_MODEL}, max_tokens: {self.max_response_tokens})")
                    stream = self.ollama_client.generate(
                        model=settings.OLLAMA_MODEL,
                        prompt=prompt,
                        stream=True,
                        options={
                            'num_predict': self.max_response_tokens,  # Hardware-aware response length
                            'temperature': 0.7,
                        }
                    )
                    chunk_count = 0
                    for chunk in stream:
                        chunk_count += 1
                        # Ollama returns dicts with 'response' key for streaming
                        if isinstance(chunk, dict):
                            # Check multiple possible keys
                            text = chunk.get("response", "") or chunk.get("text", "") or chunk.get("content", "")
                            # Also check if there's a nested response
                            if not text and "message" in chunk:
                                msg = chunk.get("message", {})
                                if isinstance(msg, dict):
                                    text = msg.get("content", "")
                            # Check for done flag
                            if chunk.get("done", False):
                                logger.info(f"Ollama stream completed ({chunk_count} chunks)")
                                q.put(('done', None))
                                return
                        elif hasattr(chunk, "response"):
                            text = chunk.response
                        elif hasattr(chunk, "text"):
                            text = chunk.text
                        else:
                            text = str(chunk) if chunk else ""
                        
                        # Only send non-empty text
                        if text and text.strip():
                            q.put(('token', text))
                    
                    logger.info(f"Ollama stream finished ({chunk_count} chunks)")
                    q.put(('done', None))
                except Exception as e:
                    logger.error(f"Ollama streaming error: {e}", exc_info=True)
                    error_message[0] = str(e)
                    error_occurred.set()
                    q.put(('error', str(e)))
            
            # Start streaming in background thread
            thread = threading.Thread(target=stream_ollama, daemon=True)
            thread.start()
            
            # Yield tokens as they arrive
            max_wait_time = self.ollama_timeout  # Hardware-aware timeout
            start_time = time.time()
            last_token_time = time.time()
            no_token_warning_sent = False
            
            while True:
                try:
                    # Wait for item with longer timeout (1 second instead of 0.1)
                    # This prevents busy-waiting and allows Ollama more time
                    item = q.get(timeout=1.0)
                    event_type, data = item
                    
                    if event_type == 'token':
                        last_token_time = time.time()
                        no_token_warning_sent = False
                        yield f"data: {json.dumps({'type': 'token', 'text': data})}\n\n"
                    elif event_type == 'done':
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
                        break
                    elif event_type == 'error':
                        raise Exception(data)
                except queue.Empty:
                    # Check if error occurred
                    if error_occurred.is_set():
                        raise Exception(error_message[0] or "Unknown error")
                    
                    # Check for timeout - if no tokens for 30 seconds, send warning
                    elapsed_since_token = time.time() - last_token_time
                    if elapsed_since_token > 30 and not no_token_warning_sent:
                        logger.warning(f"No tokens received for {elapsed_since_token:.1f} seconds")
                        yield f"data: {json.dumps({'type': 'warning', 'text': 'Still processing... This may take a while.'})}\n\n"
                        no_token_warning_sent = True
                    
                    # Check total time - hardware-aware timeout
                    total_elapsed = time.time() - start_time
                    if total_elapsed > max_wait_time:
                        timeout_msg = f"{max_wait_time} seconds"
                        gpu_msg = "Try a simpler, shorter query or consider using GPU." if not self.gpu_available else "Try a simpler, shorter query."
                        logger.error(f"Streaming exceeded max wait time of {timeout_msg}")
                        error_text = f"Query timed out after {timeout_msg}. Ollama is taking too long to respond.\n\n{gpu_msg}\n\nSuggestions:\n- Try a shorter, simpler query\n- Reduce the number of documents\n- Check if Ollama is running: `ollama list`"
                        yield f"data: {json.dumps({'type': 'error', 'text': error_text})}\n\n"
                        # Flush the error before breaking
                        import sys
                        sys.stdout.flush()
                        break
                    
                    # Continue waiting
                    continue
                except Exception as e:
                    logger.error(f"Streaming error: {e}")
                    raise e
            
            # Wait for thread to finish (with timeout)
            thread.join(timeout=5)
            if thread.is_alive():
                # Thread is still running, log warning but don't block
                logger.warning("Ollama streaming thread did not finish within timeout - it will continue in background")
                # Don't warn - just let it finish in background since it's a daemon thread
            
        except ConnectionError as e:
            import traceback
            error_msg = f"⚠️ Cannot connect to Ollama. Please ensure Ollama is running:\n\n1. Start Ollama: `ollama serve`\n2. Verify model is installed: `ollama list`\n3. Install model if needed: `ollama pull {settings.OLLAMA_MODEL}`\n\nError: {str(e)}"
            print(f"Connection error: {error_msg}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'text': error_msg})}\n\n"
        except Exception as e:
            import traceback
            error_msg = str(e)
            error_trace = traceback.format_exc()
            print(f"Streaming error: {error_msg}\n{error_trace}")
            if "model" in error_msg.lower() or "not found" in error_msg.lower():
                error_text = f"⚠️ Model '{settings.OLLAMA_MODEL}' not found. Please install it:\n\n`ollama pull {settings.OLLAMA_MODEL}`\n\nThen try your query again."
            else:
                error_text = f"⚠️ Error generating response: {error_msg}\n\nPlease ensure:\n- Ollama is running at {settings.OLLAMA_BASE_URL}\n- Model '{settings.OLLAMA_MODEL}' is installed\n- Check Ollama logs for details"
            yield f"data: {json.dumps({'type': 'error', 'text': error_text})}\n\n"

