"""
Auth request/response schemas (Pydantic v2).
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    email: str
    full_name: str
    role: str


class MeResponse(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    full_name: str
    role: str
