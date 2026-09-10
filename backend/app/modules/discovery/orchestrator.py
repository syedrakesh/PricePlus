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

    # Load store
    from app.modules.stores.models import CompetitorStore
    store_result = await db.execute(
        select(CompetitorStore).where(CompetitorStore.id == run.store_id)
    )
    store = store_result.scalar_one_or_none()
    if store is None:
        await _fail_run(db, run, "Competitor store not found")
        return

    store_url = store.url
    parsed_store = urlparse(store_url)
    store_host = parsed_store.hostname or ""

    # Mark as running
    await _update_run_status(db, run, "running")
    await db.commit()

    try:
        await _execute_pipeline(db, run, store_url, store_host)
    except Exception as exc:
        logger.exception(
            "Unexpected error in discovery pipeline for run %s: %s",
            discovery_run_id,
            exc,
        )
        await db.rollback()
        await _fail_run(db, run, f"Unexpected error: {exc}")
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
) -> None:
    """Inner pipeline — separated for clean error handling at top level."""

    # Step 1: Fetch root sitemap
    root_sitemap_url = store_url.rstrip("/") + "/sitemap.xml"
    logger.info("Fetching root sitemap: %s", root_sitemap_url)

    try:
        root_xml = await fetch_sitemap(root_sitemap_url, rate_limit_delay=0.0)
    except FetchError as exc:
        await _fail_run(db, run, f"Failed to fetch root sitemap: {exc}")
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
            "Fetching product data for %d products (of %d total)",
            len(products_to_fetch),
            len(all_parsed_products),
        )
        await _fetch_product_data_batch(
            db=db,
            store_url=store_url,
            store_id=run.store_id,
            products=products_to_fetch,
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
) -> None:
    """
    Fetch .json product data for a batch of products concurrently.

    Uses asyncio.gather with limited concurrency to avoid overwhelming the store.
    """
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

    async def fetch_one(product: ParsedProductURL) -> None:
        async with semaphore:
            json_data = await fetch_product_json(
                store_url=store_url,
                handle=product.handle,
                rate_limit_delay=0.2,
            )
            if json_data is None:
                return

            extracted = extract_product_data(json_data)
            if extracted is None:
                return

            # Update the discovered product with enriched data
            await db.execute(
                update(DiscoveredProduct)
                .where(
                    DiscoveredProduct.store_id == store_id,
                    DiscoveredProduct.handle == product.handle,
                )
                .values(
                    title=extracted.title,
                    current_price=extracted.price,
                    currency=extracted.currency,
                    is_available=extracted.is_available,
                    image_url=extracted.image_url or product.image_url,
                    raw_data=extracted.raw_data,
                    data_fetched_at=datetime.now(UTC),
                )
            )

    await asyncio.gather(*[fetch_one(p) for p in products], return_exceptions=True)
    await db.commit()


# ─── Run lifecycle helpers ────────────────────────────────────────────────────

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
) -> None:
    run.status = "failed"
    run.error_message = error_message
    run.completed_at = datetime.now(UTC)
    await db.commit()
    logger.error("Discovery run %s failed: %s", run.id, error_message)
