"""
Unit tests for subscription plan downgrade entitlements & soft pause logic.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.modules.billing.entitlements import EntitlementService, UserUsageSummary


def _make_store(store_id=None, status="active", created_offset=0):
    store = MagicMock()
    store.id = store_id or uuid.uuid4()
    store.status = status
    store.created_at = created_offset
    return store


def _make_product(product_id=None, is_active=True, status="active", created_offset=0):
    prod = MagicMock()
    prod.id = product_id or uuid.uuid4()
    prod.is_active = is_active
    prod.status = status
    prod.created_at = created_offset
    return prod


class TestDowngradeEntitlements:

    @pytest.mark.asyncio
    async def test_sync_user_plan_entitlements_downgrade(self):
        user_id = uuid.uuid4()

        # Mock Plan (Free plan: 1 store, 2 tracked products)
        free_plan = MagicMock()
        free_plan.max_stores = 1
        free_plan.max_tracked_products = 2

        # 3 Stores
        store1 = _make_store(status="active", created_offset=1)
        store2 = _make_store(status="active", created_offset=2)
        store3 = _make_store(status="active", created_offset=3)
        stores_res = MagicMock()
        stores_res.scalars().all.return_value = [store1, store2, store3]

        # 5 Products
        prod1 = _make_product(is_active=True, status="active", created_offset=1)
        prod2 = _make_product(is_active=True, status="active", created_offset=2)
        prod3 = _make_product(is_active=True, status="active", created_offset=3)
        prod4 = _make_product(is_active=True, status="active", created_offset=4)
        prod5 = _make_product(is_active=True, status="active", created_offset=5)
        prods_res = MagicMock()
        prods_res.scalars().all.return_value = [prod1, prod2, prod3, prod4, prod5]

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[stores_res, prods_res])

        with patch("app.modules.billing.entitlements._is_superuser_or_admin", return_value=False), \
             patch.object(EntitlementService, "get_user_active_plan", return_value=free_plan):
            
            await EntitlementService.sync_user_plan_entitlements(user_id, db)

        # Assert Store limits (1 active, 2 paused_over_limit)
        assert store1.status == "active"
        assert store2.status == "paused_over_limit"
        assert store3.status == "paused_over_limit"

        # Assert Product limits (2 active, 3 paused_over_limit)
        assert prod1.is_active is True and prod1.status == "active"
        assert prod2.is_active is True and prod2.status == "active"
        assert prod3.is_active is False and prod3.status == "paused_over_limit"
        assert prod4.is_active is False and prod4.status == "paused_over_limit"
        assert prod5.is_active is False and prod5.status == "paused_over_limit"

    @pytest.mark.asyncio
    async def test_sync_user_plan_entitlements_upgrade_restores(self):
        user_id = uuid.uuid4()

        # Mock Pro Plan (5 stores, 10 tracked products)
        pro_plan = MagicMock()
        pro_plan.max_stores = 5
        pro_plan.max_tracked_products = 10

        # Stores (previously 2 paused)
        store1 = _make_store(status="active", created_offset=1)
        store2 = _make_store(status="paused_over_limit", created_offset=2)
        store3 = _make_store(status="paused_over_limit", created_offset=3)
        stores_res = MagicMock()
        stores_res.scalars().all.return_value = [store1, store2, store3]

        # Products (previously 2 paused)
        prod1 = _make_product(is_active=True, status="active", created_offset=1)
        prod2 = _make_product(is_active=False, status="paused_over_limit", created_offset=2)
        prod3 = _make_product(is_active=False, status="paused_over_limit", created_offset=3)
        prods_res = MagicMock()
        prods_res.scalars().all.return_value = [prod1, prod2, prod3]

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[stores_res, prods_res])

        with patch("app.modules.billing.entitlements._is_superuser_or_admin", return_value=False), \
             patch.object(EntitlementService, "get_user_active_plan", return_value=pro_plan):
            
            await EntitlementService.sync_user_plan_entitlements(user_id, db)

        # Assert all Stores restored to active
        assert store1.status == "active"
        assert store2.status == "active"
        assert store3.status == "active"

        # Assert all Products restored to active
        assert prod1.is_active is True and prod1.status == "active"
        assert prod2.is_active is True and prod2.status == "active"
        assert prod3.is_active is True and prod3.status == "active"
