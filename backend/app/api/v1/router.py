"""API v1 root router — registers all module-level routers."""

from fastapi import APIRouter

from app.modules.alerts.router import router as alerts_router
from app.modules.auth.router import router as auth_router
from app.modules.discovery.router import router as discovery_router
from app.modules.monitoring.router import router as monitoring_router
from app.modules.stores.router import router as stores_router
from app.modules.tracking.router import router as tracking_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(stores_router, prefix="/stores", tags=["stores"])
api_router.include_router(discovery_router, prefix="/stores", tags=["discovery"])
api_router.include_router(tracking_router, prefix="", tags=["tracking"])
api_router.include_router(monitoring_router, prefix="", tags=["monitoring"])
api_router.include_router(alerts_router, prefix="", tags=["alerts"])
