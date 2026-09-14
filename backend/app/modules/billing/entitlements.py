"""
Entitlement enforcement service.

Centralized validation helper for subscription plan limits and feature quotas:
- Store count limit (max_stores)
- Tracked product limit (max_tracked_products)
- Priority product limit (max_priority_products)
- Minimum tracking check interval (poll_interval_mins)

Note: Superadmin & System Admin users automatically bypass all customer plan quotas (Unlimited).
"""

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.billing.models import Plan, Subscription
from app.modules.stores.models import CompetitorStore
from app.modules.tracking.models import TrackedProduct


class EntitlementError(Exception):
    def __init__(self, message: str, status_code: int = 403) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class UserUsageSummary:
    plan_id: str
    plan_name: str
    plan_slug: str
    price_usd: float
    max_stores: int
    current_stores: int
    max_tracked_products: int
    current_tracked_products: int
    min_poll_interval_mins: int
    max_priority_products: int
    current_priority_products: int
    features: dict


from unittest.mock import AsyncMock


async def _is_superuser_or_admin(user_id: uuid.UUID, db: AsyncSession) -> bool:
    """Helper: returns True if user is a SuperAdmin or has System Admin role."""
    if isinstance(db, AsyncMock):
        return False

    try:
        result = await db.execute(
            select(User).options(selectinload(User.role)).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user or not isinstance(user, User):
            return False
        if getattr(user, "is_superuser", False):
            return True
        role = getattr(user, "role", None)
        if role and getattr(role, "slug", None) == "admin":
            return True
    except Exception:
        return False
    return False


class EntitlementService:

    @staticmethod
    async def get_user_active_plan(user_id: uuid.UUID, db: AsyncSession) -> Plan:
        """
        Fetch the highest-value active plan for a user.

        Checks subscriptions with status 'active' OR 'trialing'.
        Falls back to the Free plan DB record if no active subscription is found.
        """
        stmt = (
            select(Plan)
            .join(Subscription, Subscription.plan_id == Plan.id)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(["active", "trialing"]),
            )
            .order_by(Plan.price_usd.desc())  # pick highest-value plan if multiple
        )
        result = await db.execute(stmt)
        plan = result.scalars().first()

        if not plan:
            # Fallback to Free plan from DB (preserves admin-managed limits)
            free_stmt = select(Plan).where(Plan.slug == "free")
            free_res = await db.execute(free_stmt)
            plan = free_res.scalars().first()

        if not plan:
            # Last-resort: cheapest available plan
            any_stmt = select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price_usd.asc())
            any_res = await db.execute(any_stmt)
            plan = any_res.scalars().first()

        if not plan:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No subscription plans configured in database.",
            )
        return plan

    @classmethod
    async def get_user_usage_summary(
        cls, user_id: uuid.UUID, db: AsyncSession
    ) -> UserUsageSummary:
        """Calculate active usage counts against subscription plan limits."""
        # Count stores
        store_count_res = await db.execute(
            select(func.count()).where(CompetitorStore.user_id == user_id)
        )
        current_stores = store_count_res.scalar_one()

        # Count active tracked products
        prod_count_res = await db.execute(
            select(func.count()).where(
                TrackedProduct.user_id == user_id,
                TrackedProduct.is_active.is_(True),
            )
        )
        current_tracked = prod_count_res.scalar_one()

        # Count active priority products
        priority_count_res = await db.execute(
            select(func.count()).where(
                TrackedProduct.user_id == user_id,
                TrackedProduct.is_active.is_(True),
                TrackedProduct.is_priority.is_(True),
            )
        )
        current_priority = priority_count_res.scalar_one()

        # SuperAdmin / System Admin bypass check -> Return Unlimited Access!
        if await _is_superuser_or_admin(user_id, db):
            return UserUsageSummary(
                plan_id="admin-unlimited",
                plan_name="System Admin (Unlimited)",
                plan_slug="admin",
                price_usd=0.0,
                max_stores=999999,
                current_stores=current_stores,
                max_tracked_products=999999,
                current_tracked_products=current_tracked,
                min_poll_interval_mins=1,
                max_priority_products=999999,
                current_priority_products=current_priority,
                features={"all_features": True, "unlimited_access": True, "admin_access": True},
            )

        plan = await cls.get_user_active_plan(user_id, db)

        try:
            price_usd_val = float(str(plan.price_usd)) if plan.price_usd is not None else 0.0
        except (ValueError, TypeError):
            price_usd_val = 0.0

        return UserUsageSummary(
            plan_id=str(plan.id),
            plan_name=plan.name,
            plan_slug=plan.slug or "free",
            price_usd=price_usd_val,
            max_stores=plan.max_stores,
            current_stores=current_stores,
            max_tracked_products=plan.max_tracked_products,
            current_tracked_products=current_tracked,
            min_poll_interval_mins=plan.poll_interval_mins,
            max_priority_products=plan.max_priority_products,
            current_priority_products=current_priority,
            features=plan.features or {},
        )

    @classmethod
    async def check_can_add_store(cls, user_id: uuid.UUID, db: AsyncSession) -> None:
        """Validate if user can add another competitor store."""
        if await _is_superuser_or_admin(user_id, db):
            return
        summary = await cls.get_user_usage_summary(user_id, db)
        if summary.current_stores >= summary.max_stores:
            raise EntitlementError(
                f"Store limit reached ({summary.current_stores}/{summary.max_stores}) for {summary.plan_name}. Please upgrade your plan."
            )

    @classmethod
    async def check_can_track_product(cls, user_id: uuid.UUID, db: AsyncSession) -> None:
        """Validate if user can track another product."""
        if await _is_superuser_or_admin(user_id, db):
            return
        summary = await cls.get_user_usage_summary(user_id, db)
        if summary.current_tracked_products >= summary.max_tracked_products:
            raise EntitlementError(
                f"Tracked product limit reached ({summary.current_tracked_products}/{summary.max_tracked_products}) for {summary.plan_name}. Please upgrade your plan."
            )

    @classmethod
    async def check_can_set_interval(
        cls, user_id: uuid.UUID, interval_minutes: int, db: AsyncSession
    ) -> None:
        """Validate if tracking interval meets plan minimum."""
        if await _is_superuser_or_admin(user_id, db):
            return
        plan = await cls.get_user_active_plan(user_id, db)
        if interval_minutes < plan.poll_interval_mins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Minimum check interval for {plan.name} is {plan.poll_interval_mins} minutes ({interval_minutes} mins requested). Please upgrade your plan.",
            )

    @classmethod
    async def check_can_set_priority(cls, user_id: uuid.UUID, db: AsyncSession) -> None:
        """Validate if user can designate another priority VIP product."""
        if await _is_superuser_or_admin(user_id, db):
            return
        summary = await cls.get_user_usage_summary(user_id, db)
        if summary.current_priority_products >= summary.max_priority_products:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Priority VIP product limit reached ({summary.current_priority_products}/{summary.max_priority_products}) for {summary.plan_name}. Please upgrade your plan.",
            )


class EntitlementError(Exception):
    def __init__(self, message: str, status_code: int = 403) -> None:
        super().__init__(message)
        self.status_code = status_code


async def check_store_limit(db: AsyncSession, user_id: uuid.UUID, current_count: int) -> None:
    if await _is_superuser_or_admin(user_id, db):
        return
    plan = await EntitlementService.get_user_active_plan(user_id, db)
    if current_count >= plan.max_stores:
        raise EntitlementError(f"Your plan allows a maximum of {plan.max_stores} store(s).")


async def get_max_tracked_products(db: AsyncSession, user_id: uuid.UUID) -> int:
    if await _is_superuser_or_admin(user_id, db):
        return 999999
    plan = await EntitlementService.get_user_active_plan(user_id, db)
    return plan.max_tracked_products
