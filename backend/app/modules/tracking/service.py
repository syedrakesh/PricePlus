"""
Tracking service — business logic for product tracking.

All DB queries live here. Routers call service functions only.

Key design decisions:
- Entitlement check counts ALL active tracked products for the user (cross-store)
  so the limit is per-account, not per-store
- "Track all" processes in batches and stops when the limit is reached —
  it does NOT fail the entire operation when the limit is hit mid-way
- Untracking is a soft-delete (is_active=False) to preserve history
- Re-tracking a previously untracked product (is_active=False) reactivates it
  without consuming an extra slot if the limit is hit
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.entitlements import (
    EntitlementError,
    EntitlementService,
    get_max_tracked_products,
)
from app.modules.discovery.models import DiscoveredProduct
from app.modules.stores.models import CompetitorStore
from app.modules.tracking.models import TrackedProduct
from app.modules.tracking.schemas import (
    BulkTrackResponse,
    TrackAllResponse,
)

logger = logging.getLogger(__name__)


class TrackingError(Exception):
    """Domain-level tracking error."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# ─── Queries ──────────────────────────────────────────────────────────────────

async def _count_active_tracked(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Count all active tracked products for a user (across all stores)."""
    result = await db.execute(
        select(func.count()).where(
            TrackedProduct.user_id == user_id,
            TrackedProduct.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one()


async def _assert_store_ownership(
    db: AsyncSession,
    store_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CompetitorStore:
    """Return the store if it belongs to user_id, raise TrackingError 404 or EntitlementError 403 otherwise."""
    result = await db.execute(
        select(CompetitorStore).where(
            CompetitorStore.id == store_id,
            CompetitorStore.user_id == user_id,
        )
    )
    store = result.scalar_one_or_none()
    if store is None:
        raise TrackingError("Store not found", status_code=404)
    if store.status in ("paused", "paused_over_limit"):
        raise EntitlementError(
            f"Cannot track products from store '{store.display_name or store.url}' because it is paused due to plan limits. Please upgrade your plan or manage active stores.",
            status_code=403,
        )
    return store


async def _get_discovered_product(
    db: AsyncSession,
    product_id: uuid.UUID,
    store_id: uuid.UUID,
) -> DiscoveredProduct:
    """Return the product if it belongs to store_id, raise TrackingError 404 otherwise."""
    result = await db.execute(
        select(DiscoveredProduct).where(
            DiscoveredProduct.id == product_id,
            DiscoveredProduct.store_id == store_id,
        )
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise TrackingError("Discovered product not found in this store", status_code=404)
    return product


# ─── Service functions ────────────────────────────────────────────────────────

async def track_product(
    db: AsyncSession,
    user_id: uuid.UUID,
    store_id: uuid.UUID,
    discovered_product_id: uuid.UUID,
) -> TrackedProduct:
    """
    Start tracking a single discovered product.

    Flow:
    1. Verify store ownership
    2. Verify product belongs to this store
    3. Check if already tracked (active) → return existing
    4. Check entitlement (max_tracked_products)
    5. Create or reactivate TrackedProduct

    Raises TrackingError on validation failure.
    Raises EntitlementError when limit is exceeded.
    """
    # Ownership checks
    await _assert_store_ownership(db, store_id, user_id)
    product = await _get_discovered_product(db, discovered_product_id, store_id)

    # Check if already actively tracked
    existing_result = await db.execute(
        select(TrackedProduct).where(
            TrackedProduct.user_id == user_id,
            TrackedProduct.discovered_product_id == discovered_product_id,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        if existing.is_active:
            # Already tracked — return idempotently
            return existing
        else:
            # Was previously untracked — reactivate, but check limit first
            await EntitlementService.check_can_track_product(user_id, db)
            existing.is_active = True
            existing.updated_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(existing)
            logger.info(
                "Re-activated tracked product: user=%s product=%s",
                user_id,
                discovered_product_id,
            )
            return existing

    # New tracking — check entitlement
    await EntitlementService.check_can_track_product(user_id, db)

    tracked = TrackedProduct(
        id=uuid.uuid4(),
        user_id=user_id,
        discovered_product_id=product.id,
        store_id=store_id,
        is_active=True,
    )
    db.add(tracked)
    await db.commit()
    await db.refresh(tracked)

    logger.info(
        "Product tracked: user=%s product=%s store=%s",
        user_id,
        discovered_product_id,
        store_id,
    )
    return tracked


async def track_multiple_products(
    db: AsyncSession,
    user_id: uuid.UUID,
    store_id: uuid.UUID,
    discovered_product_ids: list[uuid.UUID],
) -> BulkTrackResponse:
    """
    Track multiple specific products in one operation.

    Processes each product independently:
    - Already tracked → counts as 'already_tracked'
    - Not found in this store → counts as 'not_found'
    - Limit reached → stops adding, sets limit_reached=True
    - Successfully tracked → added to 'tracked' list

    Returns BulkTrackResponse with per-category lists.
    """
    await _assert_store_ownership(db, store_id, user_id)

    tracked_ids: list[str] = []
    already_tracked_ids: list[str] = []
    not_found_ids: list[str] = []
    limit_reached = False

    current_count = await _count_active_tracked(db, user_id)
    max_products = await get_max_tracked_products(db, user_id)

    if current_count >= max_products:
        await EntitlementService.check_can_track_product(user_id, db)

    for product_id in discovered_product_ids:
        if current_count >= max_products:
            limit_reached = True
            not_found_ids.append(str(product_id))
            continue

        # Check product exists in this store
        product_result = await db.execute(
            select(DiscoveredProduct).where(
                DiscoveredProduct.id == product_id,
                DiscoveredProduct.store_id == store_id,
            )
        )
        product = product_result.scalar_one_or_none()
        if product is None:
            not_found_ids.append(str(product_id))
            continue

        # Check if already tracked
        existing_result = await db.execute(
            select(TrackedProduct).where(
                TrackedProduct.user_id == user_id,
                TrackedProduct.discovered_product_id == product_id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing is not None and existing.is_active:
            already_tracked_ids.append(str(product_id))
            continue

        if existing is not None and not existing.is_active:
            # Reactivate
            existing.is_active = True
            existing.updated_at = datetime.now(UTC)
            tracked_ids.append(str(product_id))
            current_count += 1
        else:
            # Create new
            new_tracked = TrackedProduct(
                id=uuid.uuid4(),
                user_id=user_id,
                discovered_product_id=product_id,
                store_id=store_id,
                is_active=True,
            )
            db.add(new_tracked)
            tracked_ids.append(str(product_id))
            current_count += 1

    await db.commit()

    message = f"Tracked {len(tracked_ids)} product(s)."
    if limit_reached:
        message += f" Plan limit of {max_products} reached — some products were not tracked."

    return BulkTrackResponse(
        tracked=tracked_ids,
        already_tracked=already_tracked_ids,
        not_found=not_found_ids,
        limit_reached=limit_reached,
        message=message,
    )


async def track_all_products(
    db: AsyncSession,
    user_id: uuid.UUID,
    store_id: uuid.UUID,
) -> TrackAllResponse:
    """
    Track ALL discovered products for a store, up to the plan limit.

    Does not fail when the limit is hit — simply stops and reports how many
    were tracked vs skipped. If called when limit is ALREADY hit, raises EntitlementError.

    Returns TrackAllResponse with counts.
    """
    await _assert_store_ownership(db, store_id, user_id)

    # Get all discovered products for this store
    products_result = await db.execute(
        select(DiscoveredProduct)
        .where(DiscoveredProduct.store_id == store_id)
        .order_by(DiscoveredProduct.discovered_at.asc())
    )
    all_products = list(products_result.scalars().all())

    if not all_products:
        return TrackAllResponse(
            tracked_count=0,
            already_tracked=0,
            skipped_limit_reached=0,
            message="No discovered products found for this store. Run discovery first.",
        )

    current_count = await _count_active_tracked(db, user_id)
    max_products = await get_max_tracked_products(db, user_id)

    if current_count >= max_products:
        await EntitlementService.check_can_track_product(user_id, db)

    tracked_count = 0
    already_tracked = 0
    skipped_limit = 0

    # Get all existing tracked product IDs for this user+store (for bulk check)
    existing_result = await db.execute(
        select(TrackedProduct.discovered_product_id, TrackedProduct.is_active).where(
            TrackedProduct.user_id == user_id,
            TrackedProduct.store_id == store_id,
        )
    )
    existing_map: dict[uuid.UUID, bool] = {
        row[0]: row[1] for row in existing_result.all()
    }

    for product in all_products:
        existing_active = existing_map.get(product.id)

        if existing_active is True:
            # Already actively tracked
            already_tracked += 1
            continue

        if current_count >= max_products:
            skipped_limit += 1
            continue

        if existing_active is False:
            # Reactivate
            await db.execute(
                update(TrackedProduct)
                .where(
                    TrackedProduct.user_id == user_id,
                    TrackedProduct.discovered_product_id == product.id,
                )
                .values(is_active=True, updated_at=datetime.now(UTC))
            )
            tracked_count += 1
            current_count += 1
        else:
            # Create new
            db.add(TrackedProduct(
                id=uuid.uuid4(),
                user_id=user_id,
                discovered_product_id=product.id,
                store_id=store_id,
                is_active=True,
            ))
            tracked_count += 1
            current_count += 1

    await db.commit()

    parts = [f"Tracked {tracked_count} product(s)."]
    if already_tracked:
        parts.append(f"{already_tracked} already tracked.")
    if skipped_limit:
        parts.append(
            f"{skipped_limit} skipped — plan limit of {max_products} reached. "
            "Upgrade to track more."
        )

    return TrackAllResponse(
        tracked_count=tracked_count,
        already_tracked=already_tracked,
        skipped_limit_reached=skipped_limit,
        message=" ".join(parts),
    )


async def untrack_product(
    db: AsyncSession,
    user_id: uuid.UUID,
    tracked_product_id: uuid.UUID,
) -> None:
    """
    Stop tracking a product (soft-delete — sets is_active=False).

    Raises TrackingError 404 if not found or not owned by this user.
    """
    result = await db.execute(
        select(TrackedProduct).where(
            TrackedProduct.id == tracked_product_id,
            TrackedProduct.user_id == user_id,
        )
    )
    tracked = result.scalar_one_or_none()
    if tracked is None:
        raise TrackingError("Tracked product not found", status_code=404)

    if not tracked.is_active:
        # Already inactive — idempotent
        return

    tracked.is_active = False
    tracked.updated_at = datetime.now(UTC)
    await db.commit()

    logger.info(
        "Product untracked: user=%s tracked=%s",
        user_id,
        tracked_product_id,
    )


async def list_tracked_products(
    db: AsyncSession,
    user_id: uuid.UUID,
    store_id: uuid.UUID | None = None,
    active_only: bool = True,
) -> list[tuple[TrackedProduct, DiscoveredProduct]]:
    """
    List tracked products for a user, optionally filtered to a specific store.

    Returns a list of (TrackedProduct, DiscoveredProduct) tuples so callers
    can build enriched responses without additional queries.

    Args:
        store_id: If provided, filter to products from this store only.
        active_only: If True, only return is_active=True records.
    """
    stmt = (
        select(TrackedProduct, DiscoveredProduct)
        .join(
            DiscoveredProduct,
            DiscoveredProduct.id == TrackedProduct.discovered_product_id,
        )
        .where(TrackedProduct.user_id == user_id)
        .order_by(TrackedProduct.created_at.desc())
    )

    if store_id is not None:
        stmt = stmt.where(TrackedProduct.store_id == store_id)

    if active_only:
        stmt = stmt.where(
            (TrackedProduct.is_active == True) | (TrackedProduct.status == "paused_over_limit")  # noqa: E712
        )

    result = await db.execute(stmt)
    return list(result.all())


async def get_tracked_product(
    db: AsyncSession,
    user_id: uuid.UUID,
    tracked_product_id: uuid.UUID,
) -> tuple[TrackedProduct, DiscoveredProduct]:
    """
    Get a single tracked product with its discovered product data.
    Raises TrackingError 404 if not found or not owned by this user.
    """
    result = await db.execute(
        select(TrackedProduct, DiscoveredProduct)
        .join(
            DiscoveredProduct,
            DiscoveredProduct.id == TrackedProduct.discovered_product_id,
        )
        .where(
            TrackedProduct.id == tracked_product_id,
            TrackedProduct.user_id == user_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise TrackingError("Tracked product not found", status_code=404)
    return row
