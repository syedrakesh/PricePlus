"""
Rate limiting middleware for PricePlus API.

Uses SlowAPI (Starlette-compatible wrapper around limits library).
Rate limits are applied per-IP from the X-Forwarded-For header in production
or the direct client IP in development.

Limits by endpoint category:
  auth endpoints:     5/minute   (prevents brute force)
  discovery trigger:  2/minute   (expensive background job)
  general API:        60/minute  (reasonable SaaS usage)
  webhook:            100/minute (Stripe may burst)

Configuration:
  Rate limits are defined here as constants and applied via decorators
  in each router. They are disabled in test mode (RATE_LIMIT_ENABLED=false).

Storage:
  Uses in-memory storage in development, Redis in production for
  distributed rate limiting across multiple API worker processes.
"""

import logging

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_real_ip(request) -> str:
    """
    Extract real client IP, respecting X-Forwarded-For in production.
    In development, use direct remote address.
    """
    settings = get_settings()
    if settings.is_production:
        # Trust the first IP in X-Forwarded-For set by the load balancer
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


def create_limiter() -> Limiter:
    """
    Create and configure the rate limiter.

    Uses Redis in production (distributed), memory storage in dev.
    """
    settings = get_settings()

    if settings.is_production and settings.redis_url:
        storage_uri = settings.redis_url
        logger.info("Rate limiter: using Redis storage (%s)", storage_uri)
    else:
        storage_uri = "memory://"
        logger.info("Rate limiter: using in-memory storage")

    return Limiter(
        key_func=_get_real_ip,
        storage_uri=storage_uri,
        # Default limit applied to all decorated endpoints
        default_limits=["60/minute"],
    )


# Module-level limiter instance — imported by routers that need rate limiting
limiter = create_limiter()

# ─── Rate limit strings ───────────────────────────────────────────────────────
# Import these in routers as: from app.core.rate_limit import LIMIT_AUTH, limiter

LIMIT_AUTH = "5/minute"
"""Authentication endpoints — prevents credential stuffing / brute force."""

LIMIT_DISCOVERY = "2/minute"
"""Discovery trigger — expensive background job, limit to prevent abuse."""

LIMIT_API = "60/minute"
"""General API endpoints — standard SaaS usage rate."""

LIMIT_WEBHOOK = "200/minute"
"""Stripe webhooks — Stripe can burst; keep high to avoid missed events."""

LIMIT_STRICT = "10/minute"
"""Sensitive write operations (checkout session creation, etc.)."""
