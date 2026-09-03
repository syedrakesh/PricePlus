"""
TrackedProduct ORM model.

Design decisions:
- Links a USER to a DISCOVERED PRODUCT they want to monitor
- UNIQUE(user_id, discovered_product_id) — can't track the same product twice
- is_active flag — soft-delete; allows "untrack" without losing history
  (monitoring stops for inactive records, but snapshots are preserved)
- store_id is denormalized here for efficient queries: "all products tracked
  for store X by user Y" without joining through discovered_products
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TrackedProduct(Base):
    __tablename__ = "tracked_products"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "discovered_product_id",
            name="uq_tracked_products_user_product",
        ),
    )

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
    discovered_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovered_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized for query efficiency
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("competitor_stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<TrackedProduct id={self.id} "
            f"user={self.user_id} product={self.discovered_product_id} "
            f"active={self.is_active}>"
        )
