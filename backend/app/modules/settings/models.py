"""
User settings ORM model.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    discovery_concurrency: Mapped[int] = mapped_column(
        Integer,
        default=2,
        nullable=False,
        comment="Parallel worker count for product data fetching (1 to 10)",
    )
    discovery_min_delay: Mapped[float] = mapped_column(
        Float,
        default=0.8,
        nullable=False,
        comment="Minimum delay between requests in seconds",
    )
    discovery_max_delay: Mapped[float] = mapped_column(
        Float,
        default=1.5,
        nullable=False,
        comment="Maximum delay between requests in seconds",
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
        return (
            f"<UserSettings user_id={self.user_id} "
            f"concurrency={self.discovery_concurrency} "
            f"delay={self.discovery_min_delay}-{self.discovery_max_delay}s>"
        )
