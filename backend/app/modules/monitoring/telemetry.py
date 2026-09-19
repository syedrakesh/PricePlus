"""
Worker Telemetry Service — thread-safe ring buffer tracking live worker pool health,
active background tasks, and real-time item pull events for Discovery, Fetching, and Alerts.
"""

from collections import deque
from datetime import UTC, datetime
import logging
import threading
from typing import Any

import asyncio
import uuid
from app.core.db import AsyncSessionLocal
from app.modules.monitoring.models import WorkerTelemetryLog

logger = logging.getLogger(__name__)


async def _persist_event_to_db(event: dict[str, Any]) -> None:
    """Helper task to asynchronously persist a telemetry log into the database."""
    try:
        async with AsyncSessionLocal() as db:
            user_uuid = None
            if event.get("user_id"):
                try:
                    user_uuid = uuid.UUID(event["user_id"])
                except (ValueError, TypeError):
                    user_uuid = None

            log_id = None
            if event.get("id"):
                try:
                    log_id = uuid.UUID(event["id"])
                except (ValueError, TypeError):
                    log_id = uuid.uuid4()
            else:
                log_id = uuid.uuid4()

            log_entry = WorkerTelemetryLog(
                id=log_id,
                action=event.get("action", "UNKNOWN"),
                product_title=event.get("product_title"),
                store_domain=event.get("store_domain"),
                price=event.get("price"),
                status_code=event.get("status_code", 200),
                latency_ms=event.get("latency_ms", 0),
                user_id=user_uuid,
                details=event.get("details"),
            )
            db.add(log_entry)
            await db.commit()
    except Exception as exc:
        logger.warning("Failed to persist telemetry log to database: %s", exc)


class WorkerTelemetryService:
    def __init__(self, max_buffer_size: int = 200) -> None:
        self._max_buffer_size = max_buffer_size
        self._events_buffer: deque[dict[str, Any]] = deque(maxlen=max_buffer_size)
        self._lock = threading.Lock()
        self.started_at: datetime = datetime.now(UTC)

    def record_event(
        self,
        action: str,  # "PULLED" | "DISCOVERED" | "DISPATCHED" | "ERROR"
        product_title: str | None = None,
        store_domain: str | None = None,
        price: float | None = None,
        status_code: int = 200,
        latency_ms: int = 0,
        user_id: str | None = None,
        details: str | None = None,
    ) -> dict[str, Any]:
        """Record a live worker action into the telemetry ring buffer and DB log table."""
        event_id = str(uuid.uuid4())
        event = {
            "id": event_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "action": action,
            "product_title": product_title or "Unknown Product",
            "store_domain": store_domain or "General",
            "price": price,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "user_id": user_id,
            "details": details or "",
        }
        with self._lock:
            self._events_buffer.appendleft(event)

        # Async background insert to database
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_persist_event_to_db(event))
        except RuntimeError:
            pass

        return event


    def get_events(
        self,
        user_id: str | None = None,
        is_admin: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve recent events from the ring buffer. Admins see all events; regular users see their own."""
        with self._lock:
            all_events = list(self._events_buffer)

        if not is_admin and user_id:
            all_events = [e for e in all_events if e.get("user_id") == user_id or e.get("user_id") is None]

        return all_events[:limit]

    def get_worker_pool_status(self, is_running: bool = True, total_cycles: int = 0) -> list[dict[str, Any]]:
        """Return real-time status of backend workers."""
        now = datetime.now(UTC)
        return [
            {
                "name": "Worker #1 — Price Fetching Engine",
                "role": "price_fetcher",
                "status": "ACTIVE" if is_running else "PAUSED",
                "current_task": "Periodic Price Polling & HTML Extraction",
                "throughput_cycles": total_cycles,
                "concurrency": "5 concurrent httpx slots",
            },
            {
                "name": "Worker #2 — Store Discovery Pipeline",
                "role": "discovery_engine",
                "status": "ACTIVE",
                "current_task": "Sitemap & Product Catalog Parser",
                "concurrency": "Async Background Pipeline",
            },
            {
                "name": "Worker #3 — Notification Alert Dispatcher",
                "role": "alert_dispatcher",
                "status": "ACTIVE",
                "current_task": "Rule Evaluator & Telegram/Email Dispatcher",
                "concurrency": "Instant Async Event Loop",
            },
        ]


# Singleton instance
worker_telemetry = WorkerTelemetryService()
