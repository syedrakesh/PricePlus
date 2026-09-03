"""
Alert ORM model — user-defined alert rules for price changes.

Design decisions:
- AlertRule: one per (user, tracked_product, condition)
  Conditions: price_drop_pct, price_increase_pct, price_below, price_above,
              any_change, out_of_stock, back_in_stock
- Alert: one record per triggered AlertRule event
  Links to the PriceChange that triggered it
- Delivery channels: email (MVP), webhook (future)
- is_enabled: soft-disable without deleting the rule
- last_triggered_at: throttle alerts (don't spam on every tiny change)
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AlertRule(Base):
    """
    User-defined rule: 'Alert me when [condition] for [tracked_product]'.

    condition_type:
      price_drop_pct     — price dropped by >= threshold_pct %
      price_increase_pct — price increased by >= threshold_pct %
      price_below        — price fell below threshold_price
      price_above        — price rose above threshold_price
      any_change         — any price or availability change
      out_of_stock       — product became unavailable
      back_in_stock      — product became available again
    """

    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tracked_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracked_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    condition_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment=(
            "price_drop_pct | price_increase_pct | price_below | "
            "price_above | any_change | out_of_stock | back_in_stock"
        ),
    )
    threshold_pct: Mapped[float | None] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="Percentage threshold for price_drop_pct / price_increase_pct",
    )
    threshold_price: Mapped[float | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="Absolute price threshold for price_below / price_above",
    )

    # Delivery settings
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="email")
    webhook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Throttling: don't re-alert within cool_down_minutes
    cool_down_minutes: Mapped[int] = mapped_column(nullable=False, default=60)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AlertRule {self.condition_type!r} tracked={self.tracked_product_id}>"


class Alert(Base):
    """
    A triggered alert event — one record per AlertRule fire.

    Links the rule, the price change that triggered it, and delivery status.
    """

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price_change_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("price_changes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Delivery status
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="email")
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Snapshot of what triggered the alert (for the notification body)
    trigger_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description of what changed, stored at trigger time",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<Alert rule={self.alert_rule_id} delivered={self.delivered}>"
