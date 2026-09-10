"""
Stores router — HTTP layer for competitor store management.

All endpoints require authentication (get_current_user_id dependency).
Business logic lives entirely in service.py.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.billing.entitlements import EntitlementError
from app.modules.stores.schemas import AddStoreRequest, StoreListResponse, StoreResponse
from app.modules.stores.service import StoreError, add_store, delete_store, get_store, list_stores

logger = logging.getLogger(__name__)

router = APIRouter()


def _handle_store_error(e: StoreError) -> None:
    raise HTTPException(status_code=e.status_code, detail=str(e))


def _handle_entitlement_error(e: EntitlementError) -> None:
    raise HTTPException(status_code=e.status_code, detail=str(e))


@router.post("", response_model=StoreResponse, status_code=201)
async def add_competitor_store(
    data: AddStoreRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> StoreResponse:
    """
    Add a competitor Shopify store to monitor.

    - URL is validated and SSRF-protected
    - URL is normalized before storage
    - Returns 409 if the store URL already exists for this user
    - Returns 403 if the user has reached their plan store limit
    """
    user_id = uuid.UUID(user_id_str)
    try:
        store = await add_store(db, user_id, data)
    except StoreError as e:
        _handle_store_error(e)
    except EntitlementError as e:
        _handle_entitlement_error(e)

    return StoreResponse.from_orm_model(store)


@router.get("", response_model=StoreListResponse)
async def list_competitor_stores(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> StoreListResponse:
    """
    List all competitor stores for the authenticated user.
    Returns stores ordered by creation date (newest first).
    """
    user_id = uuid.UUID(user_id_str)
    stores = await list_stores(db, user_id)

    from sqlalchemy import func, select
    from app.modules.discovery.models import DiscoveredProduct

    store_ids = [s.id for s in stores]
    counts_map: dict[uuid.UUID, int] = {}
    if store_ids:
        counts_res = await db.execute(
            select(DiscoveredProduct.store_id, func.count(DiscoveredProduct.id))
            .where(DiscoveredProduct.store_id.in_(store_ids))
            .group_by(DiscoveredProduct.store_id)
        )
        counts_map = {row[0]: row[1] for row in counts_res.all()}

    return StoreListResponse(
        stores=[StoreResponse.from_orm_model(s, counts_map.get(s.id, 0)) for s in stores],
        total=len(stores),
    )



@router.get("/{store_id}", response_model=StoreResponse)
async def get_competitor_store(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> StoreResponse:
    """
    Get a single competitor store by ID.
    Returns 404 if not found or not owned by the current user.
    """
    user_id = uuid.UUID(user_id_str)
    try:
        store_uuid = uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Store not found") from None

    try:
        store = await get_store(db, user_id, store_uuid)
    except StoreError as e:
        _handle_store_error(e)

    return StoreResponse.from_orm_model(store)


@router.delete("/{store_id}", status_code=204)
async def delete_competitor_store(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> None:
    """
    Delete a competitor store and all associated data.
    Returns 404 if not found or not owned by the current user.
    Returns 204 No Content on success.
    """
    user_id = uuid.UUID(user_id_str)
    try:
        store_uuid = uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Store not found") from None

    try:
        await delete_store(db, user_id, store_uuid)
    except StoreError as e:
        _handle_store_error(e)
