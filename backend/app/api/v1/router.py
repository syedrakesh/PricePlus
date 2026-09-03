"""API v1 root router — registers all module-level routers."""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.discovery.router import router as discovery_router
from app.modules.stores.router import router as stores_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(stores_router, prefix="/stores", tags=["stores"])
api_router.include_router(discovery_router, prefix="/stores", tags=["discovery"])
