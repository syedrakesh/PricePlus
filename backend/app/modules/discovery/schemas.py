"""
Discovery schemas — request/response models for discovery endpoints.
"""

from pydantic import BaseModel


class TriggerDiscoveryResponse(BaseModel):
    """Response when a discovery run is triggered."""

    discovery_run_id: str
    status: str
    message: str


class DiscoveryRunResponse(BaseModel):
    """Full status of a discovery run."""

    id: str
    store_id: str
    status: str
    triggered_by: str

    total_sitemaps_found: int
    product_sitemaps_found: int
    product_sitemaps_processed: int
    products_discovered: int
    products_created: int
    products_updated: int
    products_failed: int
    products_fetched: int    # How many .json fetches done — used for ETA

    error_message: str | None
    raw_error: str | None = None
    started_at: str
    completed_at: str | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, run: object) -> "DiscoveryRunResponse":
        from app.modules.discovery.models import DiscoveryRun
        assert isinstance(run, DiscoveryRun)
        return cls(
            id=str(run.id),
            store_id=str(run.store_id),
            status=run.status,
            triggered_by=run.triggered_by,
            total_sitemaps_found=run.total_sitemaps_found,
            product_sitemaps_found=run.product_sitemaps_found,
            product_sitemaps_processed=run.product_sitemaps_processed,
            products_discovered=run.products_discovered,
            products_created=run.products_created,
            products_updated=run.products_updated,
            products_failed=run.products_failed,
            products_fetched=run.products_fetched,
            error_message=run.error_message,
            raw_error=getattr(run, "raw_error", None),
            started_at=run.started_at.isoformat(),
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
        )


class DiscoveredProductResponse(BaseModel):
    """A single discovered product."""

    id: str
    store_id: str
    handle: str
    product_url: str
    title: str | None
    current_price: float | None
    compare_at_price: float | None   # Original price; non-None = product is on sale
    currency: str
    is_on_sale: bool
    is_discontinued: bool
    image_url: str | None
    is_tracked: bool = False
    tracking_status: str | None = None
    discovered_at: str
    last_seen_at: str

    @classmethod
    def from_orm_model(
        cls,
        product: object,
        is_tracked: bool = False,
        tracking_status: str | None = None,
    ) -> "DiscoveredProductResponse":
        from app.modules.discovery.models import DiscoveredProduct
        assert isinstance(product, DiscoveredProduct)
        return cls(
            id=str(product.id),
            store_id=str(product.store_id),
            handle=product.handle,
            product_url=product.product_url,
            title=product.title,
            current_price=float(product.current_price) if product.current_price is not None else None,
            compare_at_price=float(product.compare_at_price) if product.compare_at_price is not None else None,
            currency=product.currency,
            is_on_sale=getattr(product, 'is_on_sale', False),
            is_discontinued=getattr(product, 'is_discontinued', False),
            image_url=product.image_url,
            is_tracked=is_tracked,
            tracking_status=tracking_status,
            discovered_at=product.discovered_at.isoformat(),
            last_seen_at=product.last_seen_at.isoformat(),
        )


class DiscoveredProductListResponse(BaseModel):
    products: list[DiscoveredProductResponse]
    total: int
    page: int
    page_size: int
