"""
Billing router — Stripe checkout, portal, subscription status, plan listing.

Endpoints:
  GET    /billing/plans                      list available plans (public)
  GET    /billing/usage                      current user's usage summary
  GET    /billing/subscription               get current user's subscription (with embedded plan)
  GET    /billing/entitlements               current usage vs limits
  POST   /billing/checkout                   create Stripe Checkout Session (or direct upgrade)
  POST   /billing/downgrade                  switch to Free or lower plan without Stripe
  POST   /billing/portal                     create Stripe Customer Portal Session
  POST   /billing/cancel                     cancel subscription at period end
  POST   /billing/webhook                    Stripe webhook (no auth — sig verification instead)

  GET    /billing/admin/plans                all plans incl. hidden (superadmin)
  POST   /billing/admin/plans                create plan (superadmin)
  PATCH  /billing/admin/plans/{plan_id}      update plan (superadmin)
  PUT    /billing/admin/users/{user_id}/subscription   assign plan to user (superadmin)

Security:
  /billing/webhook uses Stripe signature verification (NOT JWT auth)
  All other endpoints require JWT authentication
"""

import logging
import uuid

from datetime import UTC, datetime, timedelta
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user_id, get_current_superuser_id
from app.modules.auth.models import User
from app.modules.billing.entitlements import EntitlementService
from app.modules.billing.models import Plan, Subscription
from app.modules.billing.schemas import (
    AdminAssignSubscriptionRequest,
    BillingPortalResponse,
    CheckoutSessionResponse,
    CreateCheckoutSessionRequest,
    CreatePlanRequest,
    CreatePortalSessionRequest,
    DowngradePlanRequest,
    EntitlementResponse,
    PlanResponse,
    SubscriptionResponse,
    UpdatePlanRequest,
    UserUsageSummaryResponse,
)
from app.modules.billing.stripe_service import (
    BillingError,
    cancel_subscription,
    create_billing_portal_session,
    create_checkout_session,
    get_or_create_customer,
    verify_webhook,
)
from app.modules.billing.webhook_handler import handle_webhook_event
from app.modules.stores.models import CompetitorStore
from app.modules.tracking.models import TrackedProduct

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing")


def _billing_error_to_http(e: BillingError) -> None:
    raise HTTPException(status_code=e.status_code, detail=str(e))


async def _get_or_create_free_subscription(user_id: uuid.UUID, db: AsyncSession) -> Subscription:
    """
    Ensure a user has a Free Plan subscription.
    Creates one if none exists, resets to Free if called on an existing sub.
    """
    free_plan_res = await db.execute(select(Plan).where(Plan.slug == "free"))
    free_plan = free_plan_res.scalar_one_or_none()
    if not free_plan:
        # Fallback: cheapest plan
        fallback_res = await db.execute(select(Plan).order_by(Plan.price_usd.asc()).limit(1))
        free_plan = fallback_res.scalar_one_or_none()
    if not free_plan:
        raise HTTPException(status_code=500, detail="No Free Plan found in database.")

    # Find existing subscription
    sub_res = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = sub_res.scalar_one_or_none()
    if sub:
        sub.plan_id = free_plan.id
        sub.status = "active"
        sub.stripe_subscription_id = None
        sub.stripe_customer_id = None
        sub.current_period_end = None
    else:
        sub = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            plan_id=free_plan.id,
            status="active",
        )
        db.add(sub)
    await db.commit()
    await EntitlementService.sync_user_plan_entitlements(user_id, db)
    return sub


# ─── Public Plan Listing ───────────────────────────────────────────────────────

@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[PlanResponse]:
    """List all active public plans ordered by price ascending (public — no auth required)."""
    result = await db.execute(
        select(Plan).where(Plan.is_active.is_(True), Plan.is_public.is_(True)).order_by(Plan.price_usd.asc())
    )
    plans = list(result.scalars().all())
    return [PlanResponse.from_orm_model(p) for p in plans]


# ─── User Billing Endpoints ───────────────────────────────────────────────────

