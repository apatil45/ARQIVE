"""
Query API: POST /api/query (JSON), GET /api/query/stream (SSE), GET /api/query/history.
Rate limit 60/min per user on query*. Tenant from JWT only.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.db.models import Document
from app.dependencies import DbSession, CurrentUserPayload
from app.services.retrieval.semantic import semantic_search
from app.services.retrieval.structured import structured_search
from app.services.retrieval.reranker import reciprocal_rank_fusion
from app.services.retrieval.prompt import SYSTEM_PROMPT, build_context, build_messages
from app.services.llm.client import stream_completion
from app.services.llm.confidence import compute_confidence, confidence_label
from app.services.llm.queue import enqueue, dequeue, wait_turn
from app.services.audit.logger import log as audit_log

router = APIRouter(prefix="/api/query", tags=["query"])


async def _allowed_document_ids(session: DbSession, tenant_id: str, role: str, user_id: str) -> list[str]:
    result = await session.execute(
        select(Document).where(
            Document.tenant_id == tenant_id,
            Document.status == "indexed",
        )
    )
    docs = result.scalars().all()
    return [
        d.id
        for d in docs
        if role in (d.allowed_roles or []) or (d.allowed_user_ids and user_id in d.allowed_user_ids)
    ]


def _parse_json_from_stream(text: str) -> dict | None:
    try:
        # Find first { ... } block
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
        return None
    except Exception:
        return None


@router.post("")
async def query(
    request: Request,
    body: dict,
    session: DbSession,
    payload: CurrentUserPayload,
) -> dict:
    """Synchronous query (full JSON response). Rate limited."""
    q = (body.get("query") or "").strip()
    if not q:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query required")
    tenant_id = payload["tenant_id"]
    user_id = payload["sub"]
    role = payload.get("role") or "viewer"
    allowed = await _allowed_document_ids(session, tenant_id, role, user_id)
    if not allowed:
        return {
            "answer": "No indexed documents available for your access.",
            "citations": [],
            "confidence": "LOW",
            "confidence_reason": "No documents to search.",
            "unanswered_aspects": None,
        }
    semantic = semantic_search(tenant_id, q, allowed, top_k=10)
    structured = await structured_search(session, tenant_id, allowed, limit=10)
    top = reciprocal_rank_fusion(semantic, structured, top_n=5)
    if not top:
        return {
            "answer": "The provided documents do not contain sufficient information to answer this.",
            "citations": [],
            "confidence": "LOW",
            "confidence_reason": "No relevant chunks found.",
            "unanswered_aspects": q,
        }
    context = build_context(top)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + build_messages(q, context)
    full_text = ""
    async for token in stream_completion(messages):
        full_text += token
    parsed = _parse_json_from_stream(full_text)
    if parsed:
        scores = [c.get("score", 0) for c in top]
        cov = 1.0 if parsed.get("citations") else 0.0
        score, reason = compute_confidence(scores, parsed.get("confidence"), cov)
        return {
            "answer": parsed.get("answer", full_text),
            "citations": parsed.get("citations", []),
            "confidence": confidence_label(score),
            "confidence_reason": reason,
            "unanswered_aspects": parsed.get("unanswered_aspects"),
        }
    return {"answer": full_text, "citations": [], "confidence": "LOW", "confidence_reason": "Parse failed.", "unanswered_aspects": None}


async def _stream_events(
    request: Request,
    q: str,
    session: DbSession,
    payload: dict,
) -> AsyncGenerator[str, None]:
    tenant_id = payload["tenant_id"]
    user_id = payload["sub"]
    role = payload.get("role") or "viewer"
    request_id = f"{user_id}-{time.time()}"
    try:
        queued = await enqueue(request_id)
        if queued:
            pos, eta = queued
            yield f"data: {json.dumps({'type': 'queue', 'position': pos, 'eta_seconds': eta})}\n\n"
        await wait_turn(request_id)
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        await dequeue(request_id)
        return
    try:
        yield f"data: {json.dumps({'type': 'status', 'message': 'Searching documents...'})}\n\n"
        allowed = await _allowed_document_ids(session, tenant_id, role, user_id)
        if not allowed:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No documents available.'})}\n\n"
            await dequeue(request_id)
            return
        semantic = semantic_search(tenant_id, q, allowed, top_k=10)
        structured = await structured_search(session, tenant_id, allowed, limit=10)
        top = reciprocal_rank_fusion(semantic, structured, top_n=5)
        yield f"data: {json.dumps({'type': 'status', 'message': 'Generating answer...'})}\n\n"
        if not top:
            yield f"data: {json.dumps({'type': 'token', 'content': 'The provided documents do not contain sufficient information to answer this.'})}\n\n"
            yield f"data: {json.dumps({'type': 'citations', 'data': []})}\n\n"
            yield f"data: {json.dumps({'type': 'confidence', 'data': {'confidence': 'LOW', 'reason': 'No chunks.'}})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            await dequeue(request_id)
            return
        context = build_context(top)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + build_messages(q, context)
        full_text = ""
        async for token in stream_completion(messages):
            full_text += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        parsed = _parse_json_from_stream(full_text)
        citations = parsed.get("citations", []) if parsed else []
        scores = [c.get("score", 0) for c in top]
        cov = len(citations) / len(top) if top else 0
        score, reason = compute_confidence(scores, parsed.get("confidence") if parsed else None, cov)
        yield f"data: {json.dumps({'type': 'citations', 'data': citations})}\n\n"
        yield f"data: {json.dumps({'type': 'confidence', 'data': {'confidence': confidence_label(score), 'reason': reason}})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        # Audit after stream
        await audit_log(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            action="query",
            query_text=q,
            document_ids_accessed=list({c.get("document_id") for c in top if c.get("document_id")}),
            chunk_ids_accessed=[c.get("id") for c in top if c.get("id")],
            prompt_hash=hashlib.sha256((SYSTEM_PROMPT + context).encode()).hexdigest()[:64],
            response_hash=hashlib.sha256(full_text.encode()).hexdigest()[:64],
            confidence_score=score,
            ip_address=request.client.host if request.client else None,
        )
        await session.commit()
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    finally:
        await dequeue(request_id)


@router.get("/stream")
async def query_stream(
    request: Request,
    q: str,
    session: DbSession,
    payload: CurrentUserPayload,
):
    """SSE stream: status -> tokens -> citations -> confidence -> done."""
    if not (q or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query q required")
    return StreamingResponse(
        _stream_events(request, q.strip(), session, payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/history")
async def query_history(
    session: DbSession,
    payload: CurrentUserPayload,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Paginated query history from audit log (query action)."""
    from app.db.models.audit_log import AuditLog
    tenant_id = payload["tenant_id"]
    user_id = payload["sub"]
    result = await session.execute(
        select(AuditLog)
        .where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.user_id == user_id,
            AuditLog.action == "query",
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()
    return {
        "items": [
            {
                "timestamp": r.timestamp.isoformat(),
                "query_text": r.query_text,
                "confidence_score": r.confidence_score,
            }
            for r in rows
        ],
        "limit": limit,
        "offset": offset,
    }
