"""
Unit tests for price_detector.py.

The price change detector is a pure function — no DB or HTTP required.
Tests cover all change_type variants, None handling, floating point edge cases,
percentage calculation, and the availability > price precedence rule.
"""

import pytest

from app.modules.monitoring.price_detector import (
    SnapshotData,
    detect_price_change,
)


def snap(price: float | None, available: bool | None = True, currency: str = "USD") -> SnapshotData:
    return SnapshotData(price=price, is_available=available, currency=currency)


class TestPriceIncrease:
    def test_simple_price_increase(self):
        event = detect_price_change(snap(10.00), snap(15.00))
        assert event is not None
        assert event.change_type == "price_increase"
        assert event.old_price == pytest.approx(10.00)
        assert event.new_price == pytest.approx(15.00)

    def test_price_increase_pct_calculated(self):
        event = detect_price_change(snap(100.00), snap(150.00))
        assert event is not None
        assert event.pct_change == pytest.approx(50.0)

    def test_small_price_increase(self):
        event = detect_price_change(snap(9.99), snap(10.00))
        assert event is not None
        assert event.change_type == "price_increase"

    def test_price_increase_pct_precision(self):
        """pct_change should be rounded to 4 decimal places."""
        event = detect_price_change(snap(3.00), snap(4.00))
        assert event is not None
        assert event.pct_change == pytest.approx(33.3333, abs=0.001)


class TestPriceDecrease:
    def test_simple_price_decrease(self):
        event = detect_price_change(snap(20.00), snap(15.00))
        assert event is not None
        assert event.change_type == "price_decrease"
        assert event.old_price == pytest.approx(20.00)
        assert event.new_price == pytest.approx(15.00)

    def test_price_decrease_pct_negative(self):
        event = detect_price_change(snap(100.00), snap(75.00))
        assert event is not None
        assert event.pct_change == pytest.approx(-25.0)

    def test_price_decrease_to_zero(self):
        event = detect_price_change(snap(10.00), snap(0.00))
        assert event is not None
        assert event.change_type == "price_decrease"
        assert event.pct_change == pytest.approx(-100.0)


class TestAvailabilityChanges:
    def test_became_unavailable(self):
        event = detect_price_change(snap(10.00, available=True), snap(10.00, available=False))
        assert event is not None
        assert event.change_type == "became_unavailable"
        assert event.pct_change is None  # No pct for availability changes

    def test_became_available(self):
        event = detect_price_change(snap(10.00, available=False), snap(10.00, available=True))
        assert event is not None
        assert event.change_type == "became_available"

    def test_availability_takes_precedence_over_price(self):
        """When BOTH availability and price change, availability wins."""
        event = detect_price_change(
            snap(10.00, available=True),
            snap(15.00, available=False),
        )
        assert event is not None
        assert event.change_type == "became_unavailable"
        # Price change is NOT reported separately — only availability change

    def test_none_availability_no_spurious_event(self):
        """If availability is None in either snapshot, no availability event."""
        event = detect_price_change(snap(10.00, available=None), snap(10.00, available=False))
        # No availability change because previous was None (unknown)
        assert event is None or event.change_type not in ("became_unavailable", "became_available")


class TestNoChange:
    def test_identical_price_returns_none(self):
        assert detect_price_change(snap(19.99), snap(19.99)) is None

    def test_both_prices_none_returns_none(self):
        assert detect_price_change(snap(None), snap(None)) is None

    def test_same_availability_no_change(self):
        assert detect_price_change(snap(10.00, True), snap(10.00, True)) is None


class TestNoneHandling:
    def test_previous_price_none_no_price_event(self):
        """Transient fetch error in previous snapshot → no price change event."""
        event = detect_price_change(snap(None), snap(10.00))
        # Only availability could generate an event (if it changed)
        if event is not None:
            assert event.change_type in ("became_available", "became_unavailable")

    def test_current_price_none_no_price_event(self):
        """Transient fetch error in current snapshot → no price change event."""
        event = detect_price_change(snap(10.00), snap(None))
        # Only availability could generate an event
        if event is not None:
            assert event.change_type in ("became_available", "became_unavailable")


class TestCurrency:
    def test_currency_preserved_in_event(self):
        event = detect_price_change(snap(10.00, currency="EUR"), snap(15.00, currency="EUR"))
        assert event is not None
        assert event.currency == "EUR"


class TestPctChangeEdgeCases:
    def test_from_zero_price_no_pct(self):
        """Division by zero: if old price is 0, pct_change should be None."""
        event = detect_price_change(snap(0.00), snap(10.00))
        assert event is not None
        assert event.change_type == "price_increase"
        assert event.pct_change is None  # 0 denominator → None

    def test_very_small_change(self):
        """Tiny price changes should still be detected."""
        event = detect_price_change(snap(100.0000), snap(100.0001))
        assert event is not None
        assert event.change_type == "price_increase"

    def test_decimal_and_float_comparison(self):
        """Ensure Decimal (from DB column) and float (from JSON) do not raise TypeError."""
        from decimal import Decimal
        prev_snap = SnapshotData(price=Decimal("61.95"), is_available=True)
        curr_snap = SnapshotData(price=61.95, is_available=True)
        assert detect_price_change(prev_snap, curr_snap) is None

        curr_increase = SnapshotData(price=75.00, is_available=True)
        event = detect_price_change(prev_snap, curr_increase)
        assert event is not None
        assert event.change_type == "price_increase"
        assert event.old_price == pytest.approx(61.95)
        assert event.new_price == pytest.approx(75.00)
