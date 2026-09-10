"""
Settings router — HTTP layer for user preference configuration.
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.settings.models import UserSettings
from app.modules.settings.schemas import UpdateUserSettingsRequest, UserSettingsResponse

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_or_create_settings(db: AsyncSession, user_id: uuid.UUID) -> UserSettings:
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = UserSettings(
            user_id=user_id,
            discovery_concurrency=2,
            discovery_min_delay=0.8,
            discovery_max_delay=1.5,
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.get("", response_model=UserSettingsResponse)
async def get_user_settings(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> UserSettingsResponse:
    """
    Get discovery rate and concurrency settings for the current user.
    Creates default settings (concurrency=2, min_delay=0.8s, max_delay=1.5s) if not configured yet.
    """
    user_id = uuid.UUID(user_id_str)
    settings = await _get_or_create_settings(db, user_id)
    return UserSettingsResponse(
        user_id=str(settings.user_id),
        discovery_concurrency=settings.discovery_concurrency,
        discovery_min_delay=settings.discovery_min_delay,
        discovery_max_delay=settings.discovery_max_delay,
        updated_at=settings.updated_at.isoformat(),
    )


@router.patch("", response_model=UserSettingsResponse)
async def update_user_settings(
    data: UpdateUserSettingsRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> UserSettingsResponse:
    """
    Update discovery rate and concurrency settings for the current user.
    """
    user_id = uuid.UUID(user_id_str)
    settings = await _get_or_create_settings(db, user_id)

    if data.discovery_concurrency is not None:
        settings.discovery_concurrency = data.discovery_concurrency
    if data.discovery_min_delay is not None:
        settings.discovery_min_delay = data.discovery_min_delay
    if data.discovery_max_delay is not None:
        settings.discovery_max_delay = data.discovery_max_delay

    settings.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(settings)

    logger.info(
        "Updated discovery settings for user %s: concurrency=%d, delay=%.1f-%.1fs",
        user_id, settings.discovery_concurrency,
        settings.discovery_min_delay, settings.discovery_max_delay,
    )

    return UserSettingsResponse(
        user_id=str(settings.user_id),
        discovery_concurrency=settings.discovery_concurrency,
        discovery_min_delay=settings.discovery_min_delay,
        discovery_max_delay=settings.discovery_max_delay,
        updated_at=settings.updated_at.isoformat(),
    )
