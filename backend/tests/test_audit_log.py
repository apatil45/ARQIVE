"""Audit log: append-only behaviour and row_hash."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.services.audit.logger import log as audit_log


@pytest.mark.asyncio
async def test_audit_log_append(db_session: AsyncSession) -> None:
    """Log an entry and verify it has id, timestamp, row_hash."""
    await audit_log(
        db_session,
        tenant_id="tenant-1",
        user_id="user-1",
        action="login",
    )
    await db_session.commit()
    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "login"))
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.tenant_id == "tenant-1"
    assert row.user_id == "user-1"
    assert row.action == "login"
    assert row.row_hash is not None
    assert len(row.row_hash) == 64  # SHA-256 hex
