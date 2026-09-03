"""
Celery application factory.

Celery is initialized here (not in FastAPI app) so workers can be started
independently without booting the full FastAPI application.

Usage:
  celery -A app.workers.celery_app worker --loglevel=info
  celery -A app.workers.celery_app beat --loglevel=info
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "priceplus",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.discovery_tasks",
        "app.workers.monitoring_tasks",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    enable_utc=True,
    timezone="UTC",

    # Task behavior
    task_track_started=True,
    task_acks_late=True,          # Only ack after task completes (safer)
    worker_prefetch_multiplier=1,  # One task at a time per worker (prevents hoarding)

    # Results
    result_expires=3600,  # 1 hour — we persist state in DB, not in Celery

    # Retry defaults
    task_default_retry_delay=60,
    task_max_retries=3,

    # Beat schedule — monitoring runs every DEFAULT_POLL_INTERVAL_MINUTES
    beat_schedule={
        "monitoring.run_monitoring_cycle": {
            "task": "monitoring.run_monitoring_cycle",
            "schedule": settings.default_poll_interval_minutes * 60,  # seconds
            "options": {"expires": settings.default_poll_interval_minutes * 60},
        },
    },
)
