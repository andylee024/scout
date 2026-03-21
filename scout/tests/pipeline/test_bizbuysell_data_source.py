from scout.pipeline.data_sources.bizbuysell import BizBuySellDataSource
from scout.pipeline.models.listing import Listing
from scout.pipeline.models.query import Query


class StubProvider:
    def __init__(self, listings):
        self._listings = listings
        self.market_stats = {"median_multiple": 3.2}
        self.last_query = None
        self.last_use_cache = None

    def search(self, query, use_cache=True):
        self.last_query = query
        self.last_use_cache = use_cache
        return self._listings


def _listing(*, source_id: str, name: str, description: str = "") -> Listing:
    return Listing(
        source="bizbuysell",
        source_id=source_id,
        url=f"https://example.com/{source_id}",
        name=name,
        industry="",
        location="Austin, TX",
        description=description,
        fetched_at="2026-03-21T00:00:00",
    )


def test_bizbuysell_data_source_fetch_and_validation_signals():
    source = BizBuySellDataSource()
    source.provider = StubProvider(
        [
            _listing(source_id="1", name="HVAC Business"),
            _listing(source_id="2", name="Coffee Shop"),
        ]
    )
    query = Query(industry="hvac", location="Austin, TX", max_results=25, use_cache=False)

    raw = source.fetch(query)
    batch = source.normalize(raw, query)

    assert source.provider.last_query.industry == "hvac"
    assert source.provider.last_query.location == "Austin, TX"
    assert source.provider.last_query.max_results == 25
    assert source.provider.last_use_cache is False

    assert len(batch.listings) == 2
    assert all(listing.industry == "hvac" for listing in batch.listings)
    assert batch.signals["market_stats"]["median_multiple"] == 3.2
    assert batch.signals["validation"]["total"] == 2
    assert batch.signals["validation"]["relevant"] == 1
    assert batch.signals["validation"]["precision_pct"] == 50.0
    assert "Coffee Shop" in batch.signals["validation"]["irrelevant_names"]
