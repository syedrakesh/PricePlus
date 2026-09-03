"""
Security utilities — password hashing and JWT token operations.

Design decisions:
- bcrypt directly (not passlib — passlib is unmaintained and incompatible with bcrypt >= 4.x)
- python-jose for JWT (HS256)
- Access tokens: short-lived (30 min default)
- Refresh tokens: long-lived (30 days default)
- Token type claim prevents token confusion attacks
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

# ── Password utilities ────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password with bcrypt.
    Never store the plain password.

    Note: bcrypt truncates at 72 bytes internally. For passwords longer than
    72 bytes, behaviour is defined by bcrypt spec — we do NOT pre-hash
    (which can introduce its own vulnerabilities). Instead we enforce a
    128-char max in the schema.
    """
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a bcrypt hash.
    Returns False (never raises) on mismatch or bad hash.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ── JWT utilities ─────────────────────────────────────────────────────────────

def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    """Internal: create a signed JWT with expiry."""
    settings = get_settings()
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + expires_delta
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    """Create a short-lived access token. Includes type='access' claim."""
    settings = get_settings()
    return _create_token(
        data={"sub": user_id, "type": "access"},
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token. Includes type='refresh' claim."""
    settings = get_settings()
    return _create_token(
        data={"sub": user_id, "type": "refresh"},
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days),
    )


def decode_access_token(token: str) -> str:
    """
    Decode and validate an access token.
    Returns user_id on success. Raises ValueError on any failure.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

    if payload.get("type") != "access":
        raise ValueError("Invalid token type")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise ValueError("Token missing subject claim")

    return user_id


def decode_refresh_token(token: str) -> str:
    """
    Decode and validate a refresh token.
    Returns user_id on success. Raises ValueError on any failure.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

    if payload.get("type") != "refresh":
        raise ValueError("Invalid token type")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise ValueError("Token missing subject claim")

    return user_id
