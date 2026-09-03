"""
Monitoring ORM models: ProductSnapshot, PriceChange.

Design decisions:
- ProductSnapshot: one row per (tracked_product, time) — immutable time series
  Append-only. Never updated. Deleted only by data retention jobs.
- PriceChange: derived record written when a new snapshot shows a different
  price vs the previous snapshot. The source of truth for alerting.
- Numeric(12, 4) for all prices — sufficient precision for any currency.
- Both tables are expected to grow large; store_id + tracked_product_id are
  denormalized to enable efficient per-store queries without deep joins.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProductSnapshot(Base):
    """
    Immutable snapshot of a tracked product's price at a point in time.

    Written by the monitoring Celery task on every successful poll.
    Even if the price hasn't changed, a snapshot is written — this gives
    us a complete history of when prices were last seen.
    """

    __tablename__ = "product_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tracked_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracked_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    discovered_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovered_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized for efficient queries
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    price: Mapped[float | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="Price at the time of this snapshot (None if product unavailable/unreadable)",
    )
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    is_available: Mapped[bool | None] = mapped_column(
        nullable=True,
        comment="None if availability could not be determined",
    )

    # Snapshot metadata
    http_status: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="HTTP status code from the product fetch",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ProductSnapshot tracked={self.tracked_product_id} "
            f"price={self.price} at={self.captured_at}>"
        )


class PriceChange(Base):
    """
    A detected price change for a tracked product.

    Written when a new ProductSnapshot shows a price different from the
    previous snapshot. The 'pct_change' field is pre-computed for efficient
    filtering of large/small changes.

    Used as the source of truth for alert generation (Phase 6).
    """

    __tablename__ = "price_changes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tracked_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracked_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    discovered_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovered_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The two snapshots that produced this change
    from_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )

    old_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    new_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")

    # Pre-computed for filtering: ((new - old) / old) * 100
    pct_change: Mapped[float | None] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="Percentage change: positive = price increase, negative = decrease",
    )

    # Type: 'price_increase' | 'price_decrease' | 'became_unavailable' | 'became_available'
    change_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    # Alert tracking (Phase 6)
    alert_sent: Mapped[bool] = mapped_column(nullable=False, default=False, index=True)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<PriceChange tracked={self.tracked_product_id} "
            f"{self.old_price} → {self.new_price} ({self.change_type})>"
        )
