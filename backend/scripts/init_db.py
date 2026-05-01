"""
Create tables and optionally seed demo data. Run from backend/ with PYTHONPATH=backend.
Usage: python scripts/init_db.py   (or from repo root: python backend/scripts/init_db.py)
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure app is on path
_backend = Path(__file__).resolve().parents[1]
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

# Load .env from project root
_root = _backend.parent
_env = _root / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    from app.db.models import Tenant, User, Document, Chunk, AuditLog  # noqa: F401

    url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/arqive_dev.db")
    if url.startswith("sqlite"):
        # Ensure data dir exists
        path = url.replace("sqlite+aiosqlite:///", "").split("?")[0]
        p = _backend / path if not path.startswith("/") else Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables created.")
    await engine.dispose()


def main() -> None:
    asyncio.run(create_tables())


if __name__ == "__main__":
    main()
