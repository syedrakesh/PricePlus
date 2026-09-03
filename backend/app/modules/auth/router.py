"""
FastAPI auth router — thin HTTP layer only.

Router handlers:
- Validate input (via Pydantic schemas)
- Call service layer
- Return HTTP responses
- Never contain business logic or DB queries directly
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.modules.auth.service import (
    AuthError,
    get_user_by_id,
    login_user,
    refresh_tokens,
    register_user,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _handle_auth_error(e: AuthError) -> None:
    """Convert domain AuthError to FastAPI HTTPException."""
    raise HTTPException(status_code=e.status_code, detail=str(e))


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Register a new user account.

    Returns access + refresh tokens on success.
    Returns 409 if email is already registered.
    """
    try:
        return await register_user(db, data)
    except AuthError as e:
        _handle_auth_error(e)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate with email + password.

    Returns access + refresh tokens.
    Returns 401 for invalid credentials (same message for email/password
    to prevent user enumeration).
    """
    try:
        return await login_user(db, data)
    except AuthError as e:
        _handle_auth_error(e)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    """
    try:
        return await refresh_tokens(db, data.refresh_token)
    except AuthError as e:
        _handle_auth_error(e)


@router.get("/me", response_model=UserResponse)
async def me(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> UserResponse:
    """
    Return the currently authenticated user's profile.
    Requires a valid Bearer token in the Authorization header.
    """
    try:
        user = await get_user_by_id(db, user_id)
    except AuthError as e:
        _handle_auth_error(e)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )
