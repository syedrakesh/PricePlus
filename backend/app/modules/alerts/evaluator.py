"""
Alert condition evaluator — pure functions.

Given an AlertRule and a PriceChangeEvent, determines if the rule fires.
Separated from DB + email code for easy testing.

Condition type → trigger logic:
  price_drop_pct     → pct_change <= -threshold_pct (price went down enough)
  price_increase_pct → pct_change >= threshold_pct  (price went up enough)
  price_below        → new_price <= threshold_price
  price_above        → new_price >= threshold_price
  any_change         → any PriceChangeEvent (always fires)
  out_of_stock       → change_type == 'became_unavailable'
  back_in_stock      → change_type == 'became_available'
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class AlertConditionInput:
    """Input to the condition evaluator — extracted from AlertRule + PriceChange."""

    condition_type: str
    threshold_pct: float | None
    threshold_price: float | None
    cool_down_minutes: int
    last_triggered_at: datetime | None

    # From the PriceChangeEvent
    change_type: str
    old_price: float | None
    new_price: float | None
    pct_change: float | None


def should_fire(alert: AlertConditionInput) -> bool:
    """
    Return True if the alert rule should fire for this price change event.

    Checks:
    1. Cooldown: if last_triggered_at is within cool_down_minutes, return False
    2. Condition match: check the specific condition against the event
    """
    # Cooldown check
    if alert.last_triggered_at is not None:
        now = datetime.now(UTC)
        last = alert.last_triggered_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        elapsed = (now - last).total_seconds() / 60
        if elapsed < alert.cool_down_minutes:
            logger.debug(
                "Alert on cooldown (%.1f min elapsed, %d min required)",
                elapsed,
                alert.cool_down_minutes,
            )
            return False

    return _matches_condition(alert)


def _matches_condition(alert: AlertConditionInput) -> bool:
    """Return True if the price change matches the alert's condition."""
    ct = alert.condition_type

    if ct == "any_change":
        return True

    if ct == "out_of_stock":
        return alert.change_type == "became_unavailable"

    if ct == "back_in_stock":
        return alert.change_type == "became_available"

    if ct == "price_drop_pct":
        if alert.pct_change is None or alert.threshold_pct is None:
            return False
        return alert.pct_change <= -abs(alert.threshold_pct)

    if ct == "price_increase_pct":
        if alert.pct_change is None or alert.threshold_pct is None:
            return False
        return alert.pct_change >= abs(alert.threshold_pct)

    if ct == "price_below":
        if alert.new_price is None or alert.threshold_price is None:
            return False
        return alert.new_price <= alert.threshold_price

    if ct == "price_above":
        if alert.new_price is None or alert.threshold_price is None:
            return False
        return alert.new_price >= alert.threshold_price

    logger.warning("Unknown alert condition_type: %r", ct)
    return False


def build_trigger_summary(alert: AlertConditionInput, handle: str) -> str:
    """Build a human-readable description of the trigger for notification bodies."""
    ct = alert.condition_type

    if ct in ("price_increase", "price_drop_pct", "price_decrease"):
        pct = f"{alert.pct_change:+.2f}%" if alert.pct_change is not None else ""
        return (
            f"{handle}: price changed {pct} "
            f"(${alert.old_price} → ${alert.new_price})"
        )
    if ct == "out_of_stock":
        return f"{handle}: product is now out of stock"
    if ct == "back_in_stock":
        return f"{handle}: product is back in stock"
    if ct == "price_below":
        return f"{handle}: price dropped to ${alert.new_price} (below ${alert.threshold_price})"
    if ct == "price_above":
        return f"{handle}: price rose to ${alert.new_price} (above ${alert.threshold_price})"
    return f"{handle}: price change detected ({ct})"
