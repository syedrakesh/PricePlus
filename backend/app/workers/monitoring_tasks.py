"""
Monitoring Celery task — periodic price polling.

This task is scheduled by Celery Beat to run every N minutes.
The interval comes from the smallest poll_interval_mins across all active plans,
defaulting to DEFAULT_POLL_INTERVAL_MINUTES from settings.

Important: This task polls ALL tracked products across ALL users in one batch.
This is efficient for MVP. At scale, it would be sharded by store or user.
"""

import asyncio
import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="monitoring.run_monitoring_cycle",
    max_retries=0,  # Don't retry — just run again on next beat tick
    soft_time_limit=1800,  # 30 minutes
    time_limit=2100,       # 35 minutes hard kill
)
def run_monitoring_task() -> dict:
    """
    Run one full monitoring cycle: poll all active tracked products.

    Called by Celery Beat on a schedule. Returns a summary dict.
    """
    return asyncio.run(_run_monitoring_async())


async def _run_monitoring_async() -> dict:
    from app.core.db import AsyncSessionLocal
    from app.modules.monitoring.orchestrator import run_monitoring_cycle

    logger.info("Starting monitoring task")
    async with AsyncSessionLocal() as db:
        result = await run_monitoring_cycle(db)

    logger.info("Monitoring task complete: %s", result)
    return result