@router.get("/usage", response_model=UserUsageSummaryResponse)
async def get_user_usage(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> UserUsageSummaryResponse:
    """Return user's active subscription limits and actual usage breakdown."""
    user_id = uuid.UUID(user_id_str)
    summary = await EntitlementService.get_user_usage_summary(user_id, db)
    return UserUsageSummaryResponse(
        plan_id=summary.plan_id,
        plan_name=summary.plan_name,
        plan_slug=summary.plan_slug,
        price_usd=summary.price_usd,
        max_stores=summary.max_stores,
        current_stores=summary.current_stores,
        paused_stores=summary.paused_stores,
        max_tracked_products=summary.max_tracked_products,
        current_tracked_products=summary.current_tracked_products,
        paused_tracked_products=summary.paused_tracked_products,
        min_poll_interval_mins=summary.min_poll_interval_mins,
        max_priority_products=summary.max_priority_products,
        current_priority_products=summary.current_priority_products,
        is_over_limit=summary.is_over_limit,
        features=summary.features,
    )


@router.get("/subscription", response_model=SubscriptionResponse | None)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> SubscriptionResponse | None:
    """
    Get the current user's active subscription with embedded plan details.

    Returns null only if the user truly has no subscription record at all.
    Returns the subscription object with embedded plan info for all status types
    (active, trialing, past_due, canceled).
    """
    user_id = uuid.UUID(user_id_str)

    # Fetch most recent subscription regardless of status (to show even canceled)
    result = await db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    row = result.one_or_none()
    if row is None:
        return None
    sub, plan = row
    return SubscriptionResponse.from_orm_model(sub, plan)


@router.get("/entitlements", response_model=EntitlementResponse)
async def get_entitlements(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> EntitlementResponse:
    """
    Return the current user's plan limits and actual usage counts.

    All limits come from the DB Plan record — no hardcoded fallbacks.
    Use this to power upgrade prompts and usage meters in the UI.
    """
    user_id = uuid.UUID(user_id_str)
    summary = await EntitlementService.get_user_usage_summary(user_id, db)

    # Resolve subscription status
    sub_result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trialing", "past_due"]),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = sub_result.scalar_one_or_none()
    subscription_status = sub.status if sub else "active"  # free = active

    return EntitlementResponse(
        plan_name=summary.plan_name,
        plan_slug=summary.plan_slug,
        plan_id=summary.plan_id,
        max_stores=summary.max_stores,
        current_stores=summary.current_stores,
        paused_stores=summary.paused_stores,
        max_tracked_products=summary.max_tracked_products,
        current_tracked_products=summary.current_tracked_products,
        paused_tracked_products=summary.paused_tracked_products,
        poll_interval_mins=summary.min_poll_interval_mins,
        subscription_status=subscription_status,
        is_over_limit=summary.is_over_limit,
    )


@router.post("/checkout", response_model=CheckoutSessionResponse, status_code=201)
async def create_checkout(
    data: CreateCheckoutSessionRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> CheckoutSessionResponse:
    """
    Create a Stripe Checkout Session for the selected plan (upgrade path).

    If the plan has no stripe_price_id, upgrades subscription directly in DB.
    If Stripe is configured but returns an error, falls back to direct DB update.
    """
    user_id = uuid.UUID(user_id_str)

    try:
        plan_uuid = uuid.UUID(data.plan_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Plan not found") from None

    plan_result = await db.execute(
        select(Plan).where(Plan.id == plan_uuid, Plan.is_active == True)  # noqa: E712
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    if (plan.slug or "").lower() == "free":
        raise HTTPException(status_code=400, detail="Use /billing/downgrade to switch to the Free plan.")

    # Direct upgrade (no Stripe Price ID configured)
    if not plan.stripe_price_id:
        logger.info(
            "Plan %s (%s) has no Stripe Price ID — performing direct subscription update for user %s.",
            plan.name, plan.id, user_id,
        )
        sub_res = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        sub = sub_res.scalar_one_or_none()
        if sub:
            sub.plan_id = plan.id
            sub.status = "active"
        else:
            sub = Subscription(id=uuid.uuid4(), user_id=user_id, plan_id=plan.id, status="active")
            db.add(sub)
        await db.commit()
        return CheckoutSessionResponse(checkout_url=data.success_url)

    # Stripe Checkout Session
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    existing_sub_res = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.stripe_customer_id.is_not(None),
        ).limit(1)
    )
    existing_sub = existing_sub_res.scalar_one_or_none()
    existing_customer_id = existing_sub.stripe_customer_id if existing_sub else None

    try:
        customer_id = await get_or_create_customer(
            user_id=str(user_id),
            email=user.email,
            existing_customer_id=existing_customer_id,
        )
        checkout_url = await create_checkout_session(
            user_id=str(user_id),
            customer_id=customer_id,
            stripe_price_id=plan.stripe_price_id,
            success_url=data.success_url,
            cancel_url=data.cancel_url,
        )
        return CheckoutSessionResponse(checkout_url=checkout_url)
    except BillingError as e:
        logger.warning(
            "Stripe error during checkout (%s) — falling back to direct subscription update for plan %s.",
            e, plan.name,
        )
        sub_res = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        sub = sub_res.scalar_one_or_none()
        if sub:
            sub.plan_id = plan.id
            sub.status = "active"
        else:
            sub = Subscription(id=uuid.uuid4(), user_id=user_id, plan_id=plan.id, status="active")
            db.add(sub)
        await db.commit()
        return CheckoutSessionResponse(checkout_url=data.success_url)


@router.post("/downgrade", response_model=SubscriptionResponse, status_code=200)
async def downgrade_plan(
    data: DowngradePlanRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> SubscriptionResponse:
    """
    Downgrade or switch to any plan (including Free) without Stripe Checkout.

    For non-Stripe subscriptions: immediately switches plan.
    For Stripe-managed subscriptions: also updates DB immediately (Stripe
    subscription should be handled via the billing portal for pro-rated changes).
    """
    user_id = uuid.UUID(user_id_str)

    try:
        plan_uuid = uuid.UUID(data.plan_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Plan not found") from None

    plan_result = await db.execute(
        select(Plan).where(Plan.id == plan_uuid, Plan.is_active == True)  # noqa: E712
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Get current subscription
    sub_res = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = sub_res.scalar_one_or_none()

    if sub:
        # If Stripe-managed, warn that the Stripe subscription is not being canceled
        if sub.stripe_subscription_id:
            logger.info(
                "User %s downgrading from Stripe-managed subscription %s to plan %s via direct update.",
                user_id, sub.stripe_subscription_id, plan.name,
            )
        sub.plan_id = plan.id
        sub.status = "active"
        # Clear Stripe fields for Free/direct plans that have no Stripe management
        if not plan.stripe_price_id:
            sub.stripe_subscription_id = None
            sub.current_period_end = None
    else:
        sub = Subscription(id=uuid.uuid4(), user_id=user_id, plan_id=plan.id, status="active")
        db.add(sub)

    await db.commit()
    await EntitlementService.sync_user_plan_entitlements(user_id, db)
    await db.refresh(sub)

    return SubscriptionResponse.from_orm_model(sub, plan)


@router.post("/portal", response_model=BillingPortalResponse)
async def create_portal(
    data: CreatePortalSessionRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> BillingPortalResponse:
    """
    Create a Stripe Customer Portal session.

    Users can cancel their subscription, update payment method, or
    download invoices through the portal. Only available for Stripe-managed subs.
    """
    user_id = uuid.UUID(user_id_str)

    sub_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.stripe_customer_id.is_not(None),
        ).limit(1)
    )
    sub = sub_result.scalar_one_or_none()
    if sub is None or not sub.stripe_customer_id:
        raise HTTPException(
            status_code=404,
            detail="No Stripe-managed subscription found. Please use the downgrade/cancel options instead.",
        )

    try:
        portal_url = await create_billing_portal_session(
            customer_id=sub.stripe_customer_id,
            return_url=data.return_url,
        )
    except BillingError as e:
        _billing_error_to_http(e)

    return BillingPortalResponse(portal_url=portal_url)


@router.post("/cancel", status_code=200)
async def cancel_current_subscription(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> dict:
    """
    Cancel the user's current subscription.

    - For Stripe-managed subscriptions: cancels at period end via Stripe API.
    - For direct (non-Stripe) subscriptions: immediately reverts to Free plan.
    """
    user_id = uuid.UUID(user_id_str)

    sub_result = await db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trialing"]),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    row = sub_result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No active subscription found")

    sub, plan = row

    # Free plan users — nothing to cancel
    if (plan.slug or "").lower() == "free":
        raise HTTPException(status_code=400, detail="You are already on the Free plan.")

    # Stripe-managed: cancel at period end
    if sub.stripe_subscription_id:
        try:
            await cancel_subscription(sub.stripe_subscription_id)
        except BillingError as e:
            _billing_error_to_http(e)
        return {
            "message": "Subscription will be canceled at the end of the current billing period.",
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        }

    # Direct subscription: revert to Free immediately
    await _get_or_create_free_subscription(user_id, db)
    return {
        "message": "Subscription canceled. You have been moved to the Free plan.",
        "current_period_end": None,
    }


# ─── Superadmin Plan Management ───────────────────────────────────────────────

@router.get("/admin/plans", response_model=list[PlanResponse])
async def admin_list_plans(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> list[PlanResponse]:
    """List all plans including inactive & hidden plans (Superadmin only)."""
    result = await db.execute(select(Plan).order_by(Plan.price_usd.asc()))
    plans = list(result.scalars().all())
    return [PlanResponse.from_orm_model(p) for p in plans]


@router.post("/admin/plans", response_model=PlanResponse, status_code=201)
async def admin_create_plan(
    data: CreatePlanRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> PlanResponse:
    """Create a new subscription plan (Superadmin only)."""
    existing = await db.execute(select(Plan).where(Plan.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Plan slug '{data.slug}' already exists")

    plan = Plan(
        name=data.name,
        slug=data.slug,
        price_usd=data.price_usd,
        stripe_price_id=data.stripe_price_id,
        max_stores=data.max_stores,
        max_tracked_products=data.max_tracked_products,
        poll_interval_mins=data.poll_interval_mins,
        max_priority_products=data.max_priority_products,
        is_active=data.is_active,
        is_public=data.is_public,
        features=data.features,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return PlanResponse.from_orm_model(plan)


@router.patch("/admin/plans/{plan_id}", response_model=PlanResponse)
async def admin_update_plan(
    plan_id: str,
    data: UpdatePlanRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> PlanResponse:
    """Update subscription plan parameters on the fly (Superadmin only)."""
    try:
        p_uuid = uuid.UUID(plan_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Plan not found") from None

    result = await db.execute(select(Plan).where(Plan.id == p_uuid))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if data.name is not None:
        plan.name = data.name
    if data.slug is not None:
        plan.slug = data.slug
    if data.price_usd is not None:
        plan.price_usd = data.price_usd
    if data.stripe_price_id is not None:
        plan.stripe_price_id = data.stripe_price_id
    if data.max_stores is not None:
        plan.max_stores = data.max_stores
    if data.max_tracked_products is not None:
        plan.max_tracked_products = data.max_tracked_products
    if data.poll_interval_mins is not None:
        plan.poll_interval_mins = data.poll_interval_mins
    if data.max_priority_products is not None:
        plan.max_priority_products = data.max_priority_products
    if data.is_active is not None:
        plan.is_active = data.is_active
    if data.is_public is not None:
        plan.is_public = data.is_public
    if data.features is not None:
        plan.features = data.features

    await db.commit()
    await db.refresh(plan)
    return PlanResponse.from_orm_model(plan)


@router.put("/admin/users/{target_user_id}/subscription", response_model=SubscriptionResponse)
async def admin_assign_user_subscription(
    target_user_id: str,
    data: AdminAssignSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    admin_id: str = Depends(get_current_superuser_id),
) -> SubscriptionResponse:
    """
    Assign a subscription plan directly to a user (Superadmin only).

    Useful for:
    - Manual billing (invoice customers)
    - Comping a paid plan for VIP users
    - Reverting users to Free after failed payments
    - Testing subscription flows without Stripe
    """
    try:
        user_uuid = uuid.UUID(target_user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found") from None

    # Validate user exists
    user_result = await db.execute(select(User).where(User.id == user_uuid))
    if user_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate plan exists
    try:
        plan_uuid = uuid.UUID(data.plan_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Plan not found") from None

    plan_result = await db.execute(select(Plan).where(Plan.id == plan_uuid))
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Upsert subscription
    sub_res = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_uuid)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = sub_res.scalar_one_or_none()
    if sub:
        sub.plan_id = plan.id
        sub.status = "active"
        # Don't clear Stripe fields — admin might be changing plan mid-subscription
    else:
        sub = Subscription(
            id=uuid.uuid4(),
            user_id=user_uuid,
            plan_id=plan.id,
            status="active",
        )
        db.add(sub)

    # Immediately sync user's active tracked products to the new plan's poll interval
    from datetime import timedelta, UTC
    from app.modules.tracking.models import TrackedProduct
    await db.execute(
        update(TrackedProduct)
        .where(TrackedProduct.user_id == user_uuid, TrackedProduct.is_active == True)
        .values(
            next_check_at=datetime.now(UTC) + timedelta(minutes=plan.poll_interval_mins),
            tracking_interval_minutes=None,
        )
    )

    await db.commit()
    await EntitlementService.sync_user_plan_entitlements(user_uuid, db)
    await db.refresh(sub)

    logger.info(
        "Admin %s assigned plan '%s' to user %s. Note: %s",
        admin_id, plan.name, target_user_id, data.note or "none",
    )

    return SubscriptionResponse.from_orm_model(sub, plan)


# ─── Stripe Webhook ───────────────────────────────────────────────────────────

@router.post("/webhook", status_code=200)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature"),
) -> dict:
    """
    Stripe webhook endpoint — receives and processes Stripe events.

    IMPORTANT: This endpoint does NOT use JWT authentication.
    It uses Stripe signature verification instead (stripe-signature header).
    Must receive the raw request body (not parsed JSON).

    Register this URL in the Stripe Dashboard:
      https://dashboard.stripe.com/webhooks → Add endpoint
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    # CRITICAL: read raw bytes before FastAPI parses the body
    payload = await request.body()

    try:
        event = verify_webhook(payload, stripe_signature)
    except BillingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    result = await handle_webhook_event(event, db)
    logger.info("Webhook processed: event=%s result=%s", event["type"], result)

    return {"status": "ok", "result": result}
