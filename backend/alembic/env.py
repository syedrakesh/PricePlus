"""
Alembic environment configuration — async SQLAlchemy edition.

Key design decisions:
- Uses asyncpg driver via run_sync() pattern for async migrations
- Reads DATABASE_URL from environment (not hard-coded in alembic.ini)
- Imports all ORM models so autogenerate can detect schema changes
- Uses the naming convention from Base.metadata for portable constraint names
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Make sure `app` is importable from backend/ directory ─────────────────────
# Alembic is run from backend/, so app/ must be on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Import Base and ALL models ─────────────────────────────────────────────────
# Every model module must be imported here so Alembic autogenerate
# can detect schema changes. Add imports as new models are created.
from app.core.db import Base  # noqa: E402

# Future model imports (uncomment as models are added):
# from app.modules.auth.models import User  # noqa: F401
# from app.modules.stores.models import CompetitorStore  # noqa: F401
# from app.modules.discovery.models import DiscoveredProduct, DiscoveryRun  # noqa: F401
# from app.modules.tracking.models import TrackedProduct  # noqa: F401
# from app.modules.monitoring.models import ProductSnapshot, PriceChange  # noqa: F401
# from app.modules.alerts.models import Alert  # noqa: F401
# from app.modules.billing.models import Plan, Subscription  # noqa: F401

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ── Read DB URL from environment (overrides alembic.ini placeholder) ──────────
def get_url() -> str:
    """
    Read the database URL from the environment.

    In development: reads from DATABASE_URL env var (set via .env).
    In test: reads from DATABASE_TEST_URL if APP_ENV=test.
    Never reads from the hard-coded alembic.ini placeholder.
    """
    app_env = os.environ.get("APP_ENV", "development")
    if app_env == "test":
        url = os.environ.get("DATABASE_TEST_URL", "")
    else:
        url = os.environ.get("DATABASE_URL", "")

    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Copy .env.example to .env and configure it."
        )

    # Alembic needs the sync driver for migrations.
    # Replace asyncpg with psycopg2 for migration execution.
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode (generates SQL scripts without DB connection).
    Useful for reviewing changes before applying them.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine (converted to sync for Alembic)."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the real database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
