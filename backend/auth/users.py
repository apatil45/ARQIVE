"""
User management and database operations
"""
from pydantic import BaseModel
from typing import Optional
from enum import Enum


class Role(str, Enum):
    """User roles"""
    ADMIN = "admin"
    AUDITOR = "auditor"
    VIEWER = "viewer"


class User(BaseModel):
    """User model"""
    username: str
    role: Role
    email: Optional[str] = None
    full_name: Optional[str] = None
    
    class Config:
        use_enum_values = True


class UserCreate(BaseModel):
    """User creation model"""
    username: str
    password: str
    role: Role
    email: Optional[str] = None
    full_name: Optional[str] = None


