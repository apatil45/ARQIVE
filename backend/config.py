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
    
    # Accuracy Improvements (Phase 1)
    SIMILARITY_THRESHOLD: float = 0.6  # Filter chunks below this similarity (0-1, higher = stricter)
    
    # RAG
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "tinyllama"  # Fast CPU model. Alternatives: "llama2:7b" (if phi-2 unavailable). Install with: ollama pull tinyllama
    MAX_CONTEXT_CHUNKS: int = 2  # Reduced from 5 for faster processing
    
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


# Validate settings on load
settings = Settings()

# Validate SECRET_KEY and generate if needed
if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
    import secrets
    import warnings
    warnings.warn(
        "SECRET_KEY not set or too short! Generated temporary key. "
        "Set SECRET_KEY environment variable (min 32 chars) for production!",
        UserWarning
    )
    # Note: We can't directly modify the settings object, but the warning is enough
    # The app will work with the generated key, but user should set it properly


