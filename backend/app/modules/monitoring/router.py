"""
Monitoring router — read-only endpoints for price history and change events.

Endpoints:
  GET /tracked/{tracked_id}/snapshots      price history (paginated)
  GET /tracked/{tracked_id}/changes        detected price changes (paginated)
  GET /price-changes                       all recent changes across all tracked products

All endpoints require authentication and enforce ownership.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.monitoring.models import PriceChange, ProductSnapshot
from app.modules.monitoring.schemas import (
    PriceChangeListResponse,
    PriceChangeResponse,
    ProductSnapshotResponse,
    SnapshotListResponse,
)
from app.modules.tracking.models import TrackedProduct

logger = logging.getLogger(__name__)

router = APIRouter()


async def _verify_tracked_ownership(
    tracked_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> TrackedProduct:
    result = await db.execute(
        select(TrackedProduct).where(
            TrackedProduct.id == tracked_id,
            TrackedProduct.user_id == user_id,
        )
    )
    tracked = result.scalar_one_or_none()
    if tracked is None:
        raise HTTPException(status_code=404, detail="Tracked product not found")
    return tracked


@router.get("/tracked/{tracked_id}/snapshots", response_model=SnapshotListResponse)
async def list_snapshots(
    tracked_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> SnapshotListResponse:
    """
    List price snapshots for a tracked product (most recent first).

    One snapshot is written per monitoring poll cycle.
    Use this to see the full price history over time.
    """
    user_id = uuid.UUID(user_id_str)
    try:
        tracked_uuid = uuid.UUID(tracked_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tracked product not found") from None

    await _verify_tracked_ownership(tracked_uuid, user_id, db)

    count_result = await db.execute(
        select(func.count()).where(ProductSnapshot.tracked_product_id == tracked_uuid)
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    snaps_result = await db.execute(
        select(ProductSnapshot)
        .where(ProductSnapshot.tracked_product_id == tracked_uuid)
        .order_by(ProductSnapshot.captured_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    snapshots = list(snaps_result.scalars().all())

    return SnapshotListResponse(
        snapshots=[ProductSnapshotResponse.from_orm_model(s) for s in snapshots],
        total=total,
    )


@router.get("/tracked/{tracked_id}/changes", response_model=PriceChangeListResponse)
async def list_price_changes(
    tracked_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> PriceChangeListResponse:
    """
    List all detected price changes for a tracked product (most recent first).

    Only records where price or availability actually changed are returned.
    Use GET /tracked/{id}/snapshots for a complete history including unchanged polls.
    """
    user_id = uuid.UUID(user_id_str)
    try:
        tracked_uuid = uuid.UUID(tracked_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tracked product not found") from None

    await _verify_tracked_ownership(tracked_uuid, user_id, db)

    count_result = await db.execute(
        select(func.count()).where(PriceChange.tracked_product_id == tracked_uuid)
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    changes_result = await db.execute(
        select(PriceChange)
        .where(PriceChange.tracked_product_id == tracked_uuid)
        .order_by(PriceChange.detected_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    changes = list(changes_result.scalars().all())

    return PriceChangeListResponse(
        changes=[PriceChangeResponse.from_orm_model(c) for c in changes],
        total=total,
    )


@router.get("/price-changes", response_model=PriceChangeListResponse)
async def list_all_price_changes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    change_type: str | None = Query(
        default=None,
        description="Filter by change type: price_increase | price_decrease | "
                    "became_unavailable | became_available",
    ),
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> PriceChangeListResponse:
    """
    List all recent price changes across ALL tracked products.

    Useful for a dashboard feed. Filtered to the authenticated user's products.
    Optionally filter by change_type.
    """
    user_id = uuid.UUID(user_id_str)

    base_filter = PriceChange.user_id == user_id
    if change_type is not None:
        base_filter = base_filter & (PriceChange.change_type == change_type)

    count_result = await db.execute(
        select(func.count()).where(base_filter)
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    changes_result = await db.execute(
        select(PriceChange)
        .where(base_filter)
        .order_by(PriceChange.detected_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    changes = list(changes_result.scalars().all())

    return PriceChangeListResponse(
        changes=[PriceChangeResponse.from_orm_model(c) for c in changes],
        total=total,
    )
