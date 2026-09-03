"""
Plan seed script — inserts the three canonical plans.

Run via: make seed-plans
Or called automatically on first startup if plans table is empty.

Plans:
  free     — 2 stores, 10 products, 60 min poll, $0
  starter  — 5 stores, 100 products, 30 min poll, $29/mo
  pro      — 20 stores, 1000 products, 15 min poll, $99/mo

stripe_price_id values are placeholders — set via .env once Stripe products
are created in the Stripe dashboard.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

PLANS = [
    {
        "name": "free",
        "stripe_price_id": None,
        "max_stores": 2,
        "max_tracked_products": 10,
        "poll_interval_mins": 60,
        "price_usd": 0.0,
        "is_active": True,
    },
    {
        "name": "starter",
        "stripe_price_id": None,  # Set from env: STRIPE_PRICE_ID_STARTER
        "max_stores": 5,
        "max_tracked_products": 100,
        "poll_interval_mins": 30,
        "price_usd": 29.0,
        "is_active": True,
    },
    {
        "name": "pro",
        "stripe_price_id": None,  # Set from env: STRIPE_PRICE_ID_PRO
        "max_stores": 20,
        "max_tracked_products": 1000,
        "poll_interval_mins": 15,
        "price_usd": 99.0,
        "is_active": True,
    },
]


async def seed_plans() -> None:
    """Insert plans if they don't exist. Idempotent."""
    import uuid

    from sqlalchemy import select

    from app.core.config import get_settings
    from app.core.db import AsyncSessionLocal
    from app.modules.billing.models import Plan

    settings = get_settings()

    # Apply Stripe price IDs from settings if provided
    plan_price_ids = {
        "starter": getattr(settings, "stripe_price_id_starter", None) or None,
        "pro": getattr(settings, "stripe_price_id_pro", None) or None,
    }

    async with AsyncSessionLocal() as db:
        for plan_data in PLANS:
            name = plan_data["name"]
            result = await db.execute(select(Plan).where(Plan.name == name))
            existing = result.scalar_one_or_none()

            price_id = plan_price_ids.get(name)

            if existing is None:
                new_plan = Plan(
                    id=uuid.uuid4(),
                    name=name,
                    stripe_price_id=price_id or plan_data["stripe_price_id"],
                    max_stores=plan_data["max_stores"],
                    max_tracked_products=plan_data["max_tracked_products"],
                    poll_interval_mins=plan_data["poll_interval_mins"],
                    price_usd=plan_data["price_usd"],
                    is_active=plan_data["is_active"],
                )
                db.add(new_plan)
                logger.info("Seeded plan: %s", name)
            else:
                # Update stripe_price_id if it was set from env
                if price_id and existing.stripe_price_id != price_id:
                    existing.stripe_price_id = price_id
                    logger.info("Updated stripe_price_id for plan: %s", name)

        await db.commit()

    logger.info("Plan seeding complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_plans())
