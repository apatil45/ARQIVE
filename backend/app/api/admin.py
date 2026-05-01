"""
Admin API: users (CRUD), audit log (paginated), stats, queue status. Admin only.
"""
from __future__ import annotations


from fastapi import APIRouter, Query
from sqlalchemy import select, func

from app.db.models import User, AuditLog
from app.dependencies import DbSession
from app.core.rbac import RequireAdmin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    session: DbSession,
    payload: RequireAdmin,
) -> list[dict]:
    """List tenant users. Tenant from JWT."""
    tenant_id = payload["tenant_id"]
    result = await session.execute(
        select(User).where(User.tenant_id == tenant_id).order_by(User.email)
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        }
        for u in users
    ]


@router.get("/audit-log")
async def get_audit_log(
    session: DbSession,
    payload: RequireAdmin,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = None,
) -> dict:
    """Paginated audit log. Filter by action optional."""
    tenant_id = payload["tenant_id"]
    q = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    if action:
        q = q.where(AuditLog.action == action)
    count_q = select(func.count()).select_from(AuditLog).where(AuditLog.tenant_id == tenant_id)
    if action:
        count_q = count_q.where(AuditLog.action == action)
    total_result = await session.execute(count_q)
    total_count = total_result.scalar() or 0
    q = q.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
    result = await session.execute(q)
    rows = result.scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "action": r.action,
                "timestamp": r.timestamp.isoformat(),
                "query_text": r.query_text,
                "confidence_score": r.confidence_score,
                "row_hash": r.row_hash,
            }
            for r in rows
        ],
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats")
async def get_stats(
    session: DbSession,
    payload: RequireAdmin,
) -> dict:
    """Aggregated usage metrics for tenant."""
    tenant_id = payload["tenant_id"]
    from app.db.models import Document
    docs = await session.execute(
        select(func.count()).select_from(Document).where(
            Document.tenant_id == tenant_id,
            Document.status == "indexed",
        )
    )
    queries = await session.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.action == "query",
        )
    )
    return {
        "indexed_documents": docs.scalar() or 0,
        "total_queries": queries.scalar() or 0,
    }


@router.get("/queue")
async def get_queue(
    payload: RequireAdmin,
) -> dict:
    """Current LLM queue status."""
    from app.services.llm.queue import _queue
    depth = len(_queue)
    return {"queue_depth": depth, "position": depth}
