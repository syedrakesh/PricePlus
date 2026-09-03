"""
pytest conftest.py — shared fixtures and test configuration.

Phase 0: minimal setup.
Future phases will add:
- async test database session fixture
- test client with auth
- factory fixtures for models
"""

import os

# Ensure test environment is set before any app code imports config
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://priceplus:priceplus@localhost:5432/priceplus_test",
)
os.environ.setdefault(
    "DATABASE_TEST_URL",
    "postgresql+asyncpg://priceplus:priceplus@localhost:5432/priceplus_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
