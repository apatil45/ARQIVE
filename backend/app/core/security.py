"""
JWT encode/decode and bcrypt password hashing. Tenant ID from JWT only.
Access: 60 min. Refresh: 7 days, httpOnly cookie.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

# Bcrypt for passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Revoked refresh token JTIs (in-memory; use Redis in prod for multi-instance)
_revoked_refresh_jtis: set[str] = set()


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    user_id: str,
    tenant_id: str,
    role: str,
    email: str,
) -> str:
    settings = get_settings()
    expire = _now_utc() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "email": email,
        "exp": expire,
        "iat": _now_utc(),
        "type": "access",
    }
    return jwt.encode(
        payload,
        settings.APP_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: str, tenant_id: str) -> tuple[str, str]:
    """Returns (token, jti). Store jti to allow revocation."""
    settings = get_settings()
    expire = _now_utc() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": expire,
        "iat": _now_utc(),
        "type": "refresh",
        "jti": jti,
    }
    token = jwt.encode(
        payload,
        settings.APP_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, jti


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Returns payload if valid; None otherwise. Use for dependency."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.APP_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> dict[str, Any] | None:
    """Returns payload if valid and not revoked; None otherwise."""
    payload = _decode_refresh_token_raw(token)
    if not payload:
        return None
    jti = payload.get("jti")
    if jti and jti in _revoked_refresh_jtis:
        return None
    return payload


def _decode_refresh_token_raw(token: str) -> dict[str, Any] | None:
    """Decode refresh token without checking revocation (for logout to get jti)."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.APP_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None


def revoke_refresh_token(jti: str) -> None:
    _revoked_refresh_jtis.add(jti)
