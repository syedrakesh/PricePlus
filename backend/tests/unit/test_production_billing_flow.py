"""
Tests for Production Billing Flow (Real-world Stripe Checkout enforcement):
1. Registration with paid plan initializes user on Free plan until payment.
2. Session verification endpoint upgrades subscription upon payment.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import register_user
from app.modules.billing.models import Plan, Subscription
from app.modules.billing.schemas import VerifySessionRequest
from app.modules.billing.router import verify_checkout_session_endpoint


@pytest.mark.asyncio
class TestProductionBillingFlow:
    async def test_register_defaults_to_free_plan_initially(self):
        db = AsyncMock()

        user_role = MagicMock()
        user_role.id = uuid.uuid4()

        free_plan = Plan(
            id=uuid.uuid4(),
            name="Free Plan",
            slug="free",
            price_usd=0.0,
        )
        pro_plan = Plan(
            id=uuid.uuid4(),
            name="Pro Plan",
            slug="pro",
            price_usd=79.0,
            stripe_price_id="price_pro_test123",
        )

        def mock_execute(statement, *args, **kwargs):
            mock_res = MagicMock()
            sql_str = str(statement).lower()
            if "roles" in sql_str:
                mock_res.scalars().first.return_value = user_role
            elif "users" in sql_str:
                mock_res.scalar_one_or_none.return_value = None
            else:
                slug_val = None
                try:
                    params_dict = statement.compile().params
                    slug_val = params_dict.get("slug_1") or params_dict.get("slug")
                except Exception:
                    pass

                if slug_val == "pro":
                    mock_res.scalars().first.return_value = pro_plan
                else:
                    mock_res.scalars().first.return_value = free_plan
                    mock_res.scalar_one_or_none.return_value = free_plan
            return mock_res

        db.execute = AsyncMock(side_effect=mock_execute)

        req = RegisterRequest(
            email="paiduser@example.com",
            password="Password123!",
            full_name="Paid User",
            plan_slug="pro",
        )

        mock_settings = MagicMock()
        mock_settings.stripe_secret_key = "sk_test_live_key_for_test"

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.modules.billing.stripe_service.get_or_create_customer", return_value="cus_test123"), \
             patch("app.modules.billing.stripe_service.create_checkout_session", return_value="https://checkout.stripe.com/pay/cs_test123"):
            res = await register_user(db, req)

        assert res.access_token is None
        assert res.checkout_url == "https://checkout.stripe.com/pay/cs_test123"

        # Verify added subscription is on free_plan
        sub_added = [call[0][0] for call in db.add.call_args_list if isinstance(call[0][0], Subscription)][0]
        assert sub_added.plan_id == free_plan.id

    async def test_verify_session_upgrades_user_subscription(self):
        user_id = uuid.uuid4()
        free_plan_id = uuid.uuid4()
        pro_plan_id = uuid.uuid4()

        pro_plan = Plan(
            id=pro_plan_id,
            name="Pro Plan",
            slug="pro",
            price_usd=79.0,
            stripe_price_id="price_pro_test123",
        )
        existing_sub = Subscription(
            id=uuid.uuid4(),
            user_id=user_id,
            plan_id=free_plan_id,
            status="active",
        )

        mock_session = MagicMock()
        mock_session.payment_status = "paid"
        mock_session.status = "complete"
        mock_session.metadata = {"user_id": str(user_id)}
        mock_session.customer = "cus_test123"
        mock_session.subscription = "sub_test123"
        mock_item = MagicMock()
        mock_item.price.id = "price_pro_test123"
        mock_session.line_items.data = [mock_item]

        mock_db = AsyncMock()

        def mock_execute(statement, *args, **kwargs):
            mock_res = MagicMock()
            sql_str = str(statement)
            if "stripe_price_id" in sql_str or "plans" in sql_str.lower():
                mock_res.scalar_one_or_none.return_value = pro_plan
            elif "subscriptions" in sql_str.lower():
                mock_res.scalar_one_or_none.return_value = existing_sub
            return mock_res

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        with patch("app.modules.billing.router.retrieve_checkout_session", return_value=mock_session), \
             patch("app.modules.billing.entitlements.EntitlementService.sync_user_plan_entitlements", return_value=None):
            req = VerifySessionRequest(session_id="cs_test123")
            res = await verify_checkout_session_endpoint(req, db=mock_db, user_id_str=str(user_id))

        assert res.plan_slug == "pro"
        assert existing_sub.plan_id == pro_plan.id
