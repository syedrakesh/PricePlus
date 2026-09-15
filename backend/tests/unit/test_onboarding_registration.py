"""
Unit tests for user registration with plan selection and onboarding completion.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import register_user


@pytest.mark.asyncio
async def test_register_user_free_plan():
    mock_db = AsyncMock()

    # Mock DB query for existing user (None) and plan
    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = None

    mock_plan = MagicMock()
    mock_plan.id = "plan-free-123"
    mock_plan.slug = "free"
    mock_plan.price_usd = 0
    mock_plan.stripe_price_id = None

    mock_plan_res = MagicMock()
    mock_plan_res.scalars().first.return_value = mock_plan

    mock_db.execute.side_effect = [mock_user_res, mock_plan_res]

    req = RegisterRequest(
        email="newuser_free@example.com",
        password="Password123",
        full_name="Free User",
        plan_slug="free",
    )
    tokens = await register_user(mock_db, req)
    assert tokens.access_token is not None
    assert tokens.redirect_url == "/onboarding"
    assert tokens.checkout_url is None
