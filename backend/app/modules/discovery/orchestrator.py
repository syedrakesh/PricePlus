"""
Discovery orchestrator — coordinates the full sitemap-first discovery pipeline.

This module contains the async business logic that runs inside Celery tasks.
It is NOT a Celery task itself — it's pure async Python called by the worker.

Pipeline:
1. Mark DiscoveryRun as 'running'
2. Fetch /sitemap.xml → parse root (sitemapindex vs urlset)
3. For each product sitemap URL:
   a. Fetch the sitemap XML
   b. Parse all <url><loc> entries
   c. Validate each URL as /products/{handle}
   d. Upsert to discovered_products (INSERT ... ON CONFLICT DO UPDATE)
4. For each newly discovered or stale product: fetch .json data
5. Mark DiscoveryRun as 'completed', 'partial', or 'failed'

Failure handling:
- Failure in one product sitemap does NOT abort the whole run
- Failures increment products_failed counter
- If ALL sitemaps fail: status='failed'
- If SOME sitemaps fail: status='partial'
- products_failed are logged with the error for diagnosis
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.discovery.fetcher import FetchError, fetch_product_json, fetch_sitemap
from app.modules.discovery.models import DiscoveredProduct, DiscoveryRun
from app.modules.discovery.product_extractor import extract_product_data
from app.modules.discovery.sitemap_parser import (
    ParsedProductURL,
    parse_product_sitemap,
    parse_root_sitemap,
)

logger = logging.getLogger(__name__)

# After this many seconds, a discovery run is considered stale and can be retried
_STALE_RUN_THRESHOLD_SECONDS = 3600  # 1 hour


async def run_discovery_pipeline(
    db: AsyncSession,
    discovery_run_id: uuid.UUID,
) -> None:
    """
    Execute the full discovery pipeline for a DiscoveryRun.

    This is the main entry point called by the Celery task.
    All state is persisted to the DB so progress is observable via the API.
    """
    # Load the run and its store
    run_result = await db.execute(
        select(DiscoveryRun).where(DiscoveryRun.id == discovery_run_id)
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        logger.error("DiscoveryRun %s not found", discovery_run_id)
        return

    # Load store & user settings
    from app.modules.stores.models import CompetitorStore
    from app.modules.settings.models import UserSettings

    store_result = await db.execute(
        select(CompetitorStore).where(CompetitorStore.id == run.store_id)
    )
    store = store_result.scalar_one_or_none()
    if store is None:
        await _fail_run(db, run, "Competitor store not found")
        return

    # Fetch user settings for discovery rate control
    settings_res = await db.execute(
        select(UserSettings).where(UserSettings.user_id == store.user_id)
    )
    user_settings = settings_res.scalar_one_or_none()
    concurrency = user_settings.discovery_concurrency if user_settings else 2
    min_delay = user_settings.discovery_min_delay if user_settings else 0.8
    max_delay = user_settings.discovery_max_delay if user_settings else 1.5

    store_url = store.url
    parsed_store = urlparse(store_url)
    store_host = parsed_store.hostname or ""

    # Mark as running
    await _update_run_status(db, run, "running")
    await db.commit()

    try:
        await _execute_pipeline(
            db=db,
            run=run,
            store_url=store_url,
            store_host=store_host,
            concurrency=concurrency,
            min_delay=min_delay,
            max_delay=max_delay,
        )
    except Exception as exc:
        logger.exception(
            "Unexpected error in discovery pipeline for run %s: %s",
            discovery_run_id,
            exc,
        )
        await db.rollback()
        user_msg, raw_err = _sanitize_discovery_error(exc)
        await _fail_run(db, run, error_message=user_msg, raw_error=f"Unexpected error: {raw_err}")
        return

    # Update store.last_discovery_at
    await db.execute(
        update(CompetitorStore)
        .where(CompetitorStore.id == run.store_id)
        .values(last_discovery_at=datetime.now(UTC))
    )
    await db.commit()


async def _execute_pipeline(
    db: AsyncSession,
    run: DiscoveryRun,
    store_url: str,
    store_host: str,
    concurrency: int = 2,
    min_delay: float = 0.8,
    max_delay: float = 1.5,
) -> None:
    """Inner pipeline — separated for clean error handling at top level."""

    # Step 1: Fetch root sitemap
    root_sitemap_url = store_url.rstrip("/") + "/sitemap.xml"
    logger.info("Fetching root sitemap: %s", root_sitemap_url)

    try:
        root_xml = await fetch_sitemap(root_sitemap_url, rate_limit_delay=0.0)
    except FetchError as exc:
        user_msg, raw_err = _sanitize_discovery_error(exc)
        await _fail_run(
            db,
            run,
            error_message=user_msg,
            raw_error=f"Failed to fetch root sitemap ({root_sitemap_url}): {raw_err}",
        )
        return

    # Step 2: Parse root sitemap
    parse_result = parse_root_sitemap(root_xml, store_url)

    run.total_sitemaps_found = parse_result.total_sitemaps_found
    run.product_sitemaps_found = len(parse_result.product_sitemap_urls)
    await db.commit()

    if not parse_result.product_sitemap_urls:
        logger.warning("No product sitemaps found for %s", store_url)
        await _complete_run(db, run, status="partial")
        return

    logger.info(
        "Found %d product sitemap(s) for %s",
        len(parse_result.product_sitemap_urls),
        store_url,
    )

    # Step 3: Process each product sitemap
    total_created = 0
    total_updated = 0
    total_failed = 0
    all_parsed_products: list[ParsedProductURL] = []

    for sitemap_url in parse_result.product_sitemap_urls:
        created, updated, failed, parsed = await _process_product_sitemap(
            db=db,
            run=run,
            sitemap_url=sitemap_url,
            store_host=store_host,
        )
        total_created += created
        total_updated += updated
        total_failed += failed
        all_parsed_products.extend(parsed)

        run.product_sitemaps_processed += 1
        run.products_created = total_created
        run.products_updated = total_updated
        run.products_failed = total_failed
        run.products_discovered = total_created + total_updated
        await db.commit()

    # Step 4: Fetch product data (.json) for all discovered products
    products_to_fetch = all_parsed_products

    if products_to_fetch:
        logger.info(
            "Fetching product data for %d products (concurrency=%d, delay=%.1f-%.1fs)",
            len(products_to_fetch), concurrency, min_delay, max_delay,
        )
        await _fetch_product_data_batch(
            db=db,
            store_url=store_url,
            store_id=run.store_id,
            products=products_to_fetch,
            run=run,
            concurrency=concurrency,
            min_delay=min_delay,
            max_delay=max_delay,
        )


    # Determine final status
    if total_failed > 0 and total_created + total_updated == 0:
        status = "failed"
    elif total_failed > 0:
        status = "partial"
    else:
        status = "completed"

    await _complete_run(db, run, status=status)
    logger.info(
        "Discovery run %s completed: status=%s created=%d updated=%d failed=%d",
        run.id,
        status,
        total_created,
        total_updated,
        total_failed,
    )


async def _process_product_sitemap(
    db: AsyncSession,
    run: DiscoveryRun,
    sitemap_url: str,
    store_host: str,
) -> tuple[int, int, int, list[ParsedProductURL]]:
    """
    Fetch and process one product sitemap.

    Returns (created, updated, failed, parsed_products).
    Failure in this function is contained — does not propagate to caller.
    """
    try:
        xml_bytes = await fetch_sitemap(sitemap_url, rate_limit_delay=1.0)
    except FetchError as exc:
        logger.warning("Failed to fetch product sitemap %s: %s", sitemap_url, exc)
        return 0, 0, 1, []

    parsed_products = parse_product_sitemap(xml_bytes, sitemap_url, store_host)

    if not parsed_products:
        logger.info("No valid product URLs in sitemap: %s", sitemap_url)
        return 0, 0, 0, []

    created = 0
    updated = 0
    failed = 0

    for product in parsed_products:
        try:
            was_created = await _upsert_product(db, run, product)
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as exc:
            logger.warning(
                "Failed to upsert product %r: %s",
                product.handle,
                exc,
            )
            failed += 1

    return created, updated, failed, parsed_products


async def _upsert_product(
    db: AsyncSession,
    run: DiscoveryRun,
    product: ParsedProductURL,
) -> bool:
    """
    Upsert a discovered product. Returns True if created (new), False if updated.

    Uses PostgreSQL's INSERT ... ON CONFLICT DO UPDATE so the unique
    constraint (store_id, handle) is enforced at the DB level.
    """
    now = datetime.now(UTC)

    stmt = (
        pg_insert(DiscoveredProduct)
        .values(
            id=uuid.uuid4(),
            store_id=run.store_id,
            discovery_run_id=run.id,
            handle=product.handle,
            product_url=product.loc,
            image_url=product.image_url,
            sitemap_lastmod=product.lastmod,
            sitemap_source=product.sitemap_source,
            discovered_at=now,
            last_seen_at=now,
        )
        .on_conflict_do_update(
            index_elements=["store_id", "handle"],
            set_={
                "product_url": product.loc,
                "image_url": product.image_url,
                "sitemap_lastmod": product.lastmod,
                "sitemap_source": product.sitemap_source,
                "last_seen_at": now,
                "discovery_run_id": run.id,
            },
        )
        .returning(DiscoveredProduct.discovered_at)
    )

    result = await db.execute(stmt)
    row = result.fetchone()

    # If discovered_at == now, it was just created
    was_created = row is not None and row[0] is not None and (
        abs((row[0].replace(tzinfo=UTC) if row[0].tzinfo is None else row[0]) - now).total_seconds() < 2
    )

    return was_created


async def _fetch_product_data_batch(
    db: AsyncSession,
    store_url: str,
    store_id: uuid.UUID,
    products: list[ParsedProductURL],
    run: DiscoveryRun,
    concurrency: int = 2,
    min_delay: float = 0.8,
    max_delay: float = 1.5,
) -> None:
    """
    Fetch .json product data using user-configured concurrency and jitter delays.
    """
    import random
    from datetime import UTC, datetime

    COMMIT_BATCH_SIZE = 10

    total = len(products)
    fetched_count = 0
    pending_writes: list[tuple] = []
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(concurrency)

    logger.info(
        "Starting rate-limited product data fetch (%d workers, delay=%.1f-%.1fs) for %d products",
        concurrency, min_delay, max_delay, total,
    )

    async def fetch_one(product: ParsedProductURL) -> None:
        nonlocal fetched_count
        async with sem:
            await asyncio.sleep(random.uniform(min_delay, max_delay))
            try:
                json_data = await fetch_product_json(
                    store_url=store_url,
                    handle=product.handle,
                    rate_limit_delay=0.0,
                )
            except Exception as exc:
                logger.warning("Failed fetching %r: %s", product.handle, exc)
                json_data = None

            extracted = extract_product_data(json_data) if json_data else None

            async with lock:
                fetched_count += 1
                if extracted is not None:
                    pending_writes.append((
                        product.handle,
                        extracted.title,
                        extracted.price,
                        extracted.compare_at_price,
                        extracted.currency,
                        extracted.is_on_sale,
                        extracted.is_discontinued,
                        extracted.image_url or product.image_url,
                        extracted.raw_data,
                    ))

                should_commit = (
                    fetched_count % COMMIT_BATCH_SIZE == 0
                    or fetched_count == total
                )
                if should_commit and pending_writes:
                    for (
                        handle, title, price, compare_at, currency,
                        is_on_sale, is_disc, img_url, raw
                    ) in pending_writes:
                        await db.execute(
                            update(DiscoveredProduct)
                            .where(
                                DiscoveredProduct.store_id == store_id,
                                DiscoveredProduct.handle == handle,
                            )
                            .values(
                                title=title,
                                current_price=price,
                                compare_at_price=compare_at,
                                currency=currency,
                                is_on_sale=is_on_sale,
                                is_discontinued=is_disc,
                                image_url=img_url,
                                raw_data=raw,
                                data_fetched_at=datetime.now(UTC),
                            )
                        )
                    pending_writes.clear()
                    run.products_fetched = fetched_count
                    await db.commit()

                    logger.info(
                        "Product fetch progress: %d/%d (%.0f%%)",
                        fetched_count, total,
                        100 * fetched_count / total,
                    )

    tasks = [asyncio.create_task(fetch_one(p)) for p in products]
    await asyncio.gather(*tasks)
    logger.info("Finished fetching product data: %d/%d products processed", fetched_count, total)


# ─── Run lifecycle helpers ────────────────────────────────────────────────────

def _sanitize_discovery_error(exc: Exception) -> tuple[str, str]:
    """
    Given a discovery exception, return a tuple of:
    (user_friendly_clean_message, raw_technical_error_details)
    """
    raw_error = str(exc)
    raw_lower = raw_error.lower()

    if isinstance(exc, FetchError):
        status = getattr(exc, "status_code", None)
        if status == 404 or "not found" in raw_lower:
            user_msg = "Store sitemap is unavailable or private. Could not automatically discover products."
        elif status in (401, 403) or "forbidden" in raw_lower or "access denied" in raw_lower:
            user_msg = "Access to store catalog was restricted by store security settings."
        elif status == 429 or "rate limit" in raw_lower:
            user_msg = "Store server rate limit reached. Please try running discovery again later."
        elif "timeout" in raw_lower or "timed out" in raw_lower:
            user_msg = "Store server did not respond in time. Please try running discovery again later."
        else:
            user_msg = "Unable to fetch store sitemap catalog."
    else:
        user_msg = "Product discovery encountered an issue while scanning this store."

    return user_msg, raw_error


async def _update_run_status(
    db: AsyncSession,
    run: DiscoveryRun,
    status: str,
) -> None:
    run.status = status
    await db.commit()


async def _complete_run(
    db: AsyncSession,
    run: DiscoveryRun,
    status: str,
) -> None:
    run.status = status
    run.completed_at = datetime.now(UTC)
    await db.commit()


async def _fail_run(
    db: AsyncSession,
    run: DiscoveryRun,
    error_message: str,
    raw_error: str | None = None,
) -> None:
    run.status = "failed"
    run.error_message = error_message
    if raw_error:
        run.raw_error = raw_error
    run.completed_at = datetime.now(UTC)
    await db.commit()
    logger.error("Discovery run %s failed: %s (raw: %s)", run.id, error_message, raw_error or error_message)
