"""
Price change detection logic.

Pure functions — no DB or HTTP calls. Given two price snapshots, returns
a description of what changed. Separated from the monitoring task for testability.

Change types:
  price_increase    — price went up
  price_decrease    — price went down
  became_unavailable — product was available, now isn't
  became_available   — product was unavailable, now is

Design: we treat price=None (fetch failure) as "unknown" and do NOT generate
a price_change event for it — only availability changes are recorded when
price data is missing. This prevents spurious alerts from transient fetch errors.
"""

from dataclasses import dataclass


@dataclass
class SnapshotData:
    """Lightweight representation of a product snapshot for comparison."""

    price: float | None
    is_available: bool | None
    currency: str = "USD"

    def __post_init__(self) -> None:
        if self.price is not None:
            self.price = float(self.price)


@dataclass
class PriceChangeEvent:
    """Represents a detected price change between two snapshots."""

    change_type: str
    """One of: price_increase | price_decrease | became_unavailable | became_available"""

    old_price: float | None
    new_price: float | None
    currency: str
    pct_change: float | None
    """Pre-computed percentage change (positive = increase, negative = decrease)."""

    def __post_init__(self) -> None:
        if self.old_price is not None:
            self.old_price = float(self.old_price)
        if self.new_price is not None:
            self.new_price = float(self.new_price)
        if self.pct_change is not None:
            self.pct_change = float(self.pct_change)


def detect_price_change(
    previous: SnapshotData,
    current: SnapshotData,
) -> PriceChangeEvent | None:
    """
    Compare two snapshots and return a PriceChangeEvent if something changed.

    Returns None if prices are identical (or both None).

    Percentage change is only computed when both prices are valid non-zero numbers.
    Availability changes take precedence over price changes when both happen together —
    separate events would require two alerts, which is noisy.
    """
    # Availability change takes precedence
    if previous.is_available is not None and current.is_available is not None:
        if previous.is_available and not current.is_available:
            return PriceChangeEvent(
                change_type="became_unavailable",
                old_price=previous.price,
                new_price=current.price,
                currency=current.currency,
                pct_change=None,
            )
        if not previous.is_available and current.is_available:
            return PriceChangeEvent(
                change_type="became_available",
                old_price=previous.price,
                new_price=current.price,
                currency=current.currency,
                pct_change=None,
            )

    # Price change — only when both are valid
    if previous.price is None or current.price is None:
        return None

    if previous.price == current.price:
        return None

    pct_change: float | None = None
    if previous.price != 0:
        pct_change = round(
            ((current.price - previous.price) / previous.price) * 100,
            4,
        )

    change_type = "price_increase" if current.price > previous.price else "price_decrease"

    return PriceChangeEvent(
        change_type=change_type,
        old_price=previous.price,
        new_price=current.price,
        currency=current.currency,
        pct_change=pct_change,
    )
