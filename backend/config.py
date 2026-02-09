"""
ARQIVE Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Ignore extra fields in .env file
    )
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    
    # JWT
    SECRET_KEY: str = ""  # Must be set via environment variable (min 32 chars)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    SQLITE_DB_PATH: str = "data/arqive.db"
    CHROMA_DB_PATH: str = "data/chroma_db"
    
    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"  # Local sentence-transformers model
    EMBEDDING_DIMENSION: int = 384
    
    # Chunking
    CHUNK_SIZE: int = 400  # tokens
    CHUNK_OVERLAP: int = 50  # tokens
    USE_AUDIT_CHUNKER: bool = True  # Use audit-aware chunking for better structure preservation
    
    # Accuracy Improvements (Phase 1)
    SIMILARITY_THRESHOLD: float = 0.6  # Filter chunks below this similarity (0-1, higher = stricter)
    
    # RAG
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "tinyllama"  # Fast CPU model. Alternatives: "llama2:7b" (if phi-2 unavailable). Install with: ollama pull tinyllama
    MAX_CONTEXT_CHUNKS: int = 2  # Reduced from 5 for faster processing
    
    # RAG Performance & Limits
    OLLAMA_CONTEXT_LIMIT: int = 4096  # Maximum context window for Ollama models
    PROMPT_TEMPLATE_TOKENS: int = 50  # Estimated tokens for prompt template
    RESERVE_FOR_RESPONSE: int = 100  # Reserve tokens for LLM response
    MAX_CONTEXT_TOKENS: int = 1500  # Maximum context tokens to send to LLM (CPU optimized)
    MAX_CONTEXT_TOKENS_GPU: int = 2000  # Maximum context tokens for GPU (higher limit)
    MIN_CONTEXT_TOKENS: int = 50  # Minimum context tokens for basic answer
    TARGET_CONTEXT_TOKENS: int = 500  # Target context tokens for fast processing
    MAX_CHUNK_LENGTH_TOKENS: int = 400  # Maximum chunk length before truncation
    
    # RAG Timeouts (seconds)
    OLLAMA_TIMEOUT_GPU: int = 30  # Timeout for GPU inference
    OLLAMA_TIMEOUT_CPU: int = 60  # Timeout for CPU inference
    MAX_RESPONSE_TOKENS_GPU: int = 400  # Max response tokens for GPU
    MAX_RESPONSE_TOKENS_CPU: int = 250  # Max response tokens for CPU
    
    # RAG Caching
    EMBEDDING_CACHE_SIZE: int = 1000  # LRU cache size for query embeddings
    QUERY_RESULT_CACHE_SIZE: int = 500  # Max cached query results
    QUERY_RESULT_CACHE_TTL: int = 3600  # Query result cache TTL (1 hour)
    USER_DOC_CACHE_TTL: int = 300  # User document access cache TTL (5 minutes)
    
    # Document Processing
    UPLOAD_DIR: str = "data/uploads"
    MAX_FILE_SIZE_MB: int = 50
    
    # S3 Storage (optional - if not configured, uses local storage)
    USE_S3: bool = False  # Set to True to enable S3 storage
    S3_BUCKET_NAME: str = ""  # S3 bucket name
    S3_REGION: str = "us-east-1"  # AWS region
    S3_ACCESS_KEY_ID: str = ""  # AWS access key (optional if using IAM role)
    S3_SECRET_ACCESS_KEY: str = ""  # AWS secret key (optional if using IAM role)
    
    # Debug/Development
    DEBUG: bool = False  # Set to True for detailed error messages
    USE_JSON_LOGGING: bool = False  # Set to True for JSON structured logging (better for log aggregation)
    
    # Environment
    ENVIRONMENT: str = "development"  # development, staging, production
    
    # Security
    ENFORCE_SECRET_KEY: bool = False  # Set to True in production to enforce SECRET_KEY validation
    
    # SQLite Connection Pooling
    SQLITE_POOL_SIZE: int = 5  # Number of connections to keep in pool
    SQLITE_MAX_OVERFLOW: int = 10  # Maximum additional connections beyond pool_size
    SQLITE_USE_POOL: bool = True  # Set to False to disable connection pooling (backward compatible)


# Validate settings on load
settings = Settings()

# Validate SECRET_KEY and generate if needed
if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
    import secrets
    import warnings
    import os
    
    # In production, enforce SECRET_KEY requirement
    if settings.ENFORCE_SECRET_KEY or os.getenv("ENFORCE_SECRET_KEY", "").lower() in ("true", "1", "yes"):
        raise ValueError(
            "SECRET_KEY is required and must be at least 32 characters. "
            "Set SECRET_KEY environment variable for production deployment."
        )
    
    warnings.warn(
        "SECRET_KEY not set or too short! Generated temporary key. "
        "Set SECRET_KEY environment variable (min 32 chars) for production! "
        "Set ENFORCE_SECRET_KEY=true to enforce this requirement.",
        UserWarning
    )
    # Note: We can't directly modify the settings object, but the warning is enough
    # The app will work with the generated key, but user should set it properly


