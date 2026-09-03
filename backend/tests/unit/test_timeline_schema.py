"""
Unit tests for monitoring schemas — specifically TimelineEntry and TimelineResponse.

Tests validate the shape and logic of the Phase 6 unified timeline.
"""

from app.modules.monitoring.schemas import TimelineEntry, TimelineResponse


class TestTimelineEntry:
    def test_snapshot_entry_fields(self):
        entry = TimelineEntry(
            kind="snapshot",
            timestamp="2024-01-15T10:00:00+00:00",
            price=19.99,
            currency="USD",
            is_available=True,
            change_type=None,
            old_price=None,
            new_price=None,
            pct_change=None,
            error_message=None,
            ref_id="550e8400-e29b-41d4-a716-446655440000",
        )
        assert entry.kind == "snapshot"
        assert entry.price == 19.99
        assert entry.change_type is None
        assert entry.pct_change is None

    def test_change_entry_fields(self):
        entry = TimelineEntry(
            kind="change",
            timestamp="2024-01-16T10:00:00+00:00",
            price=15.99,
            currency="USD",
            is_available=None,
            change_type="price_decrease",
            old_price=19.99,
            new_price=15.99,
            pct_change=-20.0,
            error_message=None,
            ref_id="550e8400-e29b-41d4-a716-446655440001",
        )
        assert entry.kind == "change"
        assert entry.change_type == "price_decrease"
        assert entry.pct_change == -20.0
        assert entry.old_price == 19.99
        assert entry.is_available is None  # Not set for change entries


class TestTimelineResponse:
    def _make_snapshot_entry(self, ts: str, price: float) -> TimelineEntry:
        return TimelineEntry(
            kind="snapshot",
            timestamp=ts,
            price=price,
            currency="USD",
            is_available=True,
            change_type=None,
            old_price=None,
            new_price=None,
            pct_change=None,
            error_message=None,
            ref_id="abc",
        )

    def test_response_structure(self):
        entries = [
            self._make_snapshot_entry("2024-01-16T10:00:00+00:00", 15.99),
            self._make_snapshot_entry("2024-01-15T10:00:00+00:00", 19.99),
        ]
        response = TimelineResponse(
            entries=entries,
            total_snapshots=2,
            total_changes=1,
            min_price=15.99,
            max_price=19.99,
            latest_price=15.99,
        )
        assert len(response.entries) == 2
        assert response.min_price == 15.99
        assert response.max_price == 19.99
        assert response.latest_price == 15.99
        assert response.total_changes == 1

    def test_empty_timeline(self):
        response = TimelineResponse(
            entries=[],
            total_snapshots=0,
            total_changes=0,
            min_price=None,
            max_price=None,
            latest_price=None,
        )
        assert response.entries == []
        assert response.min_price is None

    def test_entries_newest_first_ordering(self):
        """Verify that entries are expected to be sorted newest first."""
        e1 = self._make_snapshot_entry("2024-01-16T10:00:00+00:00", 15.99)  # newer
        e2 = self._make_snapshot_entry("2024-01-15T10:00:00+00:00", 19.99)  # older
        response = TimelineResponse(
            entries=[e1, e2],  # already newest-first
            total_snapshots=2,
            total_changes=0,
            min_price=15.99,
            max_price=19.99,
            latest_price=15.99,
        )
        # Newest entry first
        assert response.entries[0].timestamp > response.entries[1].timestamp
