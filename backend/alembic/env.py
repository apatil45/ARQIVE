"""
Alembic environment. Uses sync DB URL (sqlite:// or postgresql://).
Loads .env from project root so DATABASE_URL is set.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env from project root (parent of backend/)
_root = Path(__file__).resolve().parents[1].parent
_env_file = _root / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file)

# Ensure app is importable
_backend = Path(__file__).resolve().parents[1]
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy.pool import StaticPool
from alembic import context

from app.db.base import Base, create_sync_engine_url
from app.db.models import Tenant, User, Document, Chunk, AuditLog  # noqa: F401 — register models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url with env
url = create_sync_engine_url()
config.set_main_option("sqlalchemy.url", url)

# Ensure data dir exists for SQLite (./data/arqive_dev.db)
if "sqlite" in url and "/" in url:
    from pathlib import Path
    path = Path(url.replace("sqlite:///", "").split("?")[0])
    if not path.is_absolute():
        path = _backend / path
    path.parent.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL only)."""
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to DB)."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = url
    if url.startswith("sqlite"):
        engine = engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=StaticPool,
        )
    else:
        engine = engine_from_config(configuration, prefix="sqlalchemy.")
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
