"""
Billing ORM models: Plan, Subscription.

Design decisions:
- Plans are seeded records, not user-created (admin/migration managed)
- Subscriptions are created/updated via Stripe webhooks
- plan limits (max_stores, max_tracked_products, poll_interval_mins) live in DB
  so they can be changed without code deploys
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    slug: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
    )
    stripe_price_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    max_stores: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
    )
    max_tracked_products: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
    )
    poll_interval_mins: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
        comment="Minimum minutes between monitoring polls",
    )
    max_priority_products: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Max number of priority VIP items allowed",
    )
    price_usd: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Monthly price in USD (0 for free)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    features: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Plan name={self.name!r} max_stores={self.max_stores}>"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id"),
        nullable=False,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        index=True,
        comment="active | canceled | past_due | trialing",
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Subscription user={self.user_id} plan={self.plan_id} status={self.status!r}>"
