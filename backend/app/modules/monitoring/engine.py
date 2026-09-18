"""
Monitoring background engine manager — handles periodic monitoring task lifecycle,
status tracking, manual polling triggers, and engine restarts.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.monitoring.orchestrator import run_monitoring_cycle

logger = logging.getLogger(__name__)


class MonitoringEngineManager:
    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = interval_seconds
        self.is_running: bool = False
        self.status: str = "stopped"  # "running" | "idle" | "stalled" | "stopped" | "error"
        self.started_at: datetime | None = None
        self.last_run_at: datetime | None = None
        self.next_run_at: datetime | None = None
        self.total_cycles_run: int = 0
        self.last_polled_count: int = 0
        self.last_changes_count: int = 0
        self.last_error_count: int = 0
        self.last_error_message: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    def start_engine(self) -> None:
        """Start the background monitoring loop task."""
        if self._task and not self._task.done():
            logger.info("Monitoring engine task is already running.")
            return

        self.is_running = True
        self.status = "running"
        self.started_at = datetime.now(UTC)
        self.next_run_at = datetime.now(UTC) + timedelta(seconds=self.interval_seconds)
        self._task = asyncio.create_task(self._periodic_loop())
        logger.info("Monitoring engine started with %ds interval.", self.interval_seconds)

    def stop_engine(self) -> None:
        """Stop the background monitoring loop task."""
        self.is_running = False
        self.status = "stopped"
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        logger.info("Monitoring engine stopped.")

    async def restart_engine(self) -> dict[str, Any]:
        """Restart the background task loop and immediately execute a check cycle across all products."""
        self.stop_engine()
        self.start_engine()
        from app.core.db import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await self.trigger_now(db, force_all=True)
        return self.get_status_dict()

    async def sync_cycles_from_db(self, db: AsyncSession) -> None:
        """Sync cumulative cycle count from worker_telemetry_logs database table."""
        try:
            from sqlalchemy import select, func
            from app.modules.monitoring.models import WorkerTelemetryLog
            res = await db.execute(
                select(func.count()).where(WorkerTelemetryLog.action == "CYCLE_COMPLETED")
            )
            count = res.scalar_one_or_none() or 0
            if count > self.total_cycles_run:
                self.total_cycles_run = count
        except Exception as exc:
            logger.warning("Failed to sync total cycles count from DB: %s", exc)

    async def trigger_now(self, db: AsyncSession, force_all: bool = False) -> dict[str, Any]:
        """Trigger a monitoring cycle immediately."""
        async with self._lock:
            try:
                res = await run_monitoring_cycle(db, force_all=force_all)
                self.last_run_at = datetime.now(UTC)
                self.total_cycles_run += 1
                self.last_polled_count = res.get("polled", 0)
                self.last_changes_count = res.get("changes", 0)
                self.last_error_count = res.get("errors", 0)
                self.last_error_message = None
                self.next_run_at = datetime.now(UTC) + timedelta(seconds=self.interval_seconds)
                if self.is_running:
                    self.status = "running"

                from app.modules.monitoring.telemetry import worker_telemetry
                worker_telemetry.record_event(
                    action="CYCLE_COMPLETED",
                    product_title=f"Monitoring Cycle #{self.total_cycles_run}",
                    store_domain="System Engine",
                    status_code=200,
                    details=f"Polled {self.last_polled_count} items, {self.last_changes_count} price changes, {self.last_error_count} errors",
                )

                return res
            except Exception as exc:
                self.last_error_message = str(exc)
                self.status = "error"
                logger.exception("Monitoring cycle trigger failed: %s", exc)
                raise

    async def _periodic_loop(self) -> None:
        """Background loop that executes monitoring cycles periodically."""
        from app.core.db import AsyncSessionLocal

        # Short initial delay on startup so DB migrations/seeds complete cleanly
        await asyncio.sleep(2)
        
        # Perform initial cycle on engine launch and sync historical counts
        try:
            async with AsyncSessionLocal() as db:
                await self.sync_cycles_from_db(db)
                await self.trigger_now(db, force_all=True)
        except Exception as exc:
            logger.warning("Initial monitoring run error: %s", exc)

        while self.is_running:
            try:
                self.next_run_at = datetime.now(UTC) + timedelta(seconds=self.interval_seconds)
                await asyncio.sleep(self.interval_seconds)

                async with AsyncSessionLocal() as db:
                    await self.trigger_now(db)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.last_error_message = str(exc)
                self.status = "error"
                logger.warning("Background periodic monitoring loop exception: %s", exc)
                await asyncio.sleep(10)  # Cool down on error before retrying loop

    def get_status_dict(self) -> dict[str, Any]:
        """Return full health & telemetry status of the monitoring engine."""
        task_active = self._task is not None and not self._task.done()
        
        current_status = self.status
        if not task_active and self.is_running:
            current_status = "stalled"
        elif not self.is_running:
            current_status = "stopped"

        now = datetime.now(UTC)
        seconds_until_next = 0
        if self.next_run_at and self.next_run_at > now:
            seconds_until_next = int((self.next_run_at - now).total_seconds())

        return {
            "status": current_status,
            "is_running": task_active,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "seconds_until_next_run": seconds_until_next,
            "interval_seconds": self.interval_seconds,
            "total_cycles_run": self.total_cycles_run,
            "last_polled_count": self.last_polled_count,
            "last_changes_count": self.last_changes_count,
            "last_error_count": self.last_error_count,
            "last_error_message": self.last_error_message,
        }


# Singleton monitoring engine instance
monitoring_engine = MonitoringEngineManager(interval_seconds=60)
