"""
Pydantic schemas for product tracking endpoints.
"""

from pydantic import BaseModel, Field


class TrackProductRequest(BaseModel):
    """Request body for tracking a single discovered product."""

    discovered_product_id: str = Field(
        description="UUID of the discovered product to start tracking"
    )


class TrackMultipleRequest(BaseModel):
    """Request body for tracking multiple discovered products at once."""

    discovered_product_ids: list[str] = Field(
        min_length=1,
        max_length=200,
        description="List of discovered product UUIDs to track (max 200 per request)",
    )


class UpdateTrackedProductRequest(BaseModel):
    """Request body for updating tracked product frequency or priority status."""

    tracking_interval_minutes: int | None = Field(
        default=None, ge=1, description="Custom check interval in minutes (None = reset to user default)"
    )
    is_priority: bool | None = Field(
        default=None, description="Set VIP priority status for high-frequency monitoring"
    )


class TrackedProductResponse(BaseModel):
    """Response schema for a single tracked product."""

    id: str
    user_id: str
    discovered_product_id: str
    store_id: str
    is_active: bool
    tracking_interval_minutes: int | None = None
    is_priority: bool = False
    next_check_at: str | None = None
    created_at: str

    # Enriched product fields (joined from discovered_products)
    handle: str | None = None
    product_url: str | None = None
    title: str | None = None
    current_price: float | None = None
    currency: str | None = None
    image_url: str | None = None

    @classmethod
    def from_orm_model(
        cls,
        tracked: object,
        product: object | None = None,
    ) -> "TrackedProductResponse":
        from app.modules.discovery.models import DiscoveredProduct
        from app.modules.tracking.models import TrackedProduct

        assert isinstance(tracked, TrackedProduct)

        enriched: dict = {}
        if product is not None and isinstance(product, DiscoveredProduct):
            enriched = {
                "handle": product.handle,
                "product_url": product.product_url,
                "title": product.title,
                "current_price": (
                    float(product.current_price)
                    if product.current_price is not None
                    else None
                ),
                "currency": product.currency,
                "image_url": product.image_url,
            }

        return cls(
            id=str(tracked.id),
            user_id=str(tracked.user_id),
            discovered_product_id=str(tracked.discovered_product_id),
            store_id=str(tracked.store_id),
            is_active=tracked.is_active,
            tracking_interval_minutes=tracked.tracking_interval_minutes,
            is_priority=tracked.is_priority,
            next_check_at=tracked.next_check_at.isoformat() if tracked.next_check_at else None,
            created_at=tracked.created_at.isoformat(),
            **enriched,
        )


class TrackedProductListResponse(BaseModel):
    tracked_products: list[TrackedProductResponse]
    total: int
    active_count: int


class TrackAllResponse(BaseModel):
    """Response for 'track all' operation."""

    tracked_count: int
    already_tracked: int
    skipped_limit_reached: int
    message: str


class BulkTrackResponse(BaseModel):
    """Response for bulk tracking multiple specific products."""

    tracked: list[str]
    already_tracked: list[str]
    not_found: list[str]
    limit_reached: bool
    message: str
