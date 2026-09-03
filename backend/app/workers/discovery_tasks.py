"""
Discovery Celery tasks.

These are thin task wrappers — the actual logic lives in orchestrator.py.
Tasks are responsible for:
- DB session lifecycle
- Error handling and retry logic
- Logging task lifecycle events
"""

import asyncio
import logging
import uuid

from celery import Task

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class DiscoveryTask(Task):
    """
    Base class for discovery tasks.
    Provides a reusable async DB session pattern.
    """

    abstract = True


@celery_app.task(
    bind=True,
    base=DiscoveryTask,
    name="discovery.run_discovery",
    max_retries=3,
    default_retry_delay=120,  # 2 minutes
    soft_time_limit=1800,  # 30 min soft limit (raises SoftTimeLimitExceeded)
    time_limit=2100,  # 35 min hard kill
)
def run_discovery_task(self: Task, discovery_run_id: str) -> dict:
    """
    Execute product discovery for a DiscoveryRun.

    Args:
        discovery_run_id: UUID string of the DiscoveryRun to process

    Returns:
        Dict with run summary (status, counts)
    """
    return asyncio.run(_run_discovery_async(self, discovery_run_id))


async def _run_discovery_async(task: Task, discovery_run_id: str) -> dict:
    """Async implementation of the discovery task."""
    from app.core.db import AsyncSessionLocal
    from app.modules.discovery.orchestrator import run_discovery_pipeline

    run_uuid = uuid.UUID(discovery_run_id)
    logger.info("Starting discovery task for run %s", discovery_run_id)

    async with AsyncSessionLocal() as db:
        try:
            await run_discovery_pipeline(db, run_uuid)
        except Exception as exc:
            logger.exception(
                "Unhandled error in discovery task %s: %s",
                discovery_run_id,
                exc,
            )
            # Don't retry on unhandled errors — the run is already marked as failed
            return {"status": "error", "error": str(exc)}

    # Fetch final run state for return value
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        from app.modules.discovery.models import DiscoveryRun
        result = await db.execute(
            select(DiscoveryRun).where(DiscoveryRun.id == run_uuid)
        )
        run = result.scalar_one_or_none()
        if run is None:
            return {"status": "unknown"}

        logger.info(
            "Discovery task complete: run=%s status=%s created=%d updated=%d",
            discovery_run_id,
            run.status,
            run.products_created,
            run.products_updated,
        )

        return {
            "status": run.status,
            "products_created": run.products_created,
            "products_updated": run.products_updated,
            "products_failed": run.products_failed,
        }
