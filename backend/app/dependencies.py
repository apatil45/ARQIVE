"""
Shared FastAPI dependencies: DB session, current user from DB.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.core.rbac import get_current_user_payload

# Re-export for route use
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUserPayload = Annotated[dict, Depends(get_current_user_payload)]


async def get_current_user(
    session: AsyncSession,
    payload: dict,
) -> User | None:
    """Load User from DB by payload['sub']. Returns None if not found or inactive."""
    user_id = payload.get("sub")
    if not user_id:
        return None
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    return user
