import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # Register
    res = await client.post("/api/v1/auth/register", json={"email": "test@example.com", "password": "Password123"})
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    
    # Login
    res = await client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "Password123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    
    # Get Me
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "test@example.com"
