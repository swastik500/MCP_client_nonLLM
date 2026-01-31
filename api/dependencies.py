"""
FastAPI dependencies.

Provides:
- Authentication dependencies
- Database session dependencies
- User context dependencies
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.auth import decode_token, TokenData
from database.connection import get_session
from database.models import User

# Security scheme
security = HTTPBearer(auto_error=False)


async def get_current_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[TokenData]:
    """
    Extract and validate token from request.
    
    Returns TokenData if valid, None otherwise.
    Does not raise exception for missing token.
    """
    if credentials is None:
        return None
    
    token_data = decode_token(credentials.credentials)
    return token_data


async def get_current_user(
    token_data: Optional[TokenData] = Depends(get_current_token),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """
    Get current user from token.
    
    Returns User if authenticated, None otherwise.
    Does not raise exception for unauthenticated requests.
    """
    if token_data is None:
        return None
    
    try:
        result = await session.execute(
            select(User).where(User.id == token_data.user_id)
        )
        user = result.scalar_one_or_none()
        
        if user and user.is_active:
            return user
        return None
        
    except Exception:
        return None


async def require_authenticated(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """
    Require authenticated user.
    
    Raises 401 if not authenticated.
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    user: User = Depends(require_authenticated),
) -> User:
    """
    Require admin user.
    
    Raises 403 if not admin.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def get_user_context(user: Optional[User] = Depends(get_current_user)) -> dict:
    """
    Get user context for rule evaluation.
    
    Returns context dict even for unauthenticated users.
    """
    if user is None:
        return {
            "user_id": None,
            "username": "anonymous",
            "role": "guest",
            "permissions": [],
        }
    
    return {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role,
        "permissions": user.permissions or [],
    }
