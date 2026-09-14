"""
Stripe webhook event handler.

Processes inbound Stripe events to keep our Subscription table in sync.
This is the ONLY mechanism that updates subscription status — we never poll
Stripe for subscription state.

Idempotency:
  Stripe may deliver the same event multiple times. Each handler function
  is idempotent — processing the same event twice produces the same result.
  We use stripe_subscription_id as the natural key for upserts.

Events handled:
  checkout.session.completed
    → Subscription created after successful payment
    → Create/update Subscription record, link stripe_customer_id

  customer.subscription.updated
    → Plan change, renewal, payment failure status update
    → Update status, current_period_end, plan_id (if price changed)

  customer.subscription.deleted
    → Subscription canceled (at period end or immediately)
    → Update status to 'canceled'

  invoice.payment_failed
    → Payment failed (card declined, etc.)
    → Update status to 'past_due'

  invoice.payment_succeeded
    → Renewal successful after past_due
    → Update status back to 'active'

Unhandled events are logged and ignored (not an error).
"""

import logging
import uuid
from datetime import UTC, datetime

import stripe
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import Plan, Subscription

logger = logging.getLogger(__name__)


async def handle_webhook_event(event: stripe.Event, db: AsyncSession) -> str:
    """
    Route a Stripe event to the appropriate handler.

    Returns a human-readable description of what was processed.
    All handlers are idempotent.
    """
    event_type = event["type"]
    data = event["data"]["object"]

    handlers = {
        "checkout.session.completed": _handle_checkout_completed,
        "customer.subscription.updated": _handle_subscription_updated,
        "customer.subscription.deleted": _handle_subscription_deleted,
        "invoice.payment_failed": _handle_payment_failed,
        "invoice.payment_succeeded": _handle_payment_succeeded,
    }

    handler = handlers.get(event_type)
    if handler is None:
        logger.debug("Ignoring unhandled Stripe event type: %s", event_type)
        return f"ignored:{event_type}"

    logger.info("Processing Stripe event: %s (id=%s)", event_type, event["id"])
    result = await handler(data, db)
    await db.commit()

    # Sync user plan entitlements after subscription change
    stripe_sub_id = data.get("subscription") or (data.get("id") if "subscription" in event_type else None)
    if stripe_sub_id:
        sub = await _get_subscription_by_stripe_id(db, stripe_sub_id)
        if sub:
            from app.modules.billing.entitlements import EntitlementService
            await EntitlementService.sync_user_plan_entitlements(sub.user_id, db)

    return result


async def _handle_checkout_completed(data: dict, db: AsyncSession) -> str:
    """
    checkout.session.completed — user completed Stripe Checkout.

    Creates or updates the Subscription record.
    The subscription is always active at this point.
    """
    if data.get("mode") != "subscription":
        return "skipped:not_subscription_mode"

    stripe_sub_id = data.get("subscription")
    stripe_customer_id = data.get("customer")
    user_id_str = data.get("metadata", {}).get("user_id")

    if not stripe_sub_id or not user_id_str:
        logger.warning("checkout.session.completed missing subscription or user_id metadata")
        return "error:missing_fields"

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        logger.error("Invalid user_id in Stripe metadata: %r", user_id_str)
        return "error:invalid_user_id"

    # Fetch full subscription from Stripe to get price_id and period_end
    import asyncio
    from functools import partial
    loop = asyncio.get_event_loop()
    sub = await loop.run_in_executor(
        None, partial(stripe.Subscription.retrieve, stripe_sub_id)
    )

    price_id = sub["items"]["data"][0]["price"]["id"] if sub["items"]["data"] else None
    period_end = datetime.fromtimestamp(sub["current_period_end"], tz=UTC)

    # Look up our Plan by stripe_price_id
    plan = await _get_plan_by_price_id(db, price_id)
    if plan is None:
        logger.error("No plan found for Stripe price_id=%r", price_id)
        return "error:unknown_plan"

    # Upsert subscription
    existing = await _get_subscription_by_stripe_id(db, stripe_sub_id)
    if existing is not None:
        # Update existing
        await db.execute(
            update(Subscription)
            .where(Subscription.stripe_subscription_id == stripe_sub_id)
            .values(
                status="active",
                plan_id=plan.id,
                stripe_customer_id=stripe_customer_id,
                current_period_end=period_end,
            )
        )
        logger.info("Updated subscription for user %s (sub=%s)", user_id, stripe_sub_id)
    else:
        # Create new
        new_sub = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            plan_id=plan.id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_sub_id,
            status="active",
            current_period_end=period_end,
        )
        db.add(new_sub)
        logger.info("Created subscription for user %s (sub=%s)", user_id, stripe_sub_id)

    return f"ok:subscription_activated:{stripe_sub_id}"


