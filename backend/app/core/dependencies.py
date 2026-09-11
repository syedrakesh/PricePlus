"""
Shared FastAPI dependencies.

get_current_user_id: extracts and validates the Bearer JWT from
Authorization header. Used by any endpoint requiring authentication.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """
    FastAPI dependency: extract user_id from Bearer JWT.

    - Returns user_id string on success
    - Raises HTTP 401 if token is missing, invalid, or expired
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = decode_access_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    return user_id


async def get_current_superuser_id(
    user_id_str: str = Depends(get_current_user_id),
    db: "AsyncSession" = Depends(get_db),
) -> str:
    """
    FastAPI dependency: verify user has superuser privileges.
    """
    import uuid
    from sqlalchemy import select
    from app.modules.auth.models import User

    user_id = uuid.UUID(user_id_str)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privileges required.",
        )

    return user_id_str

