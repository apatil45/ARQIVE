"""
Pytest fixtures: async client, test DB, demo user for auth tests.
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Set env before importing app (so config and DB use test settings)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["APP_SECRET_KEY"] = "test-secret-key-min-32-chars-long"

from app.main import app
from app.db.base import Base
from app.db.models import Tenant, User
from app.core.security import hash_password


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_engine, test_user):
    """Async HTTP client; get_db overridden to use test engine. test_user created first."""
    from app.db.session import get_db

    async def override_get_db():
        factory = async_sessionmaker(
            db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# Simpler client that doesn't override DB: use for auth tests with pre-seeded data
@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_tenant(db_session):
    from datetime import datetime, timezone, timedelta
    t = Tenant(
        name="Test Tenant",
        slug="test-tenant",
        license_key="hash",
        license_expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        is_active=True,
        max_users=10,
    )
    db_session.add(t)
    await db_session.flush()
    return t


@pytest_asyncio.fixture
async def test_user(db_session, test_tenant):
    u = User(
        tenant_id=test_tenant.id,
        email="auditor@test.arqive.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test Auditor",
        role="auditor",
        is_active=True,
    )
    db_session.add(u)
    await db_session.commit()
    return u
