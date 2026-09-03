"""
Entitlement service — reads plan limits and enforces them.

Design decisions:
- Plans are stored in the DB (not hard-coded) so they can change without deploys
- For MVP: if a user has no subscription, they get 'free' plan limits
- Entitlement checks are done in service layer (never in routers)
- free plan defaults are conservative — upgrade prompts should show
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Free tier limits — used when user has no active subscription
# These MUST match the seeded 'free' plan in the DB
FREE_PLAN_MAX_STORES = 2
FREE_PLAN_MAX_TRACKED_PRODUCTS = 10


class EntitlementError(Exception):
    """Raised when a user has exceeded their plan limits."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status_code = 403


async def get_max_stores(db: AsyncSession, user_id: uuid.UUID) -> int:
    """
    Return the maximum number of competitor stores the user can add.
    Falls back to FREE_PLAN_MAX_STORES if no subscription found.
    """
    # Import here to avoid circular imports at module level
    from app.modules.billing.models import Plan, Subscription

    result = await db.execute(
        select(Plan.max_stores)
        .join(Subscription, Subscription.plan_id == Plan.id)
        .where(Subscription.user_id == user_id)
        .where(Subscription.status == "active")
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row is not None else FREE_PLAN_MAX_STORES


async def check_store_limit(
    db: AsyncSession,
    user_id: uuid.UUID,
    current_count: int,
) -> None:
    """
    Raise EntitlementError if adding another store would exceed the plan limit.
    """
    max_stores = await get_max_stores(db, user_id)
    if current_count >= max_stores:
        raise EntitlementError(
            f"Your plan allows a maximum of {max_stores} competitor store(s). "
            "Please upgrade to add more."
        )


async def get_max_tracked_products(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Return the maximum tracked products the user can have."""
    from app.modules.billing.models import Plan, Subscription

    result = await db.execute(
        select(Plan.max_tracked_products)
        .join(Subscription, Subscription.plan_id == Plan.id)
        .where(Subscription.user_id == user_id)
        .where(Subscription.status == "active")
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row is not None else FREE_PLAN_MAX_TRACKED_PRODUCTS
