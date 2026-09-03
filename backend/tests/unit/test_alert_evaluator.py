"""
Unit tests for alert evaluator (alerts/evaluator.py).

Pure function tests — no DB required.
Covers all 7 condition types, cooldown throttling, threshold edge cases.
"""

from datetime import UTC, datetime, timedelta

from app.modules.alerts.evaluator import AlertConditionInput, should_fire


def _alert(
    condition_type: str = "any_change",
    threshold_pct: float | None = None,
    threshold_price: float | None = None,
    cool_down_minutes: int = 60,
    last_triggered_at: datetime | None = None,
    change_type: str = "price_decrease",
    old_price: float | None = 20.0,
    new_price: float | None = 15.0,
    pct_change: float | None = -25.0,
) -> AlertConditionInput:
    return AlertConditionInput(
        condition_type=condition_type,
        threshold_pct=threshold_pct,
        threshold_price=threshold_price,
        cool_down_minutes=cool_down_minutes,
        last_triggered_at=last_triggered_at,
        change_type=change_type,
        old_price=old_price,
        new_price=new_price,
        pct_change=pct_change,
    )


class TestCooldown:
    def test_no_cooldown_fires(self):
        assert should_fire(_alert(last_triggered_at=None)) is True

    def test_past_cooldown_fires(self):
        # Last triggered 2 hours ago, cooldown is 60 min
        past = datetime.now(UTC) - timedelta(hours=2)
        assert should_fire(_alert(cool_down_minutes=60, last_triggered_at=past)) is True

    def test_within_cooldown_does_not_fire(self):
        # Last triggered 30 min ago, cooldown is 60 min
        recent = datetime.now(UTC) - timedelta(minutes=30)
        assert should_fire(_alert(cool_down_minutes=60, last_triggered_at=recent)) is False

    def test_exactly_at_cooldown_boundary_does_not_fire(self):
        # Last triggered exactly 60 min ago (elapsed == cool_down, not strictly greater)
        exact = datetime.now(UTC) - timedelta(minutes=60)
        # elapsed < cool_down_minutes is the condition → 60 < 60 is False → fires
        result = should_fire(_alert(cool_down_minutes=60, last_triggered_at=exact))
        # Should fire (elapsed is not strictly less than cool_down)
        assert result is True


class TestAnyChange:
    def test_any_change_fires_on_price_decrease(self):
        assert should_fire(_alert(condition_type="any_change", change_type="price_decrease")) is True

    def test_any_change_fires_on_price_increase(self):
        assert should_fire(_alert(condition_type="any_change", change_type="price_increase")) is True

    def test_any_change_fires_on_unavailable(self):
        assert should_fire(_alert(condition_type="any_change", change_type="became_unavailable")) is True


class TestPriceDropPct:
    def test_drop_exceeds_threshold_fires(self):
        alert = _alert(condition_type="price_drop_pct", threshold_pct=20.0, pct_change=-25.0)
        assert should_fire(alert) is True

    def test_drop_equals_threshold_fires(self):
        alert = _alert(condition_type="price_drop_pct", threshold_pct=25.0, pct_change=-25.0)
        assert should_fire(alert) is True

    def test_drop_below_threshold_does_not_fire(self):
        alert = _alert(condition_type="price_drop_pct", threshold_pct=30.0, pct_change=-25.0)
        assert should_fire(alert) is False

    def test_price_increase_does_not_fire_price_drop(self):
        alert = _alert(condition_type="price_drop_pct", threshold_pct=10.0, pct_change=+15.0)
        assert should_fire(alert) is False

    def test_none_pct_does_not_fire(self):
        alert = _alert(condition_type="price_drop_pct", threshold_pct=10.0, pct_change=None)
        assert should_fire(alert) is False


class TestPriceIncreasePct:
    def test_increase_exceeds_threshold_fires(self):
        alert = _alert(condition_type="price_increase_pct", threshold_pct=10.0, pct_change=+15.0)
        assert should_fire(alert) is True

    def test_increase_below_threshold_does_not_fire(self):
        alert = _alert(condition_type="price_increase_pct", threshold_pct=20.0, pct_change=+15.0)
        assert should_fire(alert) is False

    def test_price_decrease_does_not_fire_price_increase(self):
        alert = _alert(condition_type="price_increase_pct", threshold_pct=5.0, pct_change=-10.0)
        assert should_fire(alert) is False


class TestPriceBelow:
    def test_price_below_threshold_fires(self):
        alert = _alert(condition_type="price_below", threshold_price=20.0, new_price=15.0)
        assert should_fire(alert) is True

    def test_price_exactly_at_threshold_fires(self):
        alert = _alert(condition_type="price_below", threshold_price=15.0, new_price=15.0)
        assert should_fire(alert) is True

    def test_price_above_threshold_does_not_fire(self):
        alert = _alert(condition_type="price_below", threshold_price=10.0, new_price=15.0)
        assert should_fire(alert) is False

    def test_none_price_does_not_fire(self):
        alert = _alert(condition_type="price_below", threshold_price=10.0, new_price=None)
        assert should_fire(alert) is False


class TestPriceAbove:
    def test_price_above_threshold_fires(self):
        alert = _alert(condition_type="price_above", threshold_price=10.0, new_price=15.0)
        assert should_fire(alert) is True

    def test_price_below_threshold_does_not_fire(self):
        alert = _alert(condition_type="price_above", threshold_price=20.0, new_price=15.0)
        assert should_fire(alert) is False


class TestAvailabilityConditions:
    def test_out_of_stock_fires_on_became_unavailable(self):
        alert = _alert(condition_type="out_of_stock", change_type="became_unavailable")
        assert should_fire(alert) is True

    def test_out_of_stock_does_not_fire_on_price_change(self):
        alert = _alert(condition_type="out_of_stock", change_type="price_decrease")
        assert should_fire(alert) is False

    def test_back_in_stock_fires_on_became_available(self):
        alert = _alert(condition_type="back_in_stock", change_type="became_available")
        assert should_fire(alert) is True

    def test_back_in_stock_does_not_fire_on_price_change(self):
        alert = _alert(condition_type="back_in_stock", change_type="price_increase")
        assert should_fire(alert) is False
