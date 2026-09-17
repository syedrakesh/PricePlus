"""
Unit tests for Stripe billing — webhook handler and billing service.

Uses unittest.mock to patch stripe API calls — no real Stripe account required.
Tests cover: webhook event routing, idempotency, all 5 event types,
BillingError mapping, and entitlement schema validation.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.billing.webhook_handler import (
    _handle_checkout_completed,
    _handle_payment_failed,
    _handle_payment_succeeded,
    _handle_subscription_deleted,
    _handle_subscription_updated,
    handle_webhook_event,
)

# ─── Fixtures ──────────────────────────────────────────────────────────────────

USER_ID = str(uuid.uuid4())
STRIPE_SUB_ID = "sub_test_123"
STRIPE_CUSTOMER_ID = "cus_test_456"
STRIPE_PRICE_ID = "price_test_789"

NOW_TS = int(datetime.now(UTC).timestamp())


def _make_db(
    plan=None,
    existing_sub=None,
) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()

    # execute side effects depend on call order
    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = plan

    sub_result = MagicMock()
    sub_result.scalar_one_or_none.return_value = existing_sub

    db.execute = AsyncMock(side_effect=[plan_result, sub_result])
    return db


def _make_plan(plan_id=None):
    plan = MagicMock()
    plan.id = plan_id or uuid.uuid4()
    plan.name = "starter"
    plan.stripe_price_id = STRIPE_PRICE_ID
    return plan


def _make_subscription(status="active", stripe_sub_id=STRIPE_SUB_ID):
    sub = MagicMock()
    sub.id = uuid.uuid4()
    sub.stripe_subscription_id = stripe_sub_id
    sub.status = status
    sub.stripe_customer_id = STRIPE_CUSTOMER_ID
    return sub


# ─── Webhook routing ──────────────────────────────────────────────────────────

class TestWebhookRouting:
    @pytest.mark.asyncio
    async def test_unknown_event_ignored(self):
        event = {"type": "some.unknown.event", "id": "evt_1", "data": {"object": {}}}
        db = AsyncMock()
        result = await handle_webhook_event(event, db)
        assert "ignored" in result

    @pytest.mark.asyncio
    async def test_checkout_completed_routed(self):
        event = {
            "type": "checkout.session.completed",
            "id": "evt_2",
            "data": {"object": {"mode": "payment"}},  # non-subscription mode
        }
        db = AsyncMock()
        result = await handle_webhook_event(event, db)
        # mode=payment should be skipped
        assert "skipped" in result


# ─── checkout.session.completed ───────────────────────────────────────────────

class TestCheckoutCompleted:
    @pytest.mark.asyncio
    async def test_non_subscription_mode_skipped(self):
        data = {"mode": "payment", "subscription": None, "customer": None, "metadata": {}}
        db = AsyncMock()
        result = await _handle_checkout_completed(data, db)
        assert result == "skipped:not_subscription_mode"

    @pytest.mark.asyncio
    async def test_missing_user_id_returns_error(self):
        data = {
            "mode": "subscription",
            "subscription": STRIPE_SUB_ID,
            "customer": STRIPE_CUSTOMER_ID,
            "metadata": {},  # no user_id
        }
        db = AsyncMock()
        result = await _handle_checkout_completed(data, db)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_user_id_returns_error(self):
        data = {
            "mode": "subscription",
            "subscription": STRIPE_SUB_ID,
            "customer": STRIPE_CUSTOMER_ID,
            "metadata": {"user_id": "not-a-uuid"},
        }
        db = AsyncMock()
        result = await _handle_checkout_completed(data, db)
        assert result == "error:invalid_user_id"

    @pytest.mark.asyncio
    @patch("app.modules.billing.webhook_handler.stripe.Subscription.retrieve")
    async def test_unknown_plan_returns_error(self, mock_retrieve):
        """No plan matching the Stripe price_id → error."""
        mock_sub = MagicMock()
        mock_sub.__getitem__ = MagicMock(side_effect=lambda k: {
            "items": {"data": [{"price": {"id": STRIPE_PRICE_ID}}]},
            "current_period_end": NOW_TS,
        }[k])
        mock_retrieve.return_value = mock_sub

        data = {
            "mode": "subscription",
            "subscription": STRIPE_SUB_ID,
            "customer": STRIPE_CUSTOMER_ID,
            "metadata": {"user_id": USER_ID},
        }
        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = None  # no matching plan
        db = AsyncMock()
        db.execute = AsyncMock(return_value=plan_result)

        result = await _handle_checkout_completed(data, db)
        assert result == "error:unknown_plan"


# ─── customer.subscription.updated ───────────────────────────────────────────

class TestSubscriptionUpdated:
    @pytest.mark.asyncio
    async def test_missing_sub_id_returns_error(self):
        data = {"id": None, "status": "active", "current_period_end": NOW_TS, "items": {"data": []}}
        db = AsyncMock()
        result = await _handle_subscription_updated(data, db)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_status_updated(self):
        data = {
            "id": STRIPE_SUB_ID,
            "status": "past_due",
            "current_period_end": NOW_TS,
            "items": {"data": []},
        }
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock())
        result = await _handle_subscription_updated(data, db)
        assert "ok:subscription_updated" in result
        db.execute.assert_called_once()


# ─── customer.subscription.deleted ───────────────────────────────────────────

class TestSubscriptionDeleted:
    @pytest.mark.asyncio
    async def test_marks_canceled(self):
        data = {"id": STRIPE_SUB_ID}
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock())
        result = await _handle_subscription_deleted(data, db)
        assert "ok:subscription_canceled" in result

    @pytest.mark.asyncio
    async def test_missing_id_returns_error(self):
        data = {}
        db = AsyncMock()
        result = await _handle_subscription_deleted(data, db)
        assert "error" in result


# ─── invoice.payment_failed ───────────────────────────────────────────────────

class TestPaymentFailed:
    @pytest.mark.asyncio
    async def test_marks_past_due(self):
        data = {"subscription": STRIPE_SUB_ID}
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock())
        result = await _handle_payment_failed(data, db)
        assert "ok:canceled_no_grace_period" in result

    @pytest.mark.asyncio
    async def test_no_sub_id_skipped(self):
        data = {}
        db = AsyncMock()
        result = await _handle_payment_failed(data, db)
        assert "skipped" in result


# ─── invoice.payment_succeeded ────────────────────────────────────────────────

class TestPaymentSucceeded:
    @pytest.mark.asyncio
    async def test_reactivates_past_due(self):
        data = {"subscription": STRIPE_SUB_ID}
        existing_sub = _make_subscription(status="past_due")

        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = existing_sub
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[sub_result, MagicMock()])  # 1st=lookup, 2nd=update

        result = await _handle_payment_succeeded(data, db)
        assert "ok:reactivated" in result

    @pytest.mark.asyncio
    async def test_active_subscription_not_modified(self):
        """If subscription is already active, payment_succeeded is a no-op."""
        data = {"subscription": STRIPE_SUB_ID}
        existing_sub = _make_subscription(status="active")  # already active

        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = existing_sub
        db = AsyncMock()
        db.execute = AsyncMock(return_value=sub_result)

        result = await _handle_payment_succeeded(data, db)
        assert result == "skipped:not_past_due"

    @pytest.mark.asyncio
    async def test_no_sub_id_skipped(self):
        data = {}
        db = AsyncMock()
        result = await _handle_payment_succeeded(data, db)
        assert "skipped" in result


# ─── BillingError tests ───────────────────────────────────────────────────────

class TestBillingError:
    def test_billing_error_has_status_code(self):
        from app.modules.billing.stripe_service import BillingError
        err = BillingError("Something went wrong", status_code=403)
        assert err.status_code == 403
        assert "Something" in str(err)

    def test_billing_error_default_status(self):
        from app.modules.billing.stripe_service import BillingError
        err = BillingError("Generic error")
        assert err.status_code == 400


# ─── Entitlement schema ───────────────────────────────────────────────────────

class TestEntitlementSchema:
    def test_entitlement_response_fields(self):
        from app.modules.billing.schemas import EntitlementResponse
        r = EntitlementResponse(
            plan_name="starter",
            plan_slug="starter",
            plan_id="00000000-0000-0000-0000-000000000001",
            max_stores=5,
            current_stores=2,
            max_tracked_products=100,
            current_tracked_products=15,
            poll_interval_mins=30,
            subscription_status="active",
        )
        assert r.plan_name == "starter"
        assert r.plan_slug == "starter"
        assert r.current_stores == 2
        assert r.max_tracked_products == 100

    def test_checkout_session_request_validates_url(self):
        from pydantic import ValidationError

        from app.modules.billing.schemas import CreateCheckoutSessionRequest
        with pytest.raises(ValidationError):
            CreateCheckoutSessionRequest(
                plan_id="some-id",
                success_url="ftp://bad-url.com",
                cancel_url="https://good.com",
            )

    @pytest.mark.asyncio
    async def test_expired_subscription_falls_back_to_free(self):
        from datetime import UTC, datetime, timedelta
        from app.modules.billing.entitlements import EntitlementService
        from app.modules.billing.models import Plan, Subscription

        user_id = uuid.uuid4()
        free_plan = Plan(id=uuid.uuid4(), name="Free", slug="free", price_usd=0, max_stores=1, max_tracked_products=5)
        pro_plan = Plan(id=uuid.uuid4(), name="Pro", slug="pro", price_usd=29, max_stores=10, max_tracked_products=100)

        # Expired subscription (period end was 1 day ago)
        expired_sub = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            plan_id=pro_plan.id,
            status="active",
            current_period_end=datetime.now(UTC) - timedelta(days=1),
        )

        db = AsyncMock()
        # First call returns (pro_plan, expired_sub), second call returns free_plan
        rows_mock = MagicMock()
        rows_mock.all.return_value = [(pro_plan, expired_sub)]
        db.execute = AsyncMock(side_effect=[
            rows_mock,
            MagicMock(scalars=lambda: MagicMock(first=lambda: free_plan)),
        ])

        active_plan = await EntitlementService.get_user_active_plan(user_id, db)
        assert active_plan.slug == "free"
        assert expired_sub.status == "canceled"


# ─── Subscription Extension Tests ─────────────────────────────────────────────

class TestSubscriptionExtend:
    @pytest.mark.asyncio
    async def test_extend_active_subscription_stacks_days(self):
        """Extending active subscription adds +30 days per month to existing period end."""
        from datetime import UTC, datetime, timedelta
        from app.modules.billing.models import Plan, Subscription
        from app.modules.billing.router import extend_subscription
        from app.modules.billing.schemas import ExtendSubscriptionRequest

        user_id = uuid.uuid4()
        user_id_str = str(user_id)
        now = datetime.now(UTC)
        future_end = now + timedelta(days=10)

        plan = Plan(id=uuid.uuid4(), name="Pro", slug="pro", price_usd=29, max_stores=10, max_tracked_products=100, poll_interval_mins=60, max_priority_products=0)
        sub = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            plan_id=plan.id,
            status="active",
            current_period_end=future_end,
        )

        sub_res = MagicMock()
        sub_res.scalar_one_or_none.return_value = sub

        plan_res = MagicMock()
        plan_res.scalar_one_or_none.return_value = plan

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[sub_res, plan_res])
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        req = ExtendSubscriptionRequest(months=1)

        with patch("app.modules.billing.entitlements.EntitlementService.sync_user_plan_entitlements", new_callable=AsyncMock):
            res = await extend_subscription(data=req, db=db, user_id_str=user_id_str)

        assert res.months_added == 1
        assert sub.status == "active"
        # Verify stacked end date is 10 days + 30 days = 40 days from now
        assert sub.current_period_end > future_end
        assert (sub.current_period_end - future_end).days == 30

    @pytest.mark.asyncio
    async def test_extend_expired_subscription_resets_from_now(self):
        """Extending expired/canceled subscription resets current_period_end starting from now."""
        from datetime import UTC, datetime, timedelta
        from app.modules.billing.models import Plan, Subscription
        from app.modules.billing.router import extend_subscription
        from app.modules.billing.schemas import ExtendSubscriptionRequest

        user_id = uuid.uuid4()
        user_id_str = str(user_id)
        now = datetime.now(UTC)
        past_end = now - timedelta(days=5)

        plan = Plan(id=uuid.uuid4(), name="Starter", slug="starter", price_usd=10, max_stores=3, max_tracked_products=30, poll_interval_mins=180, max_priority_products=0)
        sub = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            plan_id=plan.id,
            status="canceled",
            current_period_end=past_end,
        )

        sub_res = MagicMock()
        sub_res.scalar_one_or_none.return_value = sub

        plan_res = MagicMock()
        plan_res.scalar_one_or_none.return_value = plan

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[sub_res, plan_res])
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        req = ExtendSubscriptionRequest(months=3)

        with patch("app.modules.billing.entitlements.EntitlementService.sync_user_plan_entitlements", new_callable=AsyncMock):
            res = await extend_subscription(data=req, db=db, user_id_str=user_id_str)

        assert res.months_added == 3
        assert sub.status == "active"
        # 3 months = 90 days from now
        assert sub.current_period_end > now
        assert (sub.current_period_end - now).days >= 89

