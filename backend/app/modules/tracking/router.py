"""
Tracking router — HTTP endpoints for product selection and tracking.

URL structure (nested under /stores/{store_id}):
  POST   /stores/{store_id}/track           track a single product
  POST   /stores/{store_id}/track/bulk      track multiple products
  POST   /stores/{store_id}/track/all       track all discovered products
  GET    /stores/{store_id}/tracked         list tracked products for this store
  DELETE /tracked/{tracked_id}              untrack (not store-scoped)

Plus a cross-store view:
  GET    /tracked                            list ALL tracked products (all stores)
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.billing.entitlements import EntitlementError, EntitlementService
from app.modules.tracking.schemas import (
    BulkTrackResponse,
    TrackAllResponse,
    TrackedProductListResponse,
    TrackedProductResponse,
    TrackMultipleRequest,
    TrackProductRequest,
    UpdateTrackedProductRequest,
)
from app.modules.tracking.service import (
    TrackingError,
    get_tracked_product,
    list_tracked_products,
    track_all_products,
    track_multiple_products,
    track_product,
    untrack_product,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _handle_tracking_error(e: TrackingError) -> None:
    raise HTTPException(status_code=e.status_code, detail=str(e))


def _handle_entitlement_error(e: EntitlementError) -> None:
    raise HTTPException(status_code=e.status_code, detail=str(e))


def _parse_uuid(value: str, label: str = "ID") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"{label} not found") from None


@router.post("/track", response_model=TrackedProductResponse, status_code=201)
async def track_single_product_direct(
    data: TrackProductRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> TrackedProductResponse:
    """
    Start tracking a discovered product directly by discovered_product_id.
    Automatically resolves store_id from discovered_products table.
    """
    from sqlalchemy import select
    from app.modules.discovery.models import DiscoveredProduct

    user_id = _parse_uuid(user_id_str, "User")
    product_uuid = _parse_uuid(data.discovered_product_id, "Product")

    # Resolve store_id from discovered_products table
    result = await db.execute(
        select(DiscoveredProduct.store_id).where(DiscoveredProduct.id == product_uuid)
    )
    store_id = result.scalar_one_or_none()
    if store_id is None:
        raise HTTPException(status_code=404, detail="Discovered product not found")

    try:
        tracked = await track_product(db, user_id, store_id, product_uuid)
    except TrackingError as e:
        _handle_tracking_error(e)
    except EntitlementError as e:
        _handle_entitlement_error(e)

    try:
        tracked_obj, product_obj = await get_tracked_product(db, user_id, tracked.id)
    except TrackingError:
        return TrackedProductResponse.from_orm_model(tracked)

    return TrackedProductResponse.from_orm_model(tracked_obj, product_obj)


# ─── Per-store tracking endpoints ─────────────────────────────────────────────

@router.post("/stores/{store_id}/track", response_model=TrackedProductResponse, status_code=201)
async def track_single_product(
    store_id: str,
    data: TrackProductRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> TrackedProductResponse:
    """
    Start tracking a discovered product.

    - Idempotent: if already tracked, returns the existing record (201)
    - Returns 403 if the user's plan limit is reached
    - Returns 404 if the product or store is not found / not owned
    """
    user_id = _parse_uuid(user_id_str, "User")
    store_uuid = _parse_uuid(store_id, "Store")
    product_uuid = _parse_uuid(data.discovered_product_id, "Product")

    try:
        tracked = await track_product(db, user_id, store_uuid, product_uuid)
    except TrackingError as e:
        _handle_tracking_error(e)
    except EntitlementError as e:
        _handle_entitlement_error(e)

    # Fetch enriched data
    try:
        tracked_obj, product_obj = await get_tracked_product(db, user_id, tracked.id)
    except TrackingError:
        return TrackedProductResponse.from_orm_model(tracked)

    return TrackedProductResponse.from_orm_model(tracked_obj, product_obj)


@router.post("/stores/{store_id}/track/bulk", response_model=BulkTrackResponse, status_code=200)
async def track_multiple(
    store_id: str,
    data: TrackMultipleRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> BulkTrackResponse:
    """
    Track multiple specific discovered products in one call.

    Returns per-product status:
    - tracked: successfully started tracking
    - already_tracked: was already being tracked
    - not_found: product ID not found in this store (or limit reached)
    - limit_reached: plan limit was hit before all products were processed
    """
    user_id = _parse_uuid(user_id_str, "User")
    store_uuid = _parse_uuid(store_id, "Store")
    product_uuids = [_parse_uuid(pid, "Product") for pid in data.discovered_product_ids]

    try:
        return await track_multiple_products(db, user_id, store_uuid, product_uuids)
    except TrackingError as e:
        _handle_tracking_error(e)


@router.post("/stores/{store_id}/track/all", response_model=TrackAllResponse, status_code=200)
async def track_all(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> TrackAllResponse:
    """
    Track ALL discovered products for this competitor store.

    Tracks up to your plan's max_tracked_products limit.
    Does NOT return an error when the limit is hit — reports how many
    were tracked vs skipped.

    Requires discovery to have been run first.
    """
    user_id = _parse_uuid(user_id_str, "User")
    store_uuid = _parse_uuid(store_id, "Store")

    try:
        return await track_all_products(db, user_id, store_uuid)
    except TrackingError as e:
        _handle_tracking_error(e)


@router.get("/stores/{store_id}/tracked", response_model=TrackedProductListResponse)
async def list_tracked_for_store(
    store_id: str,
    active_only: bool = Query(default=True, description="Only return active tracked products"),
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> TrackedProductListResponse:
    """
    List all tracked products for a specific competitor store.

    Includes enriched product data (title, price, availability, image).
    """
    user_id = _parse_uuid(user_id_str, "User")
    store_uuid = _parse_uuid(store_id, "Store")

    rows = await list_tracked_products(db, user_id, store_id=store_uuid, active_only=active_only)
    items = [TrackedProductResponse.from_orm_model(t, p) for t, p in rows]

    return TrackedProductListResponse(
        tracked_products=items,
        total=len(items),
        active_count=sum(1 for item in items if item.is_active),
    )


# ─── Cross-store endpoints ─────────────────────────────────────────────────────

@router.get("/tracked", response_model=TrackedProductListResponse)
async def list_all_tracked(
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> TrackedProductListResponse:
    """
    List ALL tracked products for the authenticated user across all stores.
    """
    user_id = _parse_uuid(user_id_str, "User")
    rows = await list_tracked_products(db, user_id, store_id=None, active_only=active_only)
    items = [TrackedProductResponse.from_orm_model(t, p) for t, p in rows]

    return TrackedProductListResponse(
        tracked_products=items,
        total=len(items),
        active_count=sum(1 for item in items if item.is_active),
    )


@router.get("/tracked/{tracked_id}", response_model=TrackedProductResponse)
async def get_single_tracked(
    tracked_id: str,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> TrackedProductResponse:
    """Get a single tracked product by its tracking record ID."""
    user_id = _parse_uuid(user_id_str, "User")
    tracked_uuid = _parse_uuid(tracked_id, "Tracked product")

    try:
        tracked_obj, product_obj = await get_tracked_product(db, user_id, tracked_uuid)
    except TrackingError as e:
        _handle_tracking_error(e)

    return TrackedProductResponse.from_orm_model(tracked_obj, product_obj)


@router.patch("/tracked/{tracked_id}", response_model=TrackedProductResponse)
async def update_single_tracked(
    tracked_id: str,
    data: UpdateTrackedProductRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> TrackedProductResponse:
    """Update custom tracking frequency or VIP priority status for a tracked product."""
    from datetime import UTC, datetime, timedelta
    user_id = _parse_uuid(user_id_str, "User")
    tracked_uuid = _parse_uuid(tracked_id, "Tracked product")

    tracked_obj, product_obj = await get_tracked_product(db, user_id, tracked_uuid)

    if data.tracking_interval_minutes is not None:
        await EntitlementService.check_can_set_interval(user_id, data.tracking_interval_minutes, db)
        tracked_obj.tracking_interval_minutes = data.tracking_interval_minutes
        tracked_obj.next_check_at = datetime.now(UTC) + timedelta(minutes=data.tracking_interval_minutes)

    if data.is_priority is not None and data.is_priority != tracked_obj.is_priority:
        if data.is_priority:
            await EntitlementService.check_can_set_priority(user_id, db)
        tracked_obj.is_priority = data.is_priority

    tracked_obj.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(tracked_obj)

    return TrackedProductResponse.from_orm_model(tracked_obj, product_obj)


@router.delete("/tracked/{tracked_id}", status_code=204)
async def untrack_single_product(
    tracked_id: str,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> None:
    """
    Stop tracking a product (soft-delete).

    Returns 204 No Content on success.
    Idempotent: untracking an already-untracked product returns 204.
    """
    user_id = _parse_uuid(user_id_str, "User")
    tracked_uuid = _parse_uuid(tracked_id, "Tracked product")

    try:
        await untrack_product(db, user_id, tracked_uuid)
    except TrackingError as e:
        _handle_tracking_error(e)
