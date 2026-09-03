"""API v1 root router — registers all module-level routers."""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
