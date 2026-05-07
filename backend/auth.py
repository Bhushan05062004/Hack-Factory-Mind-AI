"""
Factory Mind AI — JWT Authentication & RBAC
HS256-signed tokens with 8-hour expiry.
Roles: user, operator, quality.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

JWT_SECRET: str = os.getenv("JWT_SECRET", "supersecret")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_HOURS: int = 8

security = HTTPBearer()

VALID_ROLES = {"user", "operator", "quality"}


def create_access_token(user_id: int, role: str, name: str = "") -> str:
    """
    Create a JWT with sub=user_id, role=role, 8-hour expiry.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")

    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {
        "sub": str(user_id),
        "role": role,
        "name": name,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT. Returns {id: int, role: str, name: str}.
    Raises HTTPException on failure.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub", 0))
        role = payload.get("role", "")
        name = payload.get("name", "")
        if not user_id or role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims.",
            )
        return {"id": user_id, "role": role, "name": name}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
        )


async def jwt_required(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    FastAPI dependency — extracts and validates Bearer token.
    Returns dict: {id: int, role: str, name: str}.
    """
    return decode_token(credentials.credentials)


def require_role(*allowed_roles: str):
    """
    Factory for role-based access.
    Usage:  Depends(require_role("operator", "quality"))
    """
    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> dict:
        user = decode_token(credentials.credentials)
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user['role']}' is not permitted. Required: {allowed_roles}",
            )
        return user
    return _check
