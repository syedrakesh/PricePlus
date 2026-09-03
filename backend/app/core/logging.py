"""
PricePlus backend — logging configuration.

Structured logging setup that:
- Uses JSON format in production for log aggregation tools
- Uses human-readable format in development
- Never logs secrets or sensitive values
"""

import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure application-wide logging."""
    settings = get_settings()

    log_level = logging.DEBUG if settings.app_debug else logging.INFO

    # Format: structured for prod, readable for dev
    if settings.is_production:
        fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    else:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    logging.basicConfig(
        level=log_level,
        format=fmt,
        stream=sys.stdout,
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.app_debug else logging.WARNING
    )
    logging.getLogger("celery").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info("Logging configured", extra={"env": settings.app_env})


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Use module __name__ as convention."""
    return logging.getLogger(name)