async def _handle_subscription_updated(data: dict, db: AsyncSession) -> str:
    """
    customer.subscription.updated — plan change, renewal, status update.
    """
    stripe_sub_id = data.get("id")
    new_status = data.get("status")
    period_end_ts = data.get("current_period_end")
    price_id = None

    items = data.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")

    if not stripe_sub_id:
        return "error:missing_subscription_id"

    period_end = datetime.fromtimestamp(period_end_ts, tz=UTC) if period_end_ts else None

    update_vals: dict = {
        "status": new_status,
        "current_period_end": period_end,
    }

    # If plan changed, update plan_id
    if price_id:
        plan = await _get_plan_by_price_id(db, price_id)
        if plan is not None:
            update_vals["plan_id"] = plan.id

    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == stripe_sub_id)
        .values(**update_vals)
    )

    logger.info(
        "Subscription updated: sub=%s status=%s period_end=%s",
        stripe_sub_id, new_status, period_end,
    )
    return f"ok:subscription_updated:{stripe_sub_id}"


async def _handle_subscription_deleted(data: dict, db: AsyncSession) -> str:
    """
    customer.subscription.deleted — canceled (at period end or immediately).
    """
    stripe_sub_id = data.get("id")
    if not stripe_sub_id:
        return "error:missing_subscription_id"

    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == stripe_sub_id)
        .values(status="canceled")
    )

    logger.info("Subscription canceled: sub=%s", stripe_sub_id)
    return f"ok:subscription_canceled:{stripe_sub_id}"


async def _handle_payment_failed(data: dict, db: AsyncSession) -> str:
    """
    invoice.payment_failed — payment declined, subscription goes past_due.
    """
    stripe_sub_id = data.get("subscription")
    if not stripe_sub_id:
        return "skipped:no_subscription_id"

    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == stripe_sub_id)
        .values(status="past_due")
    )

    logger.warning("Payment failed for subscription: %s", stripe_sub_id)
    return f"ok:marked_past_due:{stripe_sub_id}"


async def _handle_payment_succeeded(data: dict, db: AsyncSession) -> str:
    """
    invoice.payment_succeeded — payment recovered, restore active status.
    """
    stripe_sub_id = data.get("subscription")
    if not stripe_sub_id:
        return "skipped:no_subscription_id"

    # Only update if currently past_due (don't overwrite other states)
    existing = await _get_subscription_by_stripe_id(db, stripe_sub_id)
    if existing is not None and existing.status == "past_due":
        await db.execute(
            update(Subscription)
            .where(Subscription.stripe_subscription_id == stripe_sub_id)
            .values(status="active")
        )
        logger.info("Payment recovered, subscription reactivated: %s", stripe_sub_id)
        return f"ok:reactivated:{stripe_sub_id}"

    return "skipped:not_past_due"


# ─── DB helpers ───────────────────────────────────────────────────────────────

async def _get_plan_by_price_id(db: AsyncSession, price_id: str | None) -> Plan | None:
    if not price_id:
        return None
    result = await db.execute(
        select(Plan).where(Plan.stripe_price_id == price_id, Plan.is_active == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def _get_subscription_by_stripe_id(
    db: AsyncSession, stripe_sub_id: str
) -> Subscription | None:
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    return result.scalar_one_or_none()
