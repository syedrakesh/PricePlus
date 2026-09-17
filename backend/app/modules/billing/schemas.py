"""
Pydantic schemas for billing, subscription plans, usage metrics, and superadmin management.
"""

from datetime import UTC, datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str | None = None
    price_usd: float | None = 0.0
    stripe_price_id: str | None = None
    max_stores: int
    max_tracked_products: int
    poll_interval_mins: int
    max_priority_products: int = 0
    is_active: bool = True
    is_public: bool = True
    features: dict[str, Any] | None = None

    @classmethod
    def from_orm_model(cls, plan: Any) -> "PlanResponse":
        return cls(
            id=str(plan.id),
            name=plan.name,
            slug=plan.slug or "free",
            price_usd=float(plan.price_usd) if plan.price_usd is not None else 0.0,
            stripe_price_id=getattr(plan, 'stripe_price_id', None),
            max_stores=plan.max_stores,
            max_tracked_products=plan.max_tracked_products,
            poll_interval_mins=plan.poll_interval_mins,
            max_priority_products=getattr(plan, 'max_priority_products', 0),
            is_active=plan.is_active,
            is_public=getattr(plan, 'is_public', True),
            features=getattr(plan, 'features', {}) or {},
        )


class CreatePlanRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    slug: str = Field(..., min_length=2, max_length=50)
    price_usd: float = Field(default=0.0, ge=0)
    stripe_price_id: str | None = Field(default=None, max_length=255)
    max_stores: int = Field(default=1, ge=1)
    max_tracked_products: int = Field(default=10, ge=1)
    poll_interval_mins: int = Field(default=1440, ge=1)
    max_priority_products: int = Field(default=0, ge=0)
    is_active: bool = True
    is_public: bool = True
    features: dict[str, Any] = Field(default_factory=dict)


class UpdatePlanRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=50)
    slug: str | None = Field(default=None, min_length=2, max_length=50)
    price_usd: float | None = Field(default=None, ge=0)
    stripe_price_id: str | None = Field(default=None, max_length=255)
    max_stores: int | None = Field(default=None, ge=1)
    max_tracked_products: int | None = Field(default=None, ge=1)
    poll_interval_mins: int | None = Field(default=None, ge=1)
    max_priority_products: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    is_public: bool | None = None
    features: dict[str, Any] | None = None


class EntitlementResponse(BaseModel):
    plan_name: str
    plan_slug: str
    plan_id: str
    max_stores: int
    current_stores: int
    paused_stores: int = 0
    max_tracked_products: int
    current_tracked_products: int
    paused_tracked_products: int = 0
    poll_interval_mins: int
    subscription_status: str
    is_over_limit: bool = False
    current_period_end: str | None = None


class CreateCheckoutSessionRequest(BaseModel):
    plan_id: str
    success_url: str = Field(..., pattern=r"^https?://")
    cancel_url: str = Field(..., pattern=r"^https?://")


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class CreatePortalSessionRequest(BaseModel):
    return_url: str = Field(..., pattern=r"^https?://")


class BillingPortalResponse(BaseModel):
    portal_url: str


class VerifySessionRequest(BaseModel):
    session_id: str


class VerifySessionResponse(BaseModel):
    message: str
    plan_slug: str
    plan_name: str
    access_token: str | None = None
    refresh_token: str | None = None


class SubscriptionPlanInfo(BaseModel):
    """Embedded plan details inside a SubscriptionResponse."""
    id: str
    name: str
    slug: str
    price_usd: float
    max_stores: int
    max_tracked_products: int
    poll_interval_mins: int
    max_priority_products: int
    features: dict[str, Any] | None = None


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan_id: str
    plan: SubscriptionPlanInfo | None = None  # embedded plan details
    status: str
    # Human-friendly status label
    status_label: str
    # Stripe fields (present only for Stripe-managed subscriptions)
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_end: str | None = None
    created_at: str
    # Whether this is a non-Stripe (direct) subscription
    is_direct: bool = False

    @classmethod
    def from_orm_model(cls, sub: Any, plan: Any | None = None) -> "SubscriptionResponse":
        status_labels = {
            "active": "Active",
            "trialing": "Trialing",
            "past_due": "Past Due — Payment Required",
            "canceled": "Canceled",
            "free": "Free",
        }
        is_direct = sub.stripe_subscription_id is None and sub.stripe_customer_id is None

        plan_info = None
        if plan is not None:
            plan_info = SubscriptionPlanInfo(
                id=str(plan.id),
                name=plan.name,
                slug=plan.slug or "free",
                price_usd=float(plan.price_usd) if plan.price_usd is not None else 0.0,
                max_stores=plan.max_stores,
                max_tracked_products=plan.max_tracked_products,
                poll_interval_mins=plan.poll_interval_mins,
                max_priority_products=getattr(plan, 'max_priority_products', 0) or 0,
                features=getattr(plan, 'features', {}) or {},
            )

        return cls(
            id=str(sub.id),
            plan_id=str(sub.plan_id),
            plan=plan_info,
            status=sub.status,
            status_label=status_labels.get(sub.status, sub.status.title()),
            stripe_customer_id=sub.stripe_customer_id,
            stripe_subscription_id=sub.stripe_subscription_id,
            current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
            created_at=sub.created_at.isoformat() if getattr(sub, 'created_at', None) else datetime.now(UTC).isoformat(),
            is_direct=is_direct,
        )


class UserUsageSummaryResponse(BaseModel):
    plan_id: str
    plan_name: str
    plan_slug: str
    price_usd: float
    max_stores: int
    current_stores: int
    paused_stores: int = 0
    max_tracked_products: int
    current_tracked_products: int
    paused_tracked_products: int = 0
    min_poll_interval_mins: int
    max_priority_products: int
    current_priority_products: int
    is_over_limit: bool = False
    features: dict[str, Any]


class AdminAssignSubscriptionRequest(BaseModel):
    """Admin-only request body to assign a specific plan to a user."""
    plan_id: str
    note: str | None = Field(default=None, max_length=500, description="Internal note for audit log")


class DowngradePlanRequest(BaseModel):
    """Request to downgrade/switch to a lower or equal plan without Stripe Checkout."""
    plan_id: str


class ExtendSubscriptionRequest(BaseModel):
    """Request to extend an existing subscription by a given number of months."""
    months: int = Field(default=1, ge=1, le=36, description="Number of months to extend subscription by")
    plan_id: str | None = Field(default=None, description="Optional plan ID if extending and switching plan simultaneously")


class ExtendSubscriptionResponse(BaseModel):
    """Response returned after extending a subscription."""
    message: str
    months_added: int
    new_period_end: str
    subscription: SubscriptionResponse

