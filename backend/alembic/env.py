"""
Alembic environment configuration.

Design decisions:
- Uses synchronous psycopg2 engine for migrations (simpler, no asyncio needed)
- Reads DATABASE_URL from .env file automatically (no manual export required)
- Imports all ORM models so autogenerate detects schema changes
- Naming convention from Base.metadata ensures portable constraint names
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Make app importable (backend/ must be on sys.path) ────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Load .env from backend/ so DATABASE_URL is set without manual export ───────
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file, override=False)  # don't override already-exported vars

# ── Import Base and ALL models (must happen after sys.path fix) ───────────────
# Every model must be imported here for autogenerate to detect it.
from app.core.db import Base  # noqa: E402
from app.modules.auth.models import User  # noqa: F401
from app.modules.stores.models import CompetitorStore  # noqa: F401
from app.modules.billing.models import Plan, Subscription  # noqa: F401
from app.modules.discovery.models import DiscoveredProduct, DiscoveryRun  # noqa: F401
# from app.modules.tracking.models import TrackedProduct  # noqa: F401
# from app.modules.monitoring.models import ProductSnapshot, PriceChange  # noqa: F401
# from app.modules.alerts.models import Alert  # noqa: F401

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_sync_url() -> str:
    """
    Return the psycopg2 (sync) database URL for Alembic.

    Alembic migrations run synchronously — they do not need asyncpg.
    We convert the asyncpg URL to psycopg2 here.
    """
    app_env = os.environ.get("APP_ENV", "development")
    if app_env == "test":
        raw = os.environ.get("DATABASE_TEST_URL") or os.environ.get("DATABASE_URL", "")
    else:
        raw = os.environ.get("DATABASE_URL", "")

    if not raw:
        raise RuntimeError(
            "DATABASE_URL is not set.\n"
            "  → Make sure backend/.env exists (copy from .env.example)\n"
            "  → Or export DATABASE_URL before running alembic"
        )

    # Convert async URL to sync URL for psycopg2
    return raw.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def run_migrations_offline() -> None:
    """Offline mode: emit SQL to stdout without a DB connection."""
    url = get_sync_url()
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


def run_migrations_online() -> None:
    """Online mode: connect to the DB and apply migrations synchronously."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_sync_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
