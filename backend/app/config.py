"""
Application config via pydantic-settings. All env; no hardcoded secrets.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load from .env. Never hardcode secrets."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_ENV: Literal["development", "demo", "production"] = "development"
    APP_SECRET_KEY: str = "change-me-min-32-chars"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/arqive_dev.db"

    # ChromaDB
    CHROMA_PERSIST_PATH: str = "./data/chromadb"

    # Ollama (health/model settings; runtime URL is fixed to localhost in code)
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_TIMEOUT: int = 120

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_CACHE_PATH: str = "./data/models"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage
    STORAGE_BACKEND: Literal["local", "s3", "minio"] = "local"
    STORAGE_LOCAL_PATH: str = "./data/documents"
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET_NAME: str = "arqive-documents"
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_REGION: str = "eu-west-2"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # License
    ARQIVE_LICENSE_KEY: str = "dev-unlimited"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "pretty"] = "pretty"

    # Demo
    DEMO_MODE: bool = False
    DEMO_RESET_HOURS: int = 24


def get_settings() -> Settings:
    """Return settings. Load .env from project root (parent of backend) when present."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        return Settings(_env_file=str(env_path))
    return Settings()
