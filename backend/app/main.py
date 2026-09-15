"""
PricePlus backend — FastAPI application factory.

Design notes:
- Lifespan context manager for startup/shutdown
- CORS configured from settings (never wildcard in production)
- Health check endpoint at /health (for load balancers, Docker, k8s)
- API versioned at /api/v1
- Global exception handlers for clean error responses
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown logic."""
    configure_logging()
    settings = get_settings()
    logger.info(
        "PricePlus backend starting",
        extra={"env": settings.app_env, "debug": settings.app_debug},
    )

    # Configure Stripe API key
    from app.modules.billing.stripe_service import configure_stripe
    configure_stripe()

    # Seed plans on startup (idempotent — safe to run every startup)
    from app.modules.billing.seed_plans import seed_plans
    await seed_plans()

    # Ensure schema migrations for tracked_products status column, discovery_runs raw_error, and users onboarding
    from app.core.db import AsyncSessionLocal
    from sqlalchemy import text
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("ALTER TABLE tracked_products ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active' NOT NULL;"))
            await db.execute(text("ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS raw_error TEXT;"))
            await db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT TRUE NOT NULL;"))
            await db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE NOT NULL;"))
            await db.commit()
    except Exception as exc:
        logger.warning("Failed to auto-migrate database columns: %s", exc)

    # Seed RBAC permissions and default roles on startup
    from app.core.db import AsyncSessionLocal
    from app.modules.auth.seed_rbac import seed_rbac_data
    try:
        async with AsyncSessionLocal() as db:
            await seed_rbac_data(db)
    except Exception as exc:
        logger.warning("Failed to seed RBAC data: %s", exc)

    # Clean up orphan discovery runs interrupted by server restarts
    from app.core.db import AsyncSessionLocal
    from sqlalchemy import update
    from app.modules.discovery.models import DiscoveryRun
    from datetime import datetime, UTC
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(DiscoveryRun)
                .where(DiscoveryRun.status.in_(["pending", "running"]))
                .values(
                    status="failed",
                    error_message="Interrupted by server restart",
                    completed_at=datetime.now(UTC),
                )
            )
            await db.commit()
    except Exception as exc:
        logger.warning("Failed to cleanup orphan discovery runs: %s", exc)

    # Start periodic background monitoring engine
    from app.modules.monitoring.engine import monitoring_engine
    monitoring_engine.start_engine()

    yield

    monitoring_engine.stop_engine()
    logger.info("PricePlus backend shutting down")


def create_app() -> FastAPI:
    """Application factory — create and configure the FastAPI app."""
    settings = get_settings()

    app = FastAPI(
        title="PricePlus API",
        description="Shopify competitor price monitoring SaaS",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # ── Global exception handlers ─────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled exception",
            extra={"path": str(request.url), "method": request.method},
        )
        headers = {}
        origin = request.headers.get("origin")
        if origin and (origin in settings.cors_origins or "*" in settings.cors_origins):
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
            headers=headers,
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    # Health check — must be fast, no DB dependency, for load balancers
    @app.get("/health", tags=["system"])
    async def health_check() -> dict:
        return {
            "status": "ok",
            "service": "priceplus-api",
            "version": "0.1.0",
        }

    # API v1 router (registered as modules are built)
    from app.api.v1.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    return app


# Module-level app instance used by uvicorn
app = create_app()
