"""
Sync SQLAlchemy engine/session for Celery worker. Worker cannot use async.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base import create_sync_engine_url

# Load .env before config
_root = Path(__file__).resolve().parents[3]  # backend -> project root
_env = _root / ".env"
if _env.exists():
    load_dotenv(_env)


def get_sync_engine():
    url = create_sync_engine_url()
    return create_engine(url, echo=False)


_sync_engine = None


def get_sync_session_factory():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = get_sync_engine()
    return sessionmaker(_sync_engine, class_=Session, expire_on_commit=False)


def get_sync_session() -> Session:
    return get_sync_session_factory()()
