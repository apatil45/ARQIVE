"""
Auth API: login (JWT + httpOnly refresh cookie), refresh, logout, me.
Tenant ID from JWT only — never from request body or query.
"""
from __future__ import annotations


from fastapi import APIRouter, HTTPException, status, Response, Request
from sqlalchemy import select

from app.db.models import User
from app.dependencies import DbSession, CurrentUserPayload
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    revoke_refresh_token,
)
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.services.audit.logger import log as audit_log

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Cookie name and options for refresh token
REFRESH_COOKIE = "refresh_token"
COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days in seconds


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
    session: DbSession,
) -> LoginResponse:
    """Authenticate; return access token and set httpOnly refresh cookie."""
    result = await session.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    access = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        email=user.email,
    )
    refresh_token, jti = create_refresh_token(user.id, user.tenant_id)
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/api/auth",
    )
    await audit_log(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="login",
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    return LoginResponse(
        access_token=access,
        token_type="bearer",
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    request: Request,
    response: Response,
    session: DbSession,
) -> LoginResponse:
    """Issue new access token from httpOnly refresh cookie. Tenant ID from JWT only."""
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )
    payload = decode_refresh_token(token)
    if not payload:
        response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if not user_id or not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or user.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    access = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        email=user.email,
    )
    return LoginResponse(
        access_token=access,
        token_type="bearer",
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: DbSession,
) -> dict[str, str]:
    """Invalidate refresh token and clear httpOnly cookie."""
    from app.core.security import _decode_refresh_token_raw
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        payload = _decode_refresh_token_raw(token)
        if payload and payload.get("jti"):
            revoke_refresh_token(payload["jti"])
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("sub")
            if tenant_id and user_id:
                await audit_log(
                    session,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="logout",
                    ip_address=request.client.host if request.client else None,
                )
                await session.commit()
        response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    return {"message": "Logged out"}


@router.get("/me", response_model=MeResponse)
async def me(
    session: DbSession,
    payload: CurrentUserPayload,
) -> MeResponse:
    """Current user from JWT. Tenant ID from token only."""
    from app.dependencies import get_current_user
    user = await get_current_user(session, payload)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return MeResponse(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )

