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
