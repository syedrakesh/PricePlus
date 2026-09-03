"""
Pydantic schemas for billing endpoints.
"""

from pydantic import BaseModel, field_validator


class PlanResponse(BaseModel):
    id: str
    name: str
    price_usd: float | None
    max_stores: int
    max_tracked_products: int
    poll_interval_mins: int
    is_active: bool

    @classmethod
    def from_orm_model(cls, plan: object) -> "PlanResponse":
        from app.modules.billing.models import Plan
        assert isinstance(plan, Plan)
        return cls(
            id=str(plan.id),
            name=plan.name,
            price_usd=float(plan.price_usd) if plan.price_usd is not None else None,
            max_stores=plan.max_stores,
            max_tracked_products=plan.max_tracked_products,
            poll_interval_mins=plan.poll_interval_mins,
            is_active=plan.is_active,
        )


class SubscriptionResponse(BaseModel):
    id: str
    user_id: str
    plan: PlanResponse
    status: str
    current_period_end: str | None
    stripe_customer_id: str | None

    @classmethod
    def from_orm_model(cls, sub: object, plan: object) -> "SubscriptionResponse":
        from app.modules.billing.models import Plan, Subscription
        assert isinstance(sub, Subscription)
        assert isinstance(plan, Plan)
        return cls(
            id=str(sub.id),
            user_id=str(sub.user_id),
            plan=PlanResponse.from_orm_model(plan),
            status=sub.status,
            current_period_end=(
                sub.current_period_end.isoformat() if sub.current_period_end else None
            ),
            stripe_customer_id=sub.stripe_customer_id,
        )


class CreateCheckoutSessionRequest(BaseModel):
    plan_id: str
    success_url: str
    cancel_url: str

    @field_validator("success_url", "cancel_url")
    @classmethod
    def validate_https_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class BillingPortalResponse(BaseModel):
    portal_url: str


class CreatePortalSessionRequest(BaseModel):
    return_url: str

    @field_validator("return_url")
    @classmethod
    def validate_return_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("return_url must start with http:// or https://")
        return v


class EntitlementResponse(BaseModel):
    """Current plan limits and usage for the authenticated user."""
    plan_name: str
    max_stores: int
    current_stores: int
    max_tracked_products: int
    current_tracked_products: int
    poll_interval_mins: int
    subscription_status: str
