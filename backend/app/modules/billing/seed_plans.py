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
        "name": "Free Plan",
        "slug": "free",
        "stripe_price_id": None,
        "max_stores": 1,
        "max_tracked_products": 10,
        "poll_interval_mins": 1440,
        "max_priority_products": 0,
        "price_usd": 0.0,
        "is_active": True,
        "is_public": True,
        "features": {
            "csv_export": False,
            "instant_alerts": False,
            "vip_monitoring": False,
        },
    },
    {
        "name": "Starter Plan",
        "slug": "starter",
        "stripe_price_id": None,
        "max_stores": 3,
        "max_tracked_products": 100,
        "poll_interval_mins": 180,
        "max_priority_products": 2,
        "price_usd": 29.0,
        "is_active": True,
        "is_public": True,
        "features": {
            "csv_export": True,
            "instant_alerts": True,
            "vip_monitoring": True,
        },
    },
    {
        "name": "Pro Plan",
        "slug": "pro",
        "stripe_price_id": None,
        "max_stores": 10,
        "max_tracked_products": 500,
        "poll_interval_mins": 60,
        "max_priority_products": 10,
        "price_usd": 79.0,
        "is_active": True,
        "is_public": True,
        "features": {
            "csv_export": True,
            "instant_alerts": True,
            "vip_monitoring": True,
        },
    },
    {
        "name": "Enterprise Plan",
        "slug": "enterprise",
        "stripe_price_id": None,
        "max_stores": 50,
        "max_tracked_products": 5000,
        "poll_interval_mins": 1,
        "max_priority_products": 50,
        "price_usd": 299.0,
        "is_active": True,
        "is_public": True,
        "features": {
            "csv_export": True,
            "instant_alerts": True,
            "vip_monitoring": True,
            "dedicated_proxy": True,
        },
    },
]


async def seed_plans() -> None:
    """Insert default canonical plans if they don't exist. Idempotent."""
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
            slug = plan_data["slug"]
            result = await db.execute(select(Plan).where(Plan.slug == slug))
            existing = result.scalar_one_or_none()

            price_id = plan_price_ids.get(slug)

            if existing is None:
                new_plan = Plan(
                    id=uuid.uuid4(),
                    name=plan_data["name"],
                    slug=slug,
                    stripe_price_id=price_id or plan_data["stripe_price_id"],
                    max_stores=plan_data["max_stores"],
                    max_tracked_products=plan_data["max_tracked_products"],
                    poll_interval_mins=plan_data["poll_interval_mins"],
                    max_priority_products=plan_data["max_priority_products"],
                    price_usd=plan_data["price_usd"],
                    is_active=plan_data["is_active"],
                    is_public=plan_data["is_public"],
                    features=plan_data["features"],
                )
                db.add(new_plan)
                logger.info("Seeded plan: %s (%s)", plan_data["name"], slug)
            else:
                if price_id and existing.stripe_price_id != price_id:
                    existing.stripe_price_id = price_id
                    logger.info("Updated stripe_price_id for plan: %s", slug)

        await db.commit()

    logger.info("Plan seeding complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_plans())
