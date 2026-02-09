"""
JWT token handling
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, TYPE_CHECKING
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from auth.users import User

if TYPE_CHECKING:
    from db.sqlite import SQLiteDB

security = HTTPBearer()


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict:
    """
    Verify and decode JWT token
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Global sqlite_db instance (will be set from main.py)
_sqlite_db_instance: Optional['SQLiteDB'] = None

def set_sqlite_db_instance(db_instance: 'SQLiteDB'):
    """Set the global SQLiteDB instance"""
    global _sqlite_db_instance
    _sqlite_db_instance = db_instance

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Get current authenticated user from JWT token
    """
    token = credentials.credentials
    payload = verify_token(token)
    username: str = payload.get("sub")
    role: str = payload.get("role")
    
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    # Verify user still exists in database (security: handle deleted users)
    # Use global instance if available, otherwise create new one (fallback)
    if _sqlite_db_instance is None:
        from db.sqlite import SQLiteDB
        sqlite_db = SQLiteDB()
    else:
        sqlite_db = _sqlite_db_instance
    
    db_user = await sqlite_db.get_user_by_username(username)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )
    # Use role from database, not token (prevents role escalation)
    return User(username=username, role=db_user.role)


async def verify_token_endpoint(token: str) -> Dict:
    """
    Verify a JWT token and return user information
    Used by frontend to validate tokens
    """
    try:
        payload = verify_token(token)
        username: str = payload.get("sub")
        role: str = payload.get("role")
        
        if username is None:
            return {
                "valid": False,
                "error": "Invalid token: missing username"
            }
        
        # Verify user still exists
        if _sqlite_db_instance is None:
            from db.sqlite import SQLiteDB
            sqlite_db = SQLiteDB()
        else:
            sqlite_db = _sqlite_db_instance
        
        db_user = await sqlite_db.get_user_by_username(username)
        if not db_user:
            return {
                "valid": False,
                "error": "User no longer exists"
            }
        
        # Check if token is expired (payload already verified by verify_token)
        from datetime import datetime
        exp = payload.get("exp")
        if exp:
            exp_datetime = datetime.fromtimestamp(exp)
            if datetime.utcnow() > exp_datetime:
                return {
                    "valid": False,
                    "error": "Token expired",
                    "expired_at": exp_datetime.isoformat()
                }
        
        return {
            "valid": True,
            "username": username,
            "role": db_user.role.value if hasattr(db_user.role, 'value') else str(db_user.role),
            "expires_at": datetime.fromtimestamp(exp).isoformat() if exp else None
        }
    except HTTPException as e:
        return {
            "valid": False,
            "error": e.detail
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Token verification failed: {str(e)}"
        }


