"""
Entitlement enforcement service.

Centralized validation helper for subscription plan limits and feature quotas:
- Store count limit (max_stores)
- Tracked product limit (max_tracked_products)
- Priority product limit (max_priority_products)
- Minimum tracking check interval (poll_interval_mins)
"""

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import Plan, Subscription
from app.modules.stores.models import CompetitorStore
from app.modules.tracking.models import TrackedProduct


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


class EntitlementService:

    @staticmethod
    async def get_user_active_plan(user_id: uuid.UUID, db: AsyncSession) -> Plan:
        """Fetch active plan for user, falling back to Free Plan if none assigned."""
        stmt = (
            select(Plan)
            .join(Subscription, Subscription.plan_id == Plan.id)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
            )
            .order_by(Plan.price_usd.desc())
        )
        result = await db.execute(stmt)
        plan = result.scalars().first()

        if not plan:
            # Fallback to default Free plan
            free_stmt = select(Plan).where(Plan.slug == "free")
            free_res = await db.execute(free_stmt)
            plan = free_res.scalars().first()

            if not plan:
                # Fallback if slug free missing
                any_stmt = select(Plan).order_by(Plan.price_usd.asc())
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
        plan = await cls.get_user_active_plan(user_id, db)

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

        return UserUsageSummary(
            plan_id=str(plan.id),
            plan_name=plan.name,
            plan_slug=plan.slug or "free",
            price_usd=float(plan.price_usd) if plan.price_usd is not None else 0.0,
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
        summary = await cls.get_user_usage_summary(user_id, db)
        if summary.current_stores >= summary.max_stores:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Store limit reached ({summary.current_stores}/{summary.max_stores}) for {summary.plan_name}. Please upgrade your plan.",
            )

    @classmethod
    async def check_can_track_product(cls, user_id: uuid.UUID, db: AsyncSession) -> None:
        """Validate if user can track another product."""
        summary = await cls.get_user_usage_summary(user_id, db)
        if summary.current_tracked_products >= summary.max_tracked_products:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tracked product limit reached ({summary.current_tracked_products}/{summary.max_tracked_products}) for {summary.plan_name}. Please upgrade your plan.",
            )

    @classmethod
    async def check_can_set_interval(
        cls, user_id: uuid.UUID, interval_minutes: int, db: AsyncSession
    ) -> None:
        """Validate if tracking interval meets plan minimum."""
        plan = await cls.get_user_active_plan(user_id, db)
        if interval_minutes < plan.poll_interval_mins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Minimum check interval for {plan.name} is {plan.poll_interval_mins} minutes ({interval_minutes} mins requested). Please upgrade your plan.",
            )

    @classmethod
    async def check_can_set_priority(cls, user_id: uuid.UUID, db: AsyncSession) -> None:
        """Validate if user can designate another priority VIP product."""
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
    plan = await EntitlementService.get_user_active_plan(user_id, db)
    if current_count >= plan.max_stores:
        raise EntitlementError(f"Your plan allows a maximum of {plan.max_stores} store(s).")


async def get_max_tracked_products(db: AsyncSession, user_id: uuid.UUID) -> int:
    plan = await EntitlementService.get_user_active_plan(user_id, db)
    return plan.max_tracked_products

