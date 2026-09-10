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

from app.modules.discovery.fetcher import FetchError, fetch_product_json
from app.modules.discovery.models import DiscoveredProduct
from app.modules.discovery.product_extractor import extract_product_data
from app.modules.monitoring.models import PriceChange, ProductSnapshot
from app.modules.monitoring.price_detector import SnapshotData, detect_price_change
from app.modules.tracking.models import TrackedProduct

logger = logging.getLogger(__name__)

_POLL_CONCURRENCY = 10  # Max concurrent product fetches


async def run_monitoring_cycle(db: AsyncSession) -> dict:
    """
    Run one full monitoring cycle: poll all active tracked products.

    Returns a summary dict with counts for observability.
    Called by the Celery beat task periodically.
    """
    # Load all active tracked products with their store info
    rows = await db.execute(
        select(TrackedProduct, DiscoveredProduct)
        .join(DiscoveredProduct, DiscoveredProduct.id == TrackedProduct.discovered_product_id)
        .where(TrackedProduct.is_active == True)  # noqa: E712
    )
    active_tracked = list(rows.all())

    if not active_tracked:
        logger.info("Monitoring cycle: no active tracked products")
        return {"polled": 0, "changes": 0, "errors": 0}

    logger.info("Monitoring cycle: polling %d active tracked products", len(active_tracked))

    semaphore = asyncio.Semaphore(_POLL_CONCURRENCY)
    polled = 0
    changes = 0
    errors = 0

    results = await asyncio.gather(
        *[
            _poll_one_product(db, semaphore, tracked, discovered)
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

    await db.commit()

    logger.info(
        "Monitoring cycle complete: polled=%d changes=%d errors=%d",
        polled,
        changes,
        errors,
    )
    return {"polled": polled, "changes": changes, "errors": errors}


async def _poll_one_product(
    db: AsyncSession,
    semaphore: asyncio.Semaphore,
    tracked: TrackedProduct,
    discovered: DiscoveredProduct,
) -> dict:
    """
    Poll a single tracked product, write snapshot, detect changes.
    Returns {'changed': bool, 'error': bool}.
    """
    async with semaphore:
        return await _do_poll(db, tracked, discovered)


async def _do_poll(
    db: AsyncSession,
    tracked: TrackedProduct,
    discovered: DiscoveredProduct,
) -> dict:
    """Execute one poll: fetch → snapshot → detect → optionally write PriceChange."""
    now = datetime.now(UTC)

    # Determine store URL from the product URL
    from urllib.parse import urlparse
    parsed = urlparse(discovered.product_url)
    store_url = f"{parsed.scheme}://{parsed.netloc}"

    # Fetch product data
    json_data = None
    http_status: int | None = None
    error_message: str | None = None
    extracted = None

    try:
        json_data = await fetch_product_json(
            store_url=store_url,
            handle=discovered.handle,
            rate_limit_delay=0.1,
        )
        if json_data is not None:
            extracted = extract_product_data(json_data)
            http_status = 200
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

    # Build current snapshot data
    if extracted is not None:
        current = SnapshotData(
            price=extracted.price,
            is_available=extracted.is_available,
            currency=extracted.currency,
        )
    else:
        current = SnapshotData(price=None, is_available=None)

    # Write the snapshot
    snapshot = ProductSnapshot(
        id=uuid.uuid4(),
        tracked_product_id=tracked.id,
        discovered_product_id=discovered.id,
        user_id=tracked.user_id,
        price=current.price,
        currency=current.currency,
        is_available=current.is_available,
        http_status=http_status,
        error_message=error_message,
        captured_at=now,
    )
    db.add(snapshot)

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

    if prev_snapshot is not None and error_message is None:
        previous = SnapshotData(
            price=float(prev_snapshot.price) if prev_snapshot.price is not None else None,
            is_available=prev_snapshot.is_available,
            currency=prev_snapshot.currency or "USD",
        )
        event = detect_price_change(previous, current)

        if event is not None:
            price_change = PriceChange(
                id=uuid.uuid4(),
                tracked_product_id=tracked.id,
                discovered_product_id=discovered.id,
                user_id=tracked.user_id,
                from_snapshot_id=prev_snapshot.id,
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
                is_available=extracted.is_available,
                is_on_sale=extracted.is_on_sale,
                is_discontinued=extracted.is_discontinued,
                data_fetched_at=now,
            )
        )

    return {"changed": changed, "error": error_message is not None}
