"""
Monitoring router — read-only endpoints for price history and change events.

Endpoints:
  GET /tracked/{tracked_id}/timeline       unified chronological price history (Phase 6)
  GET /tracked/{tracked_id}/snapshots      raw snapshot list (paginated)
  GET /tracked/{tracked_id}/changes        detected price changes (paginated)
  GET /price-changes                       all recent changes across all tracked products

All endpoints require authentication and enforce ownership.
"""

from datetime import UTC, datetime
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
    TimelineEntry,
    TimelineResponse,
)
from app.modules.tracking.models import TrackedProduct

logger = logging.getLogger(__name__)

from app.modules.monitoring.engine import monitoring_engine

router = APIRouter()


@router.get("/monitoring/engine/status")
async def get_monitoring_engine_status(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
):
    """Return status and telemetry of the background price monitoring engine with user plan info."""
    user_id = uuid.UUID(user_id_str)
    status = monitoring_engine.get_status_dict()

    from app.modules.billing.entitlements import EntitlementService
    user_plan = await EntitlementService.get_user_active_plan(user_id, db)
    plan_poll_interval_mins = user_plan.poll_interval_mins if user_plan else 60

    res = await db.execute(
        select(func.min(TrackedProduct.next_check_at)).where(
            TrackedProduct.user_id == user_id,
            TrackedProduct.is_active.is_(True),
        )
    )
    earliest_next_check = res.scalar()

    now = datetime.now(UTC)
    seconds_until_next_product_check = None
    if earliest_next_check:
        if earliest_next_check.tzinfo is None:
            earliest_next_check = earliest_next_check.replace(tzinfo=UTC)
        seconds_until_next_product_check = max(0, int((earliest_next_check - now).total_seconds()))

    status["user_plan_poll_interval_mins"] = plan_poll_interval_mins
    status["seconds_until_next_product_check"] = seconds_until_next_product_check
    status["earliest_next_check_at"] = earliest_next_check.isoformat() if earliest_next_check else None

    return status


@router.post("/monitoring/engine/trigger")
async def trigger_monitoring_cycle_now(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
):
    """Trigger an immediate price monitoring cycle across all active tracked products."""
    res = await monitoring_engine.trigger_now(db)
    return {
        "message": "Monitoring cycle completed",
        "result": res,
        "engine": monitoring_engine.get_status_dict(),
    }


@router.post("/monitoring/engine/restart")
async def restart_monitoring_engine(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
):
    """Restart the background monitoring service loop and trigger an immediate cycle."""
    engine_status = await monitoring_engine.restart_engine()
    return {
        "message": "Monitoring engine restarted successfully",
        "engine": engine_status,
    }



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


@router.get("/tracked/{tracked_id}/timeline", response_model=TimelineResponse)
async def get_price_timeline(
    tracked_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> TimelineResponse:
    """
    Unified chronological price history for a tracked product. (Phase 6)

    Returns a merged, time-ordered list of:
    - snapshot entries: every price observation (even when unchanged)
    - change entries: markers for detected price/availability changes

    Each entry has a 'kind' field ('snapshot' | 'change') so the UI
    can render snapshots as data points and changes as highlighted events.

    Use this endpoint to render price charts and history timelines.
    The most recent entries come first (newest → oldest).
    """
    user_id = uuid.UUID(user_id_str)
    try:
        tracked_uuid = uuid.UUID(tracked_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tracked product not found") from None

    await _verify_tracked_ownership(tracked_uuid, user_id, db)

    # Load snapshots (latest first)
    snaps_result = await db.execute(
        select(ProductSnapshot)
        .where(ProductSnapshot.tracked_product_id == tracked_uuid)
        .order_by(ProductSnapshot.captured_at.desc())
        .limit(limit)
    )
    snapshots = list(snaps_result.scalars().all())

    # Load price changes in the same window
    min_ts = snapshots[-1].captured_at if snapshots else None
    changes_stmt = (
        select(PriceChange)
        .where(PriceChange.tracked_product_id == tracked_uuid)
        .order_by(PriceChange.detected_at.desc())
        .limit(limit)
    )
    if min_ts is not None:
        changes_stmt = changes_stmt.where(PriceChange.detected_at >= min_ts)

    changes_result = await db.execute(changes_stmt)
    changes = list(changes_result.scalars().all())

    # Build unified timeline: merge and sort by timestamp (newest first)
    entries: list[TimelineEntry] = []

    for snap in snapshots:
        entries.append(TimelineEntry(
            kind="snapshot",
            timestamp=snap.captured_at.isoformat(),
            price=snap.price if snap.price is not None else None,
            currency=snap.currency,
            is_available=snap.is_available,
            change_type=None,
            old_price=None,
            new_price=None,
            pct_change=None,
            error_message=snap.error_message,
            ref_id=str(snap.id),
        ))

    for chg in changes:
        entries.append(TimelineEntry(
            kind="change",
            timestamp=chg.detected_at.isoformat(),
            price=chg.new_price if chg.new_price is not None else None,
            currency=chg.currency,
            is_available=None,
            change_type=chg.change_type,
            old_price=chg.old_price if chg.old_price is not None else None,
            new_price=chg.new_price if chg.new_price is not None else None,
            pct_change=chg.pct_change if chg.pct_change is not None else None,
            error_message=None,
            ref_id=str(chg.id),
        ))

    # Sort newest → oldest
    entries.sort(key=lambda e: e.timestamp, reverse=True)
    entries = entries[:limit]

    # Summary stats
    prices = [e.price for e in entries if e.price is not None and e.kind == "snapshot"]
    return TimelineResponse(
        entries=entries,
        total_snapshots=len(snapshots),
        total_changes=len(changes),
        min_price=min(prices) if prices else None,
        max_price=max(prices) if prices else None,
        latest_price=prices[0] if prices else None,
    )


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
