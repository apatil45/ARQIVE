"""
Seed demo tenant, users, and sample documents. Run after init_db.
Creates: ARQIVE Demo Organisation, viewer/auditor/admin users, loads demo_docs.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure app is on path
_backend = Path(__file__).resolve().parents[1]
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

_root = _backend.parent
_env = _root / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Demo users: email / password (plaintext for seed only)
DEMO_USERS = [
    ("viewer@demo.arqive.com", "DemoViewer123!", "Demo Viewer", "viewer"),
    ("auditor@demo.arqive.com", "DemoAuditor123!", "Demo Auditor", "auditor"),
    ("admin@demo.arqive.com", "DemoAdmin123!", "Demo Admin", "admin"),
]


async def seed() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select

    from app.db.models import Tenant, User

    url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/arqive_dev.db")
    engine = create_async_engine(url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if demo tenant already exists
        result = await session.execute(select(Tenant).where(Tenant.slug == "arqive-demo"))
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Demo tenant already exists. Skip seed.")
            return

        # Create demo tenant
        tenant = Tenant(
            name="ARQIVE Demo Organisation",
            slug="arqive-demo",
            license_key="demo-license-hash",  # In real seed, bcrypt hash
            license_expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            is_active=True,
            max_users=10,
        )
        session.add(tenant)
        await session.flush()

        from app.core.security import hash_password
        # Create demo users (bcrypt-hashed)
        for email, password, full_name, role in DEMO_USERS:
            user = User(
                tenant_id=tenant.id,
                email=email,
                hashed_password=hash_password(password),
                full_name=full_name,
                role=role,
                is_active=True,
            )
            session.add(user)

        await session.commit()
        logger.info("Demo tenant and 3 users created. Load demo_docs in Session 6 (ingestion).")

    await engine.dispose()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
