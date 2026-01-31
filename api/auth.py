"""
Authentication utilities - JWT token handling.

Provides:
- Password hashing
- JWT token creation/validation
- User authentication

STRICT CONSTRAINTS:
- No business logic
- Stateless token handling
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass

from jose import JWTError, jwt
from passlib.context import CryptContext

from config.settings import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class TokenData:
    """Decoded token data."""
    user_id: str
    username: str
    role: str
    exp: datetime


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: User's UUID
        username: Username
        role: User's role
        expires_delta: Optional custom expiry
        
    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.jwt.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    }
    
    return jwt.encode(
        payload,
        settings.jwt.JWT_SECRET_KEY,
        algorithm=settings.jwt.JWT_ALGORITHM
    )


def create_refresh_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        user_id: User's UUID
        expires_delta: Optional custom expiry
        
    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.jwt.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
    }
    
    return jwt.encode(
        payload,
        settings.jwt.JWT_SECRET_KEY,
        algorithm=settings.jwt.JWT_ALGORITHM
    )


def decode_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        TokenData if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt.JWT_SECRET_KEY,
            algorithms=[settings.jwt.JWT_ALGORITHM]
        )
        
        user_id = payload.get("sub")
        username = payload.get("username", "")
        role = payload.get("role", "user")
        exp = datetime.fromtimestamp(payload.get("exp", 0))
        
        if user_id is None:
            return None
        
        return TokenData(
            user_id=user_id,
            username=username,
            role=role,
            exp=exp,
        )
        
    except JWTError:
        return None


def validate_token(token: str) -> bool:
    """
    Check if a token is valid (not expired, properly signed).
    
    Args:
        token: JWT token string
        
    Returns:
        True if valid
    """
    token_data = decode_token(token)
    if token_data is None:
        return False
    
    # Check expiration
    if token_data.exp < datetime.utcnow():
        return False
    
    return True
