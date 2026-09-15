"""
Shared FastAPI dependencies.

get_current_user_id: extracts and validates the Bearer JWT from Authorization header.
get_current_active_user: returns full User model instance.
require_permission: dependency factory enforcing required permission code.
get_current_superuser_id: verifies user has access_admin permission or superuser flag.
"""

import uuid
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_access_token
from app.modules.auth.models import Permission, User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """
    FastAPI dependency: extract user_id from Bearer JWT.
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


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str | None:
    """
    FastAPI dependency: extract user_id from Bearer JWT if provided, or return None.
    """
    if credentials is None:
        return None

    try:
        return decode_access_token(credentials.credentials)
    except ValueError:
        return None


async def get_current_active_user(
    user_id_str: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: load and return current active User ORM model.
    """
    user_id = uuid.UUID(user_id_str)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


async def get_effective_user_permissions(user: User, db: AsyncSession) -> set[str]:
    """
    Helper function: resolve user's effective permissions (role permissions + custom_permissions).
    If superuser, returns all registered permission codes.
    """
    if user.is_superuser:
        perm_res = await db.execute(select(Permission.code))
        return set(perm_res.scalars().all())

    perms = set(user.custom_permissions or [])
    if user.role and user.role.role_permissions:
        for rp in user.role.role_permissions:
            perms.add(rp.permission_code)

    return perms


def require_permission(permission_code: str) -> Callable:
    """
    FastAPI dependency factory: enforce that the current user has the specified permission code.
    Usage: Depends(require_permission("manage_stores"))
    """
    async def permission_checker(
        user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        user_perms = await get_effective_user_permissions(user, db)
        if permission_code not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission_code}' access required.",
            )
        return user

    return permission_checker


async def get_current_superuser_id(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> str:
    """
    FastAPI dependency: verify user has superuser privileges or access_admin permission.
    """
    user_perms = await get_effective_user_permissions(user, db)
    if not user.is_superuser and "access_admin" not in user_perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privileges or 'access_admin' permission required.",
        )

    return str(user.id)
