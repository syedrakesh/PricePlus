"""
Discovery router — HTTP endpoints for triggering and monitoring product discovery.

Endpoints:
  POST /stores/{store_id}/discover
    Trigger a new discovery run for a competitor store.
    Returns 202 Accepted immediately; discovery runs asynchronously via Celery.

  GET /stores/{store_id}/discover/{run_id}
    Poll the status and progress of a discovery run.

  GET /stores/{store_id}/products
    List all discovered products for a store (paginated).

Design:
- Discovery is ALWAYS async (Celery task) — never blocks the HTTP request
- Prevents duplicate concurrent runs (returns existing run if already running)
- Ownership enforced on both store and discovery run
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.discovery.models import DiscoveredProduct, DiscoveryRun
from app.modules.discovery.schemas import (
    DiscoveredProductListResponse,
    DiscoveredProductResponse,
    DiscoveryRunResponse,
    TriggerDiscoveryResponse,
)
from app.modules.stores.models import CompetitorStore

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_owned_store(
    store_id: str,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> CompetitorStore:
    """Get a store and enforce ownership, raising 404 if not found/owned."""
    try:
        store_uuid = uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Store not found") from None

    result = await db.execute(
        select(CompetitorStore).where(
            CompetitorStore.id == store_uuid,
            CompetitorStore.user_id == user_id,
        )
    )
    store = result.scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


async def _run_discovery_bg(run_id: uuid.UUID) -> None:
    from app.core.db import AsyncSessionLocal
    from app.modules.discovery.orchestrator import run_discovery_pipeline

    async with AsyncSessionLocal() as db:
        try:
            await run_discovery_pipeline(db, run_id)
        except Exception as exc:
            logger.exception("Background discovery failed for run %s: %s", run_id, exc)


@router.post("/{store_id}/discover", response_model=TriggerDiscoveryResponse, status_code=202)
async def trigger_discovery(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> TriggerDiscoveryResponse:
    """
    Trigger product discovery for a competitor store.

    Returns 202 Accepted immediately. Discovery runs asynchronously.
    Use GET /stores/{store_id}/discover/{run_id} to poll progress.

    If a discovery run is already in progress for this store, returns
    the existing run rather than starting a duplicate.
    """
    import asyncio
    user_id = uuid.UUID(user_id_str)
    store = await _get_owned_store(store_id, user_id, db)

    # Check for an already-running discovery (prevent duplicate runs)
    existing_result = await db.execute(
        select(DiscoveryRun).where(
            DiscoveryRun.store_id == store.id,
            DiscoveryRun.status.in_(["pending", "running"]),
        )
    )
    existing_run = existing_result.scalar_one_or_none()

    if existing_run is not None:
        from datetime import datetime, UTC
        now = datetime.now(UTC)
        started_at = existing_run.started_at.replace(tzinfo=UTC) if existing_run.started_at.tzinfo is None else existing_run.started_at
        age_seconds = (now - started_at).total_seconds()

        # If existing run is older than 3 minutes, mark it failed so user can restart
        if age_seconds > 180:
            logger.warning("Recovering stuck discovery run %s (age %.0fs)", existing_run.id, age_seconds)
            existing_run.status = "failed"
            existing_run.error_message = "Stuck run timed out"
            existing_run.completed_at = now
            await db.commit()
            existing_run = None
        else:
            logger.info(
                "Discovery already in progress for store %s (run %s)",
                store_id,
                existing_run.id,
            )
            return TriggerDiscoveryResponse(
                discovery_run_id=str(existing_run.id),
                status=existing_run.status,
                message="Discovery is already in progress for this store.",
            )

    # Create a new DiscoveryRun record
    run = DiscoveryRun(
        id=uuid.uuid4(),
        store_id=store.id,
        status="pending",
        triggered_by="user",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Trigger background execution immediately in-process
    asyncio.create_task(_run_discovery_bg(run.id))

    # Also queue via Celery if available
    try:
        from app.workers.discovery_tasks import run_discovery_task
        run_discovery_task.delay(str(run.id))
    except Exception as exc:
        logger.debug("Celery task queueing skipped: %s", exc)

    return TriggerDiscoveryResponse(
        discovery_run_id=str(run.id),
        status="pending",
        message="Discovery started. Use the run ID to poll progress.",
    )



@router.get("/{store_id}/discover/{run_id}", response_model=DiscoveryRunResponse)
async def get_discovery_run(
    store_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> DiscoveryRunResponse:
    """
    Get the status and progress of a discovery run.

    Poll this endpoint after triggering discovery to track progress.
    Typical states: pending → running → completed | partial | failed
    """
    user_id = uuid.UUID(user_id_str)
    store = await _get_owned_store(store_id, user_id, db)

    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Discovery run not found") from None

    result = await db.execute(
        select(DiscoveryRun).where(
            DiscoveryRun.id == run_uuid,
            DiscoveryRun.store_id == store.id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    return DiscoveryRunResponse.from_orm_model(run)


@router.get("/{store_id}/products", response_model=DiscoveredProductListResponse)
async def list_discovered_products(
    store_id: str,
    q: str | None = Query(default=None, description="Search by title or handle"),
    min_price: float | None = Query(default=None, ge=0, description="Minimum price"),
    max_price: float | None = Query(default=None, ge=0, description="Maximum price"),
    is_available: bool | None = Query(default=None, description="Filter by stock availability"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> DiscoveredProductListResponse:
    """
    List products discovered for a competitor store with optional multi-criteria filtering.
    """
    user_id = uuid.UUID(user_id_str)
    store = await _get_owned_store(store_id, user_id, db)

    # Base query
    stmt = select(DiscoveredProduct).where(DiscoveredProduct.store_id == store.id)
    count_stmt = select(func.count()).where(DiscoveredProduct.store_id == store.id)

    # Apply search filter (q)
    if q and q.strip():
        search_pattern = f"%{q.strip()}%"
        q_filter = (DiscoveredProduct.title.ilike(search_pattern)) | (DiscoveredProduct.handle.ilike(search_pattern))
        stmt = stmt.where(q_filter)
        count_stmt = count_stmt.where(q_filter)

    # Apply min_price filter
    if min_price is not None:
        stmt = stmt.where(DiscoveredProduct.current_price >= min_price)
        count_stmt = count_stmt.where(DiscoveredProduct.current_price >= min_price)

    # Apply max_price filter
    if max_price is not None:
        stmt = stmt.where(DiscoveredProduct.current_price <= max_price)
        count_stmt = count_stmt.where(DiscoveredProduct.current_price <= max_price)

    # Apply is_available filter
    if is_available is not None:
        stmt = stmt.where(DiscoveredProduct.is_available == is_available)
        count_stmt = count_stmt.where(DiscoveredProduct.is_available == is_available)

    # Execute count
    count_result = await db.execute(count_stmt)
    total = count_result.scalar_one()

    # Execute pagination
    offset = (page - 1) * page_size
    products_result = await db.execute(
        stmt.order_by(DiscoveredProduct.title.asc().nulls_last(), DiscoveredProduct.handle.asc())
        .offset(offset)
        .limit(page_size)
    )
    products = list(products_result.scalars().all())

    # On-demand hydration for products missing details on this page
    missing_items = [p for p in products if p.current_price is None or p.title is None]
    if missing_items:
        import asyncio
        from app.modules.discovery.fetcher import fetch_product_json
        from app.modules.discovery.orchestrator import _update_product_details
        from app.modules.discovery.product_extractor import extract_product_data

        semaphore = asyncio.Semaphore(5)

        async def hydrate_one(p: DiscoveredProduct) -> None:
            async with semaphore:
                try:
                    raw_json = await fetch_product_json(
                        store_url=store.url,
                        handle=p.handle,
                        rate_limit_delay=0.3,
                    )
                    extracted = extract_product_data(raw_json)
                    await _update_product_details(db, store.id, p.handle, extracted)
                except Exception as exc:
                    logger.debug("On-demand hydration error for %s: %s", p.handle, exc)

        await asyncio.gather(*[hydrate_one(p) for p in missing_items])
        await db.commit()

    # Fetch set of active tracked discovered_product_ids for this user & store
    from app.modules.tracking.models import TrackedProduct

    tracked_result = await db.execute(
        select(TrackedProduct.discovered_product_id).where(
            TrackedProduct.user_id == user_id,
            TrackedProduct.store_id == store.id,
            TrackedProduct.is_active == True,
        )
    )
    tracked_ids = set(tracked_result.scalars().all())

    return DiscoveredProductListResponse(
        products=[
            DiscoveredProductResponse.from_orm_model(p, is_tracked=(p.id in tracked_ids))
            for p in products
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


