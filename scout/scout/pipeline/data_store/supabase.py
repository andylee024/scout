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
        from supabase import Client, create_client

        self.url = url or os.getenv("SUPABASE_URL", "")
        self.key = key or os.getenv("SUPABASE_KEY", "")
        if not self.url or not self.key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be set "
                "(env vars or constructor args)"
            )
        self.client: Client = create_client(self.url, self.key)
        self.batch_size = batch_size

    def persist_raw(self, run_id: str, source: str, payload: dict[str, object]) -> str:
        safe_payload = json.loads(json.dumps(payload, default=str))
        row = {"run_id": run_id, "source": source, "payload": safe_payload}
        self.client.table("raw_snapshots").upsert(
            row, on_conflict="run_id,source"
        ).execute()
        return f"{run_id}:{source}"

    def upsert_businesses(self, businesses: list[Business]) -> int:
        if not businesses:
            return 0

        rows = [
            {
                "source": b.source,
                "name": b.name,
                "address": b.address,
                "phone": b.phone,
                "website": b.website,
                "category": b.category,
                "location": b.location,
                "state": b.state,
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
        if not listings:
            return 0

        rows = [
            {
                "id": listing.id,
                "source": listing.source,
                "source_id": listing.source_id,
                "url": listing.url,
                "name": listing.name,
                "industry": listing.industry,
                "location": listing.location,
                "state": listing.state,
                "description": listing.description,
                "asking_price": listing.asking_price,
                "annual_revenue": listing.annual_revenue,
                "cash_flow": listing.cash_flow,
                "asking_multiple": listing.asking_multiple,
                "days_on_market": listing.days_on_market,
                "broker": listing.broker,
                "listed_at": listing.listed_at,
                "fetched_at": listing.fetched_at,
            }
            for listing in listings
            if listing.name
        ]

        count = 0
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i : i + self.batch_size]
            self.client.table("listings").upsert(
                batch, on_conflict="id"
            ).execute()
            count += len(batch)
        return count
