"""
Role-based access control (RBAC)
"""
from functools import wraps
from fastapi import Depends, HTTPException, status
from typing import Callable

from auth.users import User, Role
from auth.jwt_handler import get_current_user


def require_role(required_role: Role):
    """
    Dependency factory for role-based access control
    Usage: @app.get("/admin", dependencies=[Depends(require_role(Role.ADMIN))])
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role and current_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role.value} role"
            )
        return current_user
    return role_checker


def has_permission(user: User, required_role: Role) -> bool:
    """
    Check if user has required permission
    Admins have all permissions
    """
    return user.role == Role.ADMIN or user.role == required_role


