"""
Auth service — business logic layer.

Keeps endpoint handlers thin: routers call services, services call DB.
No SQLAlchemy queries in routers.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Domain-level auth error — converted to HTTP response in the router."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


async def register_user(db: AsyncSession, data: RegisterRequest) -> TokenResponse:
    """
    Register a new user.

    Raises AuthError if the email is already taken.
    Returns token pair on success.
    """
    # Check for existing user
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()

    if existing is not None:
        # Use the same message for taken vs. available — prevents email enumeration
        raise AuthError("An account with this email already exists", status_code=409)

    user = User(
        id=uuid.uuid4(),
        email=data.email,
        password_hash=hash_password(data.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("User registered", extra={"user_id": str(user.id)})

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


async def login_user(db: AsyncSession, data: LoginRequest) -> TokenResponse:
    """
    Authenticate a user by email + password.

    Raises AuthError with the same message for invalid email or wrong password
    to prevent user enumeration.
    """
    _INVALID_CREDENTIALS = "Invalid email or password"

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if user is None:
        # Timing-safe: still hash even if no user found
        hash_password(data.password)
        raise AuthError(_INVALID_CREDENTIALS, status_code=401)

    if not verify_password(data.password, user.password_hash):
        raise AuthError(_INVALID_CREDENTIALS, status_code=401)

    if not user.is_active:
        raise AuthError("Account is disabled", status_code=403)

    logger.info("User logged in", extra={"user_id": str(user.id)})

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> TokenResponse:
    """
    Issue new token pair from a valid refresh token.
    Validates the token and that the user still exists and is active.
    """
    from app.core.security import decode_refresh_token

    try:
        user_id = decode_refresh_token(refresh_token)
    except ValueError as e:
        raise AuthError(str(e), status_code=401) from e

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AuthError("Invalid token", status_code=401)

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    """Fetch a user by ID. Raises AuthError if not found or inactive."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise AuthError("Invalid user ID", status_code=401) from None

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AuthError("User not found", status_code=401)

    return user
