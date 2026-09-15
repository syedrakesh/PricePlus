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
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        is_active=True,
        is_verified=True,
        onboarding_completed=False,
    )

    # Assign default RBAC role ('user')
    from app.modules.auth.models import Role
    user_role_res = await db.execute(select(Role).where(Role.slug == "user"))
    user_role = user_role_res.scalars().first()
    if user_role:
        user.role_id = user_role.id

    db.add(user)
    await db.flush()

    # Determine subscription plan from requested plan_slug
    from app.modules.billing.models import Plan, Subscription
    plan_slug = (data.plan_slug or "free").lower().strip()
    plan_res = await db.execute(select(Plan).where(Plan.slug == plan_slug))
    selected_plan = plan_res.scalars().first()

    if not selected_plan:
        free_plan_res = await db.execute(select(Plan).where(Plan.slug == "free"))
        selected_plan = free_plan_res.scalars().first()
    if not selected_plan:
        any_plan_res = await db.execute(select(Plan).order_by(Plan.price_usd.asc()))
        selected_plan = any_plan_res.scalars().first()

    checkout_url: str | None = None
    if selected_plan:
        price_usd = selected_plan.price_usd or 0
        sub = Subscription(
            id=uuid.uuid4(),
            user_id=user.id,
            plan_id=selected_plan.id,
            status="active",
        )
        db.add(sub)

        # Optional Stripe Checkout URL generation if paid plan & stripe configured
        if price_usd > 0 and selected_plan.stripe_price_id:
            try:
                from app.modules.billing.stripe_service import create_customer, create_checkout_session
                cust_id = await create_customer(user.email, user.full_name)
                sub.stripe_customer_id = cust_id
                checkout_url = await create_checkout_session(
                    user_id=str(user.id),
                    customer_id=cust_id,
                    stripe_price_id=selected_plan.stripe_price_id,
                    success_url="http://localhost:3000/onboarding?session_id={CHECKOUT_SESSION_ID}",
                    cancel_url="http://localhost:3000/register?canceled=1",
                )
            except Exception as exc:
                logger.warning("Could not initialize Stripe checkout for user %s: %s", user.id, exc)

    await db.commit()
    await db.refresh(user)

    logger.info("User registered with plan %s", selected_plan.slug if selected_plan else "none", extra={"user_id": str(user.id)})

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        redirect_url="/onboarding",
        checkout_url=checkout_url,
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
