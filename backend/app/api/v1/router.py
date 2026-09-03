"""API v1 root router — registers all module-level routers."""

from fastapi import APIRouter

api_router = APIRouter()

# Routers will be registered here as each module is built:
# from app.modules.auth.router import router as auth_router
# from app.modules.stores.router import router as stores_router
# api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# Phase 0 placeholder — just confirms the router imports correctly
