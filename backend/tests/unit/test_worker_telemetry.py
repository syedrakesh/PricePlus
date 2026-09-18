"""
Unit test for Worker Telemetry Service & Telemetry Endpoints.
"""
import pytest
from app.modules.monitoring.telemetry import WorkerTelemetryService


def test_worker_telemetry_service():
    srv = WorkerTelemetryService(max_buffer_size=10)

    # Record events
    srv.record_event(
        action="PULLED",
        product_title="Test Shirt",
        store_domain="teststore.com",
        price=29.99,
        status_code=200,
        latency_ms=150,
        user_id="user_123",
    )
    srv.record_event(
        action="DISPATCHED",
        product_title="Test Shoes",
        store_domain="telegram",
        price=None,
        status_code=200,
        latency_ms=80,
        user_id="user_456",
    )

    # Admin gets all events
    admin_evts = srv.get_events(user_id="user_123", is_admin=True)
    assert len(admin_evts) == 2

    # User_123 gets only user_123 events
    user_evts = srv.get_events(user_id="user_123", is_admin=False)
    assert len(user_evts) == 1
    assert user_evts[0]["product_title"] == "Test Shirt"

    # Worker pool status
    workers = srv.get_worker_pool_status(is_running=True, total_cycles=5)
    assert len(workers) == 3
    assert workers[0]["role"] == "price_fetcher"
    assert workers[1]["role"] == "discovery_engine"
    assert workers[2]["role"] == "alert_dispatcher"
