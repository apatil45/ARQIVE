"""
SQLAlchemy 2.0 base and engine factory.
DB backend swaps via env: SQLite (dev) or PostgreSQL (prod).
"""
from __future__ import annotations

import os

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all models. Use Mapped[] annotations."""


def get_engine_url() -> str:
    """Return DATABASE_URL from environment. Used by Alembic and sync engine."""
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/arqive_dev.db")


def create_sync_engine_url() -> str:
    """
    For Alembic and scripts: SQLite async URL must be converted to sync.
    aiosqlite:// -> sqlite:// (same path).
    """
    url = get_engine_url()
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url
