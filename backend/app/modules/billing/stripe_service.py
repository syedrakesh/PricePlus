"""
Stripe service — all interactions with the Stripe API.

Design decisions:
- All Stripe API calls are synchronous (stripe-python is sync) but wrapped
  in asyncio.run_in_executor so they don't block the FastAPI event loop.
- stripe.api_key is set globally at app startup (set_stripe_key()).
- Idempotency keys: checkout sessions and customer creation use idempotency
  keys based on user_id so repeated calls return the same Stripe object.
- Never store raw card data — all payment handled by Stripe Checkout.
- Webhook verification uses the webhook secret (timing-safe comparison via Stripe SDK).

Stripe objects used:
  Customer    — created once per user, stored in Subscription.stripe_customer_id
  Checkout Session — ephemeral, returned to frontend for redirect
  Billing Portal  — for subscription management (cancel, upgrade)
  Subscription    — managed via webhooks (never polled)

Error handling:
  stripe.StripeError → re-raised as BillingError with appropriate HTTP status
"""

import asyncio
import logging
from functools import partial

import stripe
import stripe.error

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class BillingError(Exception):
    """Raised for Stripe API errors or billing validation failures."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def configure_stripe() -> None:
    """Set Stripe API key from settings. Call once at app startup."""
    settings = get_settings()
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key
        logger.info("Stripe configured (key prefix: %s...)", settings.stripe_secret_key[:7])
    else:
        logger.warning("STRIPE_SECRET_KEY not set — billing will not work")


async def _run_stripe(func: callable, *args, **kwargs) -> object:
    """
    Run a synchronous Stripe API call in the thread pool.
    Converts stripe.StripeError to BillingError.
    """
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))
    except stripe.error.CardError as e:
        raise BillingError(str(e.user_message or e), status_code=402) from e
    except stripe.error.InvalidRequestError as e:
        raise BillingError(str(e), status_code=400) from e
    except stripe.error.AuthenticationError as e:
        raise BillingError("Stripe authentication failed", status_code=503) from e
    except stripe.error.StripeError as e:
        logger.error("Stripe API error: %s", e)
        raise BillingError(f"Payment service error: {e}", status_code=503) from e


async def get_or_create_customer(
    user_id: str,
    email: str,
    existing_customer_id: str | None = None,
) -> str:
    """
    Return an existing Stripe Customer ID or create a new one.

    Idempotent: uses metadata.user_id to prevent duplicate customers
    if the subscription record is lost.
    """
    if existing_customer_id:
        return existing_customer_id

    customer = await _run_stripe(
        stripe.Customer.create,
        email=email,
        metadata={"user_id": user_id},
        idempotency_key=f"customer-{user_id}",
    )
    logger.info("Created Stripe customer %s for user %s", customer.id, user_id)
    return customer.id


async def create_checkout_session(
    user_id: str,
    customer_id: str,
    stripe_price_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """
    Create a Stripe Checkout Session for a subscription.

    Returns the session URL to redirect the user to.
    The subscription is created by Stripe and confirmed via webhook.
    """
    session = await _run_stripe(
        stripe.checkout.Session.create,
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": stripe_price_id, "quantity": 1}],
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user_id},
        # Allow promotion codes for marketing
        allow_promotion_codes=True,
        # Collect billing address for tax purposes
        billing_address_collection="auto",
    )
    logger.info("Created checkout session %s for user %s", session.id, user_id)
    return session.url


async def create_billing_portal_session(
    customer_id: str,
    return_url: str,
) -> str:
    """
    Create a Stripe Customer Portal session for subscription management.

    Users can cancel, upgrade, or update payment method through the portal.
    Returns the portal URL.
    """
    session = await _run_stripe(
        stripe.billing_portal.Session.create,
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def verify_webhook(payload: bytes, sig_header: str) -> stripe.Event:
    """
    Verify a Stripe webhook signature and return the event.

    Raises BillingError if the signature is invalid.
    Must be called with the raw request body (bytes), not parsed JSON.
    """
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise BillingError("Stripe webhook secret not configured", status_code=503)

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
        return event
    except stripe.error.SignatureVerificationError as e:
        logger.warning("Invalid Stripe webhook signature: %s", e)
        raise BillingError("Invalid webhook signature", status_code=400) from e


async def cancel_subscription(stripe_subscription_id: str) -> None:
    """Cancel a Stripe subscription at period end (not immediately)."""
    await _run_stripe(
        stripe.Subscription.modify,
        stripe_subscription_id,
        cancel_at_period_end=True,
    )
    logger.info("Scheduled cancellation for subscription %s", stripe_subscription_id)
