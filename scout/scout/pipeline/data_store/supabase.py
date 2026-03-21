"""Supabase DataStore implementation."""

from __future__ import annotations

import json
import os

from scout.pipeline.data_store.base import DataStore
from scout.pipeline.models.business import Business
from scout.pipeline.models.listing import Listing


class SupabaseDataStore(DataStore):
    """Persists canonical models to Supabase (Postgres via PostgREST)."""

    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        batch_size: int = 500,
    ) -> None:
        from postgrest import SyncPostgrestClient

        self.url = url or os.getenv("SUPABASE_URL", "")
        self.key = key or os.getenv("SUPABASE_KEY", "")
        if not self.url or not self.key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be set "
                "(env vars or constructor args)"
            )
        self.client = SyncPostgrestClient(
            base_url=f"{self.url}/rest/v1",
            headers={
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
            },
        )
        self.batch_size = batch_size

    def persist_raw(self, run_id: str, source: str, payload: dict[str, object]) -> str:
        """No-op — raw_snapshots table dropped in v2."""
        return f"{run_id}:{source}"

    def upsert_businesses(self, businesses: list[Business]) -> int:
        if not businesses:
            return 0

        rows = [
            {
                "source": b.source,
                "name": b.name,
                "place_id": b.place_id,
                "address": b.address,
                "city": _extract_city(b.address) if not getattr(b, "city", "") else "",
                "state": b.state or _extract_state(b.address),
                "phone": b.phone,
                "website": b.website,
                "category": b.category,
                "rating": b.rating,
                "reviews": b.reviews,
            }
            for b in businesses
            if b.name
        ]

        count = 0
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i : i + self.batch_size]
            self.client.table("businesses").upsert(
                batch, on_conflict="source,name,address"
            ).execute()
            count += len(batch)
        return count

    def upsert_listings(self, listings: list[Listing]) -> int:
        """No-op — listings table dropped in v2."""
        return 0


def _extract_city(address: str) -> str:
    """Parse city from a Google Maps formatted address."""
    from scout.pipeline.supabase_service import _extract_city as _ec
    return _ec(address)


def _extract_state(address: str) -> str:
    """Parse 2-letter state code from a formatted address."""
    from scout.pipeline.supabase_service import _extract_state as _es
    return _es(address)
