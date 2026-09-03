"""
Pydantic schemas for monitoring endpoints.
"""

from pydantic import BaseModel


class ProductSnapshotResponse(BaseModel):
    id: str
    tracked_product_id: str
    price: float | None
    currency: str
    is_available: bool | None
    http_status: int | None
    error_message: str | None
    captured_at: str

    @classmethod
    def from_orm_model(cls, snap: object) -> "ProductSnapshotResponse":
        from app.modules.monitoring.models import ProductSnapshot
        assert isinstance(snap, ProductSnapshot)
        return cls(
            id=str(snap.id),
            tracked_product_id=str(snap.tracked_product_id),
            price=float(snap.price) if snap.price is not None else None,
            currency=snap.currency,
            is_available=snap.is_available,
            http_status=snap.http_status,
            error_message=snap.error_message,
            captured_at=snap.captured_at.isoformat(),
        )


class PriceChangeResponse(BaseModel):
    id: str
    tracked_product_id: str
    discovered_product_id: str
    old_price: float | None
    new_price: float | None
    currency: str
    pct_change: float | None
    change_type: str
    alert_sent: bool
    detected_at: str

    @classmethod
    def from_orm_model(cls, change: object) -> "PriceChangeResponse":
        from app.modules.monitoring.models import PriceChange
        assert isinstance(change, PriceChange)
        return cls(
            id=str(change.id),
            tracked_product_id=str(change.tracked_product_id),
            discovered_product_id=str(change.discovered_product_id),
            old_price=float(change.old_price) if change.old_price is not None else None,
            new_price=float(change.new_price) if change.new_price is not None else None,
            currency=change.currency,
            pct_change=float(change.pct_change) if change.pct_change is not None else None,
            change_type=change.change_type,
            alert_sent=change.alert_sent,
            detected_at=change.detected_at.isoformat(),
        )


class SnapshotListResponse(BaseModel):
    snapshots: list[ProductSnapshotResponse]
    total: int


class PriceChangeListResponse(BaseModel):
    changes: list[PriceChangeResponse]
    total: int


class TimelineEntry(BaseModel):
    """
    One entry in a unified price timeline.

    kind='snapshot' — a raw price observation (every poll cycle).
    kind='change'   — a detected price/availability change event.

    The UI should render snapshots as chart data points and changes
    as highlighted markers on the timeline.
    """

    kind: str
    """'snapshot' | 'change'"""

    timestamp: str
    """ISO-8601 datetime of the observation or change."""

    price: float | None
    """Current price at this point in time (new_price for changes)."""

    currency: str
    """Currency code, e.g. 'USD'."""

    is_available: bool | None
    """Availability at time of snapshot (None for change entries)."""

    change_type: str | None
    """price_increase | price_decrease | became_unavailable | became_available (change entries only)."""

    old_price: float | None
    """Previous price (change entries only)."""

    new_price: float | None
    """New price (change entries only — same as 'price')."""

    pct_change: float | None
    """Pre-computed percentage change (change entries only)."""

    error_message: str | None
    """Fetch error if the snapshot poll failed (snapshot entries only)."""

    ref_id: str
    """UUID of the underlying ProductSnapshot or PriceChange record."""


class TimelineResponse(BaseModel):
    """Unified price history timeline for one tracked product."""

    entries: list[TimelineEntry]
    """Chronologically sorted entries, newest first."""

    total_snapshots: int
    """Total snapshot entries in this window."""

    total_changes: int
    """Total price change events in this window."""

    min_price: float | None
    """Minimum observed price in this window."""

    max_price: float | None
    """Maximum observed price in this window."""

    latest_price: float | None
    """Most recent observed price."""

