"""
RBAC: FastAPI dependencies for current user and role checks. Tenant ID from JWT only.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token

# Bearer token for Authorization header (access token)
security = HTTPBearer(auto_error=False)


def get_current_user_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict:
    """Extract and validate access token; return payload (sub, tenant_id, role, email)."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def require_role(required: str):
    """
    Dependency factory: require at least this role (viewer < auditor < admin).
    Use: Depends(require_role("auditor"))
    """

    role_order = ["viewer", "auditor", "admin"]

    def _check(
        payload: Annotated[dict, Depends(get_current_user_payload)],
    ) -> dict:
        role = payload.get("role") or "viewer"
        if role_order.index(role) < role_order.index(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role {required} or higher",
            )
        return payload

    return _check


# Convenience dependencies
CurrentUserPayload = Annotated[dict, Depends(get_current_user_payload)]
RequireAuditor = Annotated[dict, Depends(require_role("auditor"))]
RequireAdmin = Annotated[dict, Depends(require_role("admin"))]
