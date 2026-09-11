"""
FastAPI auth router — thin HTTP layer only.

Router handlers:
- Validate input (via Pydantic schemas)
- Call service layer
- Return HTTP responses
- Never contain business logic or DB queries directly
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user_id, get_current_superuser_id
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    AdminUserResponse,
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


# ─── Superadmin endpoints ─────────────────────────────────────────────────────

@router.get("/admin/users", response_model=list[AdminUserResponse])
async def admin_list_users(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> list[AdminUserResponse]:
    """
    List all users with their current subscription plan (Superadmin only).
    Ordered by registration date descending (newest first).
    """
    from app.modules.billing.models import Plan, Subscription

    # Join users with their latest active subscription + plan
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = list(result.scalars().all())

    # Batch load subscriptions for all users
    user_ids = [u.id for u in users]
    if user_ids:
        sub_result = await db.execute(
            select(Subscription, Plan)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.user_id.in_(user_ids))
            .order_by(Subscription.created_at.desc())
        )
        rows = sub_result.all()
    else:
        rows = []

    # Build a map of user_id -> (sub, plan) — keep only latest
    sub_map: dict[str, tuple] = {}
    for sub, plan in rows:
        uid = str(sub.user_id)
        if uid not in sub_map:
            sub_map[uid] = (sub, plan)

    response = []
    for user in users:
        uid = str(user.id)
        sub_info = sub_map.get(uid)
        plan_name = sub_info[1].name if sub_info else "No Plan"
        plan_slug = sub_info[1].slug if sub_info else None
        sub_status = sub_info[0].status if sub_info else "none"
        plan_id = str(sub_info[1].id) if sub_info else None
        response.append(AdminUserResponse(
            id=uid,
            email=user.email,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at.isoformat(),
            plan_name=plan_name,
            plan_slug=plan_slug,
            plan_id=plan_id,
            subscription_status=sub_status,
        ))

    return response


@router.patch("/admin/users/{target_user_id}/status", response_model=UserResponse)
async def admin_toggle_user_status(
    target_user_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> UserResponse:
    """Toggle a user's active/inactive status (Superadmin only)."""
    try:
        user_uuid = uuid.UUID(target_user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found") from None

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot deactivate a superuser")

    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)

    logger.info("Admin toggled user %s active=%s", user.email, user.is_active)
    return UserResponse(id=str(user.id), email=user.email, is_active=user.is_active, created_at=user.created_at.isoformat())
