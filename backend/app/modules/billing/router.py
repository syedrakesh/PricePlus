"""
Billing router — Stripe checkout, portal, subscription status, plan listing.

Endpoints:
  GET    /billing/plans                list available plans (public)
  GET    /billing/subscription         get current user's subscription
  GET    /billing/entitlements         current usage vs limits
  POST   /billing/checkout             create Stripe Checkout Session
  POST   /billing/portal               create Stripe Customer Portal Session
  POST   /billing/cancel               cancel subscription at period end
  POST   /billing/webhook              Stripe webhook (no auth — sig verification instead)

Security:
  /billing/webhook uses Stripe signature verification (NOT JWT auth)
  All other endpoints require JWT authentication
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.auth.models import User
from app.modules.billing.models import Plan, Subscription
from app.modules.billing.schemas import (
    BillingPortalResponse,
    CheckoutSessionResponse,
    CreateCheckoutSessionRequest,
    CreatePortalSessionRequest,
    EntitlementResponse,
    PlanResponse,
    SubscriptionResponse,
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


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[PlanResponse]:
    """List all active plans (public — no auth required)."""
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.price_usd.asc())  # noqa: E712
    )
    plans = list(result.scalars().all())
    return [PlanResponse.from_orm_model(p) for p in plans]


@router.get("/subscription", response_model=SubscriptionResponse | None)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> SubscriptionResponse | None:
    """
    Get the current user's active subscription and plan details.
    Returns null if the user has no subscription (free tier implied).
    """
    user_id = uuid.UUID(user_id_str)
    result = await db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trialing", "past_due"]),
        )
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

    Use this to power upgrade prompts and usage meters in the UI.
    """
    user_id = uuid.UUID(user_id_str)

    # Get plan + subscription
    sub_result = await db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trialing"]),
        )
        .limit(1)
    )
    row = sub_result.one_or_none()

    if row:
        sub, plan = row
        subscription_status = sub.status
    else:
        # Free tier defaults
        plan = await db.execute(select(Plan).where(Plan.name == "free"))
        plan = plan.scalar_one_or_none()
        subscription_status = "free"

    # Count actual usage
    stores_count = await db.execute(
        select(func.count()).where(CompetitorStore.user_id == user_id)
    )
    tracked_count = await db.execute(
        select(func.count()).where(
            TrackedProduct.user_id == user_id,
            TrackedProduct.is_active == True,  # noqa: E712
        )
    )

    if plan is None:
        # Absolute fallback
        return EntitlementResponse(
            plan_name="free",
            max_stores=2,
            current_stores=stores_count.scalar_one(),
            max_tracked_products=10,
            current_tracked_products=tracked_count.scalar_one(),
            poll_interval_mins=60,
            subscription_status=subscription_status,
        )

    return EntitlementResponse(
        plan_name=plan.name,
        max_stores=plan.max_stores,
        current_stores=stores_count.scalar_one(),
        max_tracked_products=plan.max_tracked_products,
        current_tracked_products=tracked_count.scalar_one(),
        poll_interval_mins=plan.poll_interval_mins,
        subscription_status=subscription_status,
    )


@router.post("/checkout", response_model=CheckoutSessionResponse, status_code=201)
async def create_checkout(
    data: CreateCheckoutSessionRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> CheckoutSessionResponse:
    """
    Create a Stripe Checkout Session for the selected plan.

    Returns a checkout_url to redirect the user to Stripe's hosted checkout.
    After payment, Stripe redirects back to success_url and sends a webhook
    which creates/updates the Subscription record.
    """
    user_id = uuid.UUID(user_id_str)

    # Load the plan
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

    if plan.name == "free":
        raise HTTPException(status_code=400, detail="Cannot create a checkout session for the free plan")

    if not plan.stripe_price_id:
        raise HTTPException(
            status_code=503,
            detail="This plan is not yet configured for payment. Please contact support.",
        )

    # Load user email for Stripe customer
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Get existing stripe_customer_id if any
    existing_sub = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.stripe_customer_id.is_not(None),
        ).limit(1)
    )
    existing_sub = existing_sub.scalar_one_or_none()
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
    except BillingError as e:
        _billing_error_to_http(e)

    return CheckoutSessionResponse(checkout_url=checkout_url)


@router.post("/portal", response_model=BillingPortalResponse)
async def create_portal(
    data: CreatePortalSessionRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> BillingPortalResponse:
    """
    Create a Stripe Customer Portal session.

    Users can cancel their subscription, update payment method, or
    download invoices through the portal.
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
            detail="No active subscription found. Please subscribe to a paid plan first.",
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
    Cancel the user's current subscription at the end of the billing period.

    The subscription remains active until current_period_end.
    Status will be updated to 'canceled' by the webhook when it expires.
    """
    user_id = uuid.UUID(user_id_str)

    sub_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.stripe_subscription_id.is_not(None),
        ).limit(1)
    )
    sub = sub_result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="No active subscription found")

    try:
        await cancel_subscription(sub.stripe_subscription_id)
    except BillingError as e:
        _billing_error_to_http(e)

    return {
        "message": "Subscription will be canceled at the end of the current billing period.",
        "current_period_end": (
            sub.current_period_end.isoformat() if sub.current_period_end else None
        ),
    }


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
