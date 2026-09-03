"""
Phase 0 smoke test — verifies the FastAPI application starts
and the /health endpoint returns the expected response.

This test does NOT require a database or Redis to be running.
It uses FastAPI's TestClient (synchronous, no network I/O).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check_returns_ok():
    """GET /health must return 200 with status=ok."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "priceplus-api"


@pytest.mark.asyncio
async def test_health_check_has_version():
    """Health response must include a version field."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health")

    assert "version" in response.json()


@pytest.mark.asyncio
async def test_unknown_route_returns_404():
    """Unregistered routes must return 404, not 500."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/nonexistent-route-xyz")

    assert response.status_code == 404
