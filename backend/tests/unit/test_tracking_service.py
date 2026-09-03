"""
Unit tests for the tracking service layer.

Uses AsyncMock to simulate DB sessions — no real DB required.
Tests cover: track, bulk track, track-all, untrack, entitlement enforcement,
idempotency, reactivation of previously untracked products.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.billing.entitlements import EntitlementError
from app.modules.discovery.models import DiscoveredProduct
from app.modules.stores.models import CompetitorStore
from app.modules.tracking.models import TrackedProduct
from app.modules.tracking.service import (
    TrackingError,
    track_product,
    untrack_product,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

USER_ID = uuid.uuid4()
STORE_ID = uuid.uuid4()
PRODUCT_ID = uuid.uuid4()


def _make_store(user_id: uuid.UUID = USER_ID, store_id: uuid.UUID = STORE_ID) -> CompetitorStore:
    store = MagicMock(spec=CompetitorStore)
    store.id = store_id
    store.user_id = user_id
    return store


def _make_product(
    product_id: uuid.UUID = PRODUCT_ID,
    store_id: uuid.UUID = STORE_ID,
) -> DiscoveredProduct:
    product = MagicMock(spec=DiscoveredProduct)
    product.id = product_id
    product.store_id = store_id
    product.handle = "test-product"
    product.product_url = "https://shop.example.com/products/test-product"
    product.title = "Test Product"
    product.current_price = 19.99
    product.currency = "USD"
    product.is_available = True
    product.image_url = None
    product.discovered_at = datetime.now(UTC)
    return product


def _make_tracked(
    user_id: uuid.UUID = USER_ID,
    product_id: uuid.UUID = PRODUCT_ID,
    store_id: uuid.UUID = STORE_ID,
    is_active: bool = True,
) -> TrackedProduct:
    tracked = MagicMock(spec=TrackedProduct)
    tracked.id = uuid.uuid4()
    tracked.user_id = user_id
    tracked.discovered_product_id = product_id
    tracked.store_id = store_id
    tracked.is_active = is_active
    tracked.created_at = datetime.now(UTC)
    tracked.updated_at = datetime.now(UTC)
    return tracked


def _mock_db_execute(return_value=None) -> AsyncMock:
    """Build an AsyncMock db.execute that returns a result with scalar_one_or_none."""
    execute_mock = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = return_value
    result_mock.scalar_one.return_value = return_value if isinstance(return_value, int) else 0
    result_mock.scalars.return_value.all.return_value = []
    result_mock.one_or_none.return_value = None
    result_mock.all.return_value = []
    execute_mock.return_value = result_mock
    return execute_mock


def _make_db(
    store: CompetitorStore | None = None,
    product: DiscoveredProduct | None = None,
    existing_tracked: TrackedProduct | None = None,
    active_count: int = 0,
    max_products: int = 10,
) -> AsyncMock:
    """
    Build a mock AsyncSession configured for common tracking test scenarios.
    """
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()

    # Each execute call returns a different result depending on context
    # We use side_effect with a list of return values
    call_returns = []

    # 1st call: store ownership check
    store_result = MagicMock()
    store_result.scalar_one_or_none.return_value = store
    call_returns.append(store_result)

    # 2nd call: discovered product lookup
    product_result = MagicMock()
    product_result.scalar_one_or_none.return_value = product
    call_returns.append(product_result)

    # 3rd call: existing tracked check
    tracked_result = MagicMock()
    tracked_result.scalar_one_or_none.return_value = existing_tracked
    call_returns.append(tracked_result)

    # 4th call: active count
    count_result = MagicMock()
    count_result.scalar_one.return_value = active_count
    call_returns.append(count_result)

    # 5th call: plan limit (from entitlement service)
    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = max_products
    call_returns.append(plan_result)

    db.execute.side_effect = call_returns
    return db


# ─── track_product ────────────────────────────────────────────────────────────

class TestTrackProduct:
    @pytest.mark.asyncio
    async def test_tracks_new_product_successfully(self):
        store = _make_store()
        product = _make_product()
        db = _make_db(store=store, product=product, active_count=3, max_products=10)

        await track_product(db, USER_ID, STORE_ID, PRODUCT_ID)

        db.add.assert_called_once()
        db.commit.assert_called()
        # The newly created TrackedProduct is passed to db.add
        added_obj = db.add.call_args[0][0]
        assert isinstance(added_obj, TrackedProduct)
        assert added_obj.user_id == USER_ID
        assert added_obj.store_id == STORE_ID
        assert added_obj.is_active is True

    @pytest.mark.asyncio
    async def test_store_not_found_raises_tracking_error(self):
        db = _make_db(store=None)

        with pytest.raises(TrackingError) as exc_info:
            await track_product(db, USER_ID, STORE_ID, PRODUCT_ID)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_product_not_found_raises_tracking_error(self):
        store = _make_store()
        db = _make_db(store=store, product=None)

        with pytest.raises(TrackingError) as exc_info:
            await track_product(db, USER_ID, STORE_ID, PRODUCT_ID)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_already_tracked_returns_existing_idempotently(self):
        store = _make_store()
        product = _make_product()
        existing = _make_tracked(is_active=True)
        db = _make_db(store=store, product=product, existing_tracked=existing)

        result = await track_product(db, USER_ID, STORE_ID, PRODUCT_ID)

        # Should NOT add a new record
        db.add.assert_not_called()
        assert result is existing

    @pytest.mark.asyncio
    async def test_entitlement_error_when_limit_reached(self):
        store = _make_store()
        product = _make_product()
        db = _make_db(
            store=store,
            product=product,
            existing_tracked=None,
            active_count=10,   # at limit
            max_products=10,
        )

        with pytest.raises(EntitlementError) as exc_info:
            await track_product(db, USER_ID, STORE_ID, PRODUCT_ID)
        assert "10" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_reactivates_previously_untracked_product(self):
        store = _make_store()
        product = _make_product()
        existing = _make_tracked(is_active=False)
        db = _make_db(
            store=store,
            product=product,
            existing_tracked=existing,
            active_count=3,
            max_products=10,
        )
        db.refresh = AsyncMock(side_effect=lambda obj: None)

        result = await track_product(db, USER_ID, STORE_ID, PRODUCT_ID)

        # Should reactivate existing record, not create a new one
        db.add.assert_not_called()
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_reactivation_blocked_at_limit(self):
        store = _make_store()
        product = _make_product()
        existing = _make_tracked(is_active=False)
        db = _make_db(
            store=store,
            product=product,
            existing_tracked=existing,
            active_count=10,
            max_products=10,
        )

        with pytest.raises(EntitlementError):
            await track_product(db, USER_ID, STORE_ID, PRODUCT_ID)


# ─── untrack_product ──────────────────────────────────────────────────────────

class TestUntrackProduct:
    @pytest.mark.asyncio
    async def test_untracks_active_product(self):
        tracked = _make_tracked(is_active=True)
        db = AsyncMock()
        db.commit = AsyncMock()

        tracked_result = MagicMock()
        tracked_result.scalar_one_or_none.return_value = tracked
        db.execute = AsyncMock(return_value=tracked_result)

        await untrack_product(db, USER_ID, tracked.id)

        assert tracked.is_active is False
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_found_raises_tracking_error(self):
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(TrackingError) as exc_info:
            await untrack_product(db, USER_ID, uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_already_inactive_is_idempotent(self):
        tracked = _make_tracked(is_active=False)
        db = AsyncMock()
        db.commit = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = tracked
        db.execute = AsyncMock(return_value=result)

        # Should not raise or commit
        await untrack_product(db, USER_ID, tracked.id)
        db.commit.assert_not_called()


# ─── Entitlement boundary tests ───────────────────────────────────────────────

class TestEntitlementBoundaries:
    @pytest.mark.asyncio
    async def test_free_plan_limit_is_enforced(self):
        """Validates that free plan (10 products) limit message includes the count."""
        store = _make_store()
        product = _make_product()
        db = _make_db(
            store=store,
            product=product,
            active_count=10,
            max_products=10,
        )

        with pytest.raises(EntitlementError) as exc_info:
            await track_product(db, USER_ID, STORE_ID, PRODUCT_ID)

        assert "10" in str(exc_info.value)
        assert "upgrade" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_one_below_limit_succeeds(self):
        """Adding product #10 when limit is 10 should succeed."""
        store = _make_store()
        product = _make_product()
        db = _make_db(
            store=store,
            product=product,
            active_count=9,   # one below limit
            max_products=10,
        )

        await track_product(db, USER_ID, STORE_ID, PRODUCT_ID)

        db.add.assert_called_once()
