"""
Monitoring orchestrator — polls tracked products and detects price changes.

Pipeline for each poll cycle:
1. Load all active TrackedProducts (with their DiscoveredProduct joined)
2. For each tracked product:
   a. Fetch /products/{handle}.json from the competitor store
   b. Extract price and availability
   c. Write a ProductSnapshot
   d. Compare to the most recent previous snapshot
   e. If changed → write a PriceChange record
3. Update DiscoveredProduct.current_price (denormalized cache)

Concurrency:
- Uses asyncio.Semaphore to limit concurrent HTTP requests
- Processes all tracked products across all users in one batch
  (The Celery beat task calls this for the whole system, not per-user)

Failure handling:
- HTTP failure for one product does NOT abort others
- Failures write a snapshot with error_message (so we have a record)
- Consecutive fetch failures are logged but not escalated yet (Phase 6)
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User  # noqa: F401
from app.modules.discovery.fetcher import FetchError, fetch_product_json
from app.modules.discovery.models import DiscoveredProduct
from app.modules.discovery.product_extractor import extract_product_data
from app.modules.monitoring.models import PriceChange, ProductSnapshot
from app.modules.monitoring.price_detector import SnapshotData, detect_price_change
from app.modules.stores.models import CompetitorStore  # noqa: F401
from app.modules.tracking.models import TrackedProduct

logger = logging.getLogger(__name__)

_POLL_CONCURRENCY = 10  # Max concurrent product fetches


async def run_monitoring_cycle(db: AsyncSession, force_all: bool = False) -> dict:
    """
    Run one full monitoring cycle: poll active tracked products.
    If force_all is True, polls ALL active tracked products immediately (e.g. manual trigger).
    Otherwise, polls active products that are due for check (next_check_at <= now OR next_check_at IS NULL).
    """
    now = datetime.now(UTC)

    stmt = (
        select(TrackedProduct, DiscoveredProduct)
        .join(DiscoveredProduct, DiscoveredProduct.id == TrackedProduct.discovered_product_id)
        .join(CompetitorStore, CompetitorStore.id == TrackedProduct.store_id)
        .where(
            TrackedProduct.is_active.is_(True),
            CompetitorStore.status == "active",
        )
    )
    if not force_all:
        stmt = stmt.where(
            (TrackedProduct.next_check_at.is_(None)) | (TrackedProduct.next_check_at <= now)
        )

    rows = await db.execute(stmt)
    active_tracked = list(rows.all())

    if not active_tracked:
        logger.info("Monitoring cycle: no active tracked products due for poll")
        return {"polled": 0, "changes": 0, "errors": 0}

    logger.info("Monitoring cycle: polling %d active tracked products", len(active_tracked))

    semaphore = asyncio.Semaphore(_POLL_CONCURRENCY)
    polled = 0
    changes = 0
    errors = 0

    results = await asyncio.gather(
        *[
            _poll_one_product(semaphore, tracked.id, discovered.id)
            for tracked, discovered in active_tracked
        ],
        return_exceptions=True,
    )

    for result in results:
        if isinstance(result, Exception):
            logger.exception("Unexpected error in poll: %s", result)
            errors += 1
        elif isinstance(result, dict):
            polled += 1
            if result.get("changed"):
                changes += 1
            if result.get("error"):
                errors += 1

    logger.info(
        "Monitoring cycle complete: polled=%d changes=%d errors=%d",
        polled,
        changes,
        errors,
    )
    return {"polled": polled, "changes": changes, "errors": errors}


async def _poll_one_product(
    semaphore: asyncio.Semaphore,
    tracked_id: uuid.UUID,
    discovered_id: uuid.UUID,
) -> dict:
    """
    Poll a single tracked product in an isolated DB session, write snapshot, detect changes.
    Returns {'changed': bool, 'error': bool}.
    """
    async with semaphore:
        from app.core.db import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            stmt = (
                select(TrackedProduct, DiscoveredProduct)
                .join(DiscoveredProduct, DiscoveredProduct.id == TrackedProduct.discovered_product_id)
                .where(TrackedProduct.id == tracked_id)
            )
            res = await db.execute(stmt)
            row = res.one_or_none()
            if not row:
                return {"changed": False, "error": True}
            tracked, discovered = row

            try:
                result = await _do_poll(db, tracked, discovered)
                await db.commit()
                return result
            except Exception as exc:
                await db.rollback()
                logger.exception("Polling failed with exception for %s: %s", discovered.handle, exc)
                from urllib.parse import urlparse
                parsed = urlparse(discovered.product_url or "")
                from app.modules.monitoring.telemetry import worker_telemetry
                worker_telemetry.record_event(
                    action="ERROR",
                    product_title=discovered.title or discovered.handle or "Unknown Product",
                    store_domain=parsed.netloc or "Store",
                    price=None,
                    status_code=500,
                    latency_ms=0,
                    user_id=str(tracked.user_id),
                    details=f"Uncaught Exception: {type(exc).__name__} — {str(exc)}",
                )
                return {"changed": False, "error": True}


async def _do_poll(
    db: AsyncSession,
    tracked: TrackedProduct,
    discovered: DiscoveredProduct,
) -> dict:
    """Execute one poll: fetch → snapshot → detect → optionally write PriceChange."""
    now = datetime.now(UTC)

    # Determine store URL from the product URL
    from urllib.parse import urlparse
    parsed = urlparse(discovered.product_url or "")
    store_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else discovered.product_url

    # Fetch product data
    json_data = None
    http_status: int | None = None
    error_message: str | None = None
    extracted = None

    # Load user speed settings for randomized jitter request delay
    import random
    from app.modules.settings.models import UserSettings
    us_res = await db.execute(
        select(UserSettings).where(UserSettings.user_id == tracked.user_id)
    )
    u_settings = us_res.scalar_one_or_none()
    min_d = u_settings.tracking_min_delay if u_settings else 0.2
    max_d = u_settings.tracking_max_delay if u_settings else 0.5
    req_delay = random.uniform(min_d, max_d)

    start_t = datetime.now(UTC)
    try:
        json_data = await fetch_product_json(
            store_url=store_url,
            handle=discovered.handle,
            rate_limit_delay=req_delay,
        )
        if json_data is not None:
            extracted = extract_product_data(json_data)
            http_status = 200
            if extracted is None:
                error_message = "Product data parser returned None"
            elif extracted.price is None:
                error_message = "Price extraction returned null (HTML structure changed or price selector missing)"
        else:
            http_status = 404
            error_message = "Product JSON returned None (404 or unavailable)"
    except FetchError as exc:
        http_status = exc.status_code
        error_message = str(exc)
        logger.warning(
            "Fetch error for %s (tracked=%s): %s",
            discovered.handle,
            tracked.id,
            exc,
        )
    except Exception as exc:
        http_status = 500
        error_message = f"Fetch exception: {type(exc).__name__} — {str(exc)}"
        logger.exception("Unexpected fetch exception for %s: %s", discovered.handle, exc)

    latency_ms = int((datetime.now(UTC) - start_t).total_seconds() * 1000)

    # Build current snapshot data
    if extracted is not None:
        current = SnapshotData(
            price=extracted.price,
            is_available=True,
            currency=extracted.currency,
        )
    else:
        current = SnapshotData(price=None, is_available=None)

    from app.modules.monitoring.telemetry import worker_telemetry
    worker_telemetry.record_event(
        action="PULLED" if not error_message else "ERROR",
        product_title=discovered.title or discovered.handle,
        store_domain=parsed.netloc,
        price=current.price,
        status_code=http_status or (200 if not error_message else 500),
        latency_ms=latency_ms,
        user_id=str(tracked.user_id),
        details=error_message or (f"Price: ${current.price}" if current.price is not None else "Fetched"),
    )

    # Write the snapshot
    snapshot = ProductSnapshot(
        id=uuid.uuid4(),
        tracked_product_id=tracked.id,
        discovered_product_id=discovered.id,
        user_id=tracked.user_id,
        price=current.price,
        currency=current.currency,
        is_available=True,
        http_status=http_status,
        error_message=error_message,
        captured_at=now,
    )
    db.add(snapshot)

    # Calculate next_check_at using the user's active plan poll_interval_mins
    from datetime import timedelta
    from app.modules.billing.entitlements import EntitlementService

    interval_mins = await EntitlementService.get_user_poll_interval_mins(tracked.user_id, db)

    tracked.next_check_at = now + timedelta(minutes=interval_mins)
    tracked.tracking_interval_minutes = None

    # Load previous snapshot for comparison
    prev_result = await db.execute(
        select(ProductSnapshot)
        .where(
            ProductSnapshot.tracked_product_id == tracked.id,
            ProductSnapshot.id != snapshot.id,
        )
        .order_by(ProductSnapshot.captured_at.desc())
        .limit(1)
    )
    prev_snapshot = prev_result.scalar_one_or_none()

    changed = False

    # Determine baseline previous price (from prev snapshot or discovered.current_price)
    previous_price: float | None = None
    if prev_snapshot is not None and prev_snapshot.price is not None:
        previous_price = float(prev_snapshot.price)
    elif discovered.current_price is not None:
        previous_price = float(discovered.current_price)

    if previous_price is not None and error_message is None:
        previous = SnapshotData(
            price=previous_price,
            is_available=True,
            currency=discovered.currency or "USD",
        )
        event = detect_price_change(previous, current)

        if event is not None:
            price_change = PriceChange(
                id=uuid.uuid4(),
                tracked_product_id=tracked.id,
                discovered_product_id=discovered.id,
                user_id=tracked.user_id,
                from_snapshot_id=prev_snapshot.id if prev_snapshot else None,
                to_snapshot_id=snapshot.id,
                old_price=event.old_price,
                new_price=event.new_price,
                currency=event.currency,
                pct_change=event.pct_change,
                change_type=event.change_type,
                alert_sent=False,
                detected_at=now,
            )
            db.add(price_change)
            changed = True
            logger.info(
                "Price change detected: %s %s→%s (%.2f%%) for %s",
                event.change_type,
                event.old_price,
                event.new_price,
                event.pct_change or 0.0,
                discovered.handle,
            )

    # Update denormalized current_price on DiscoveredProduct
    if extracted is not None:
        await db.execute(
            update(DiscoveredProduct)
            .where(DiscoveredProduct.id == discovered.id)
            .values(
                current_price=extracted.price,
                compare_at_price=extracted.compare_at_price,
                currency=extracted.currency,
                is_on_sale=extracted.is_on_sale,
                is_discontinued=extracted.is_discontinued,
                data_fetched_at=now,
            )
        )

    return {"changed": changed, "error": error_message is not None}
