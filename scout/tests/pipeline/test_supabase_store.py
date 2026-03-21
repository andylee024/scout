"""Tests for SupabaseDataStore."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scout.pipeline.models.business import Business
from scout.pipeline.models.listing import Listing


def _make_mock_client():
    """Create a mock postgrest client with chained table().upsert().execute()."""
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])
    return mock_client


def _make_store(**kwargs):
    """Create a SupabaseDataStore with a mocked postgrest client."""
    mock_client = _make_mock_client()
    with patch("postgrest.SyncPostgrestClient", return_value=mock_client):
        from scout.pipeline.data_store.supabase import SupabaseDataStore

        store = SupabaseDataStore(
            url="https://test.supabase.co", key="test-key", **kwargs
        )
    return store, mock_client


class TestSupabaseDataStoreInit:
    def test_raises_without_credentials(self):
        mock_client = _make_mock_client()
        with patch.dict("os.environ", {}, clear=True), patch("postgrest.SyncPostgrestClient", return_value=mock_client):
            from scout.pipeline.data_store.supabase import SupabaseDataStore

            with pytest.raises(ValueError, match="SUPABASE_URL"):
                SupabaseDataStore(url="", key="")


class TestUpsertBusinesses:
    def test_empty_list_returns_zero(self):
        store, client = _make_store()
        assert store.upsert_businesses([]) == 0
        client.table.assert_not_called()

    def test_upserts_businesses(self):
        store, client = _make_store()
        businesses = [
            Business(name="Acme Fire", place_id="place-1", source="google_maps", state="TX"),
            Business(name="Best Fire Co", place_id="place-2", source="google_maps", state="FL"),
        ]
        result = store.upsert_businesses(businesses)
        assert result == 2
        client.table.assert_called_with("businesses")
        call_args = client.table().upsert.call_args
        rows = call_args[0][0]
        assert len(rows) == 2
        assert rows[0]["name"] == "Acme Fire"
        assert rows[0]["place_id"] == "place-1"
        assert rows[0]["state"] == "TX"

    def test_skips_nameless_businesses(self):
        store, client = _make_store()
        businesses = [
            Business(name="", source="google_maps"),
            Business(name="Real Co", source="google_maps"),
        ]
        result = store.upsert_businesses(businesses)
        assert result == 1

    def test_batching(self):
        store, client = _make_store(batch_size=2)
        businesses = [
            Business(name=f"Co {i}", source="google_maps") for i in range(5)
        ]
        result = store.upsert_businesses(businesses)
        assert result == 5
        # 5 items with batch_size=2 → 3 upsert calls
        assert client.table().upsert.call_count == 3


class TestUpsertListings:
    def test_empty_list_returns_zero(self):
        store, client = _make_store()
        assert store.upsert_listings([]) == 0

    def test_stubbed_returns_zero(self):
        """upsert_listings is a no-op stub in v2 (listings table dropped)."""
        store, client = _make_store()
        listings = [
            Listing(
                source="bizbuysell",
                source_id="123",
                url="https://example.com/123",
                name="Fire Biz",
                industry="fire protection",
                location="Houston, TX",
                state="TX",
                asking_price=500000,
                cash_flow=100000,
            ),
        ]
        result = store.upsert_listings(listings)
        assert result == 0


class TestPersistRaw:
    def test_noop_returns_key(self):
        """persist_raw is a no-op stub in v2 (raw_snapshots table dropped)."""
        store, client = _make_store()
        result = store.persist_raw("run123", "google_maps", {"results": [1, 2, 3]})
        assert result == "run123:google_maps"
        # Should NOT call any table — it's a no-op now
        client.table.assert_not_called()
