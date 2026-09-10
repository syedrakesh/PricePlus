"""
PricePlus backend — async SQLAlchemy database engine and session factory.

Key design decisions:
- Async engine (asyncpg driver) for non-blocking I/O
- Session per request pattern via FastAPI dependency
- Base model class for all ORM models
- Engine is initialized once; sessions are created per-request
"""

from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

# ── Naming convention for Alembic migrations ─────────────────────────────────
# This ensures constraint names are always deterministic and portable.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_engine(database_url: str | None = None):
    """Create the async SQLAlchemy engine."""
    settings = get_settings()
    url = database_url or settings.database_url
    return create_async_engine(
        url,
        echo=settings.app_debug,
        pool_pre_ping=True,  # verify connections before use
        pool_size=10,
        max_overflow=20,
    )


# Module-level engine and session factory — created once at import time.
# In tests, these are overridden via dependency injection.
_engine = create_engine()
AsyncSessionLocal = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
_async_session_factory = AsyncSessionLocal



def get_engine():
    """Return the module-level async engine."""
    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session per request.

    Usage:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with _async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
