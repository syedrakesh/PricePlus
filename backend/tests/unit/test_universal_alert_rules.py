"""
Tests for Universal Account-Wide Alert Rules (Option A):
- Creating rules with tracked_product_id = None (Universal Rules)
- Dispatching alerts when price changes occur on any product owned by user
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from datetime import UTC, datetime
from app.modules.alerts.models import AlertRule, Alert
from app.modules.alerts.schemas import CreateAlertRuleRequest, AlertRuleResponse
from app.modules.alerts.dispatcher import _process_one_change
from app.modules.monitoring.models import PriceChange
from app.modules.tracking.models import TrackedProduct
from app.modules.discovery.models import DiscoveredProduct


class TestUniversalAlertRuleSchemas:
    def test_create_universal_rule_request(self):
        req = CreateAlertRuleRequest(
            tracked_product_id=None,
            condition_type="price_drop_pct",
            threshold_pct=5.0,
            channel="email",
        )
        assert req.tracked_product_id is None
        assert req.condition_type == "price_drop_pct"
        assert req.threshold_pct == 5.0

    def test_alert_rule_response_from_orm_with_null_tracked_product(self):
        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            tracked_product_id=None,
            condition_type="price_drop_pct",
            threshold_pct=10.0,
            threshold_price=None,
            channel="email",
            webhook_url=None,
            is_enabled=True,
            cool_down_minutes=60,
            last_triggered_at=None,
            created_at=datetime.now(UTC),
        )
        resp = AlertRuleResponse.from_orm_model(rule)
        assert resp.tracked_product_id is None
        assert resp.condition_type == "price_drop_pct"
        assert resp.threshold_pct == 10.0


@pytest.mark.asyncio
class TestUniversalAlertDispatcher:
    async def test_universal_rule_triggers_for_any_product(self):
        user_id = uuid.uuid4()
        prod1_id = uuid.uuid4()
        disc1_id = uuid.uuid4()

        # Universal rule owned by user_id with tracked_product_id = None
        universal_rule = AlertRule(
            id=uuid.uuid4(),
            user_id=user_id,
            tracked_product_id=None,
            condition_type="price_drop_pct",
            threshold_pct=5.0,
            threshold_price=None,
            channel="email",
            webhook_url=None,
            is_enabled=True,
            cool_down_minutes=60,
            last_triggered_at=None,
        )

        tracked1 = TrackedProduct(
            id=prod1_id,
            user_id=user_id,
            discovered_product_id=disc1_id,
        )
        disc1 = DiscoveredProduct(
            id=disc1_id,
            handle="test-product-1",
            title="Test Product 1",
        )
        change1 = PriceChange(
            id=uuid.uuid4(),
            tracked_product_id=prod1_id,
            discovered_product_id=disc1_id,
            change_type="price_decrease",
            old_price=100.0,
            new_price=90.0,
            pct_change=-10.0,
            alert_sent=False,
        )

        mock_db = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [universal_rule]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        with patch("app.modules.alerts.dispatcher._dispatch_notification", return_value=(True, None)):
            dispatched = await _process_one_change(mock_db, change1, tracked1, disc1)

        assert dispatched == 1
        assert mock_db.add.called
        fired_alert = mock_db.add.call_args[0][0]
        assert isinstance(fired_alert, Alert)
        assert fired_alert.alert_rule_id == universal_rule.id


@pytest.mark.asyncio
class TestDuplicateAlertRulePrevention:
    async def test_duplicate_active_rule_raises_http_exception(self):
        from fastapi import HTTPException
        from app.modules.alerts.router import create_alert_rule

        user_id = uuid.uuid4()
        existing_rule = AlertRule(
            id=uuid.uuid4(),
            user_id=user_id,
            tracked_product_id=None,
            condition_type="price_drop_pct",
            threshold_pct=5.0,
            is_enabled=True,
            created_at=datetime.now(UTC),
        )

        mock_db = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = existing_rule
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        req = CreateAlertRuleRequest(
            tracked_product_id=None,
            condition_type="price_drop_pct",
            threshold_pct=5.0,
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_alert_rule(data=req, db=mock_db, user_id_str=str(user_id))

        assert exc_info.value.status_code == 400
        assert "identical alert rule already exists" in exc_info.value.detail.lower()

    async def test_duplicate_paused_rule_is_re_enabled(self):
        from app.modules.alerts.router import create_alert_rule

        user_id = uuid.uuid4()
        existing_rule = AlertRule(
            id=uuid.uuid4(),
            user_id=user_id,
            tracked_product_id=None,
            condition_type="price_drop_pct",
            threshold_pct=5.0,
            channel="email",
            cool_down_minutes=60,
            is_enabled=False,
            created_at=datetime.now(UTC),
        )

        mock_db = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = existing_rule
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        req = CreateAlertRuleRequest(
            tracked_product_id=None,
            condition_type="price_drop_pct",
            threshold_pct=5.0,
        )

        resp = await create_alert_rule(data=req, db=mock_db, user_id_str=str(user_id))
        assert existing_rule.is_enabled is True
        assert resp.is_enabled is True

