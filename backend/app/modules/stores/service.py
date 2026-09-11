"""
Stores service — business logic for competitor store management.

All DB queries live here. Routers call service functions only.
"""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.entitlements import EntitlementService
from app.modules.stores.models import CompetitorStore
from app.modules.stores.schemas import AddStoreRequest
from app.modules.stores.url_validator import URLValidationError, validate_store_url

logger = logging.getLogger(__name__)


class StoreError(Exception):
    """Domain-level store error."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


async def add_store(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: AddStoreRequest,
) -> CompetitorStore:
    """
    Add a competitor store for a user.

    Steps:
    1. Validate and normalize the URL (SSRF protection)
    2. Check duplicate (same user, same URL)
    3. Check plan entitlement (max_stores)
    4. Persist

    Raises StoreError on validation/business rule failures.
    Raises EntitlementError when plan limit is exceeded.
    """
    # Step 1: validate + SSRF check
    try:
        normalized_url = validate_store_url(data.url)
    except URLValidationError as e:
        raise StoreError(str(e), status_code=400) from e

    # Step 2: duplicate check
    existing = await db.execute(
        select(CompetitorStore).where(
            CompetitorStore.user_id == user_id,
            CompetitorStore.url == normalized_url,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise StoreError(
            "You have already added this store. "
            "Check your existing stores list.",
            status_code=409,
        )

    # Step 3: entitlement check
    await EntitlementService.check_can_add_store(user_id, db)

    # Step 4: persist
    store = CompetitorStore(
        id=uuid.uuid4(),
        user_id=user_id,
        url=normalized_url,
        display_name=data.display_name,
        platform="shopify",
        status="active",
    )
    db.add(store)
    await db.commit()
    await db.refresh(store)

    logger.info(
        "Store added",
        extra={"user_id": str(user_id), "store_id": str(store.id), "url": normalized_url},
    )
    return store


async def list_stores(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[CompetitorStore]:
    """Return all competitor stores owned by the user, ordered by creation date."""
    result = await db.execute(
        select(CompetitorStore)
        .where(CompetitorStore.user_id == user_id)
        .order_by(CompetitorStore.created_at.desc())
    )
    return list(result.scalars().all())


async def get_store(
    db: AsyncSession,
    user_id: uuid.UUID,
    store_id: uuid.UUID,
) -> CompetitorStore:
    """
    Get a single store by ID, enforcing ownership.
    Raises StoreError 404 if not found or not owned by this user.
    """
    result = await db.execute(
        select(CompetitorStore).where(
            CompetitorStore.id == store_id,
            CompetitorStore.user_id == user_id,
        )
    )
    store = result.scalar_one_or_none()
    if store is None:
        raise StoreError("Store not found", status_code=404)
    return store


async def delete_store(
    db: AsyncSession,
    user_id: uuid.UUID,
    store_id: uuid.UUID,
) -> None:
    """
    Delete a competitor store, enforcing ownership.
    Also deletes all associated data (cascaded at DB level in Phase 3+).
    Raises StoreError 404 if not found or not owned by this user.
    """
    store = await get_store(db, user_id, store_id)
    await db.delete(store)
    await db.commit()

    logger.info(
        "Store deleted",
        extra={"user_id": str(user_id), "store_id": str(store_id)},
    )
