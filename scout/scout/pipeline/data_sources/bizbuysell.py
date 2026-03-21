"""BizBuySell DataSource."""

from __future__ import annotations

from data_sources.marketplaces.base import ListingQuery
from data_sources.marketplaces.bizbuysell import BizBuySellProvider
from data_sources.marketplaces.validation import validate_batch
from scout.pipeline.data_sources.base import DataSource, NormalizedBatch
from scout.pipeline.models.listing import Listing
from scout.pipeline.models.query import Query


class BizBuySellDataSource(DataSource):
    name = "bizbuysell"

    def __init__(self) -> None:
        self.provider = BizBuySellProvider()

    def fetch(self, query: Query) -> dict[str, object]:
        listing_query = ListingQuery(
            industry=query.industry,
            location=query.location,
            max_results=query.max_results,
        )
        listings = self.provider.search(listing_query, use_cache=query.use_cache)
        return {
            "listings": [listing.to_dict() for listing in listings],
            "market_stats": dict(self.provider.market_stats),
            "total_found": len(listings),
        }

    def normalize(self, raw: dict[str, object], query: Query) -> NormalizedBatch:
        listings: list[Listing] = []
        for item in raw.get("listings", []) or []:
            if not isinstance(item, dict):
                continue
            listing = Listing.from_dict(item)
            if not listing.industry:
                listing.industry = query.industry
            if listing.name:
                listings.append(listing)

        validation = validate_batch(listings, query.industry)

        return NormalizedBatch(
            businesses=[],
            listings=listings,
            signals={
                "market_stats": raw.get("market_stats", {}),
                "validation": {
                    "query_industry": validation.query_industry,
                    "total": validation.total,
                    "relevant": validation.relevant,
                    "precision_pct": validation.precision_pct,
                    "irrelevant_names": validation.irrelevant_names,
                },
            },
        )
