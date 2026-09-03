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

    # Queue the Celery task (fire and forget)
    try:
        from app.workers.discovery_tasks import run_discovery_task
        run_discovery_task.delay(str(run.id))
        logger.info(
            "Discovery task queued: store=%s run=%s",
            store_id,
            run.id,
        )
    except Exception as exc:
        # If Celery is unavailable, mark run as failed immediately
        logger.error("Failed to queue discovery task: %s", exc)
        run.status = "failed"
        run.error_message = f"Failed to queue discovery task: {exc}"
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Discovery service is temporarily unavailable. Please try again shortly.",
        ) from exc

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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> DiscoveredProductListResponse:
    """
    List all products discovered for a competitor store.

    Paginated. Returns products ordered by title (then handle as fallback).
    """
    user_id = uuid.UUID(user_id_str)
    store = await _get_owned_store(store_id, user_id, db)

    # Count
    count_result = await db.execute(
        select(func.count()).where(DiscoveredProduct.store_id == store.id)
    )
    total = count_result.scalar_one()

    # Fetch page
    offset = (page - 1) * page_size
    products_result = await db.execute(
        select(DiscoveredProduct)
        .where(DiscoveredProduct.store_id == store.id)
        .order_by(DiscoveredProduct.title.asc().nulls_last(), DiscoveredProduct.handle.asc())
        .offset(offset)
        .limit(page_size)
    )
    products = list(products_result.scalars().all())

    return DiscoveredProductListResponse(
        products=[DiscoveredProductResponse.from_orm_model(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
    )
