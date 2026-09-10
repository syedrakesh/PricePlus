"""
Discovery ORM models: DiscoveryRun, DiscoveredProduct.

Design decisions:
- DiscoveryRun tracks the full lifecycle of one discovery operation
  with granular counters so partial failures are observable
- DiscoveredProduct is keyed on (store_id, handle) — handle is the
  canonical Shopify product identifier in /products/{handle}
- raw_data (JSONB) stores the full .json response for future use
  without requiring schema changes
- Products are never deleted when a new discovery run finds them again —
  they are UPSERTED (last_seen_at updated, data refreshed)
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DiscoveryRun(Base):
    """Tracks one full execution of the product discovery pipeline for a store."""

    __tablename__ = "discovery_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("competitor_stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending | running | completed | partial | failed",
    )
    triggered_by: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
        comment="user | scheduler",
    )

    # Progress counters
    total_sitemaps_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    product_sitemaps_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    product_sitemaps_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    products_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    products_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    products_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    products_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<DiscoveryRun id={self.id} store={self.store_id} status={self.status!r}>"


class DiscoveredProduct(Base):
    """
    A product URL discovered via sitemap for a competitor store.

    One record per (store_id, handle). Updated in-place when rediscovered.
    Product data (.json extraction) is stored separately after discovery.
    """

    __tablename__ = "discovered_products"

    __table_args__ = (
        UniqueConstraint("store_id", "handle", name="uq_discovered_products_store_handle"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("competitor_stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    discovery_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovery_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Core identity — handle is the canonical Shopify product key
    handle: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Shopify product handle from /products/{handle}",
    )
    product_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="Normalized canonical product URL",
    )

    # Product data — populated by ProductDataExtractor after discovery
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    current_price: Mapped[float | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="Latest known current/sale price",
    )
    compare_at_price: Mapped[float | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="Original price before sale (Shopify compare_at_price); None if not on sale",
    )
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_on_sale: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True when compare_at_price > current_price",
    )
    is_discontinued: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True when product price is $0.00 (hidden/discontinued by seller)",
    )

    # Sitemap metadata
    sitemap_lastmod: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="<lastmod> value from the sitemap XML",
    )
    sitemap_source: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="Which product sitemap URL this was found in",
    )

    # Full product JSON response (from /products/{handle}.json)
    raw_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    data_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When .json data was last fetched",
    )

    def __repr__(self) -> str:
        return f"<DiscoveredProduct handle={self.handle!r} store={self.store_id}>"
