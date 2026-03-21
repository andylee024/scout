"""Minimal live smoke tests for data sources.

Set SCOUT_LIVE_TESTS=1 to enable network tests.
"""

from __future__ import annotations

import os
import pytest

from data_sources.maps.google_maps import GoogleMapsTool
from data_sources.maps.google_reviews import GoogleReviewsScraper
from data_sources.marketplaces.bizbuysell import BizBuySellProvider as BizBuySellTool
from data_sources.marketplaces.base import ListingQuery
from data_sources.sentiment.reddit import RedditSentimentScraper
from data_sources.shared.config import ScraperConfig


LIVE = os.getenv("SCOUT_LIVE_TESTS") == "1"


def _skip_live(reason: str) -> None:
    if not LIVE:
        pytest.skip(reason)


def test_google_maps_smoke():
    _skip_live("Set SCOUT_LIVE_TESTS=1 to run live data source tests")
    api_key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        pytest.skip("Missing Google Maps API key")

    tool = GoogleMapsTool()
    result = tool.search("car wash", "Austin, TX", max_results=5, use_cache=False)
    assert result.get("source") == "google_maps"
    assert isinstance(result.get("results"), list)
    assert len(result.get("results", [])) > 0


def test_google_reviews_smoke():
    _skip_live("Set SCOUT_LIVE_TESTS=1 to run live data source tests")
    api_key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        pytest.skip("Missing Google Maps API key")

    # Use a known Google Place ID (example: Googleplex)
    scraper = GoogleReviewsScraper(api_key=api_key)
    result = scraper.search("ChIJj61dQgK6j4AR4GeTYWZsKWw", use_cache=False)
    assert result.get("source") == "google_reviews"
    assert isinstance(result.get("results"), list)


def test_bizbuysell_smoke():
    _skip_live("Set SCOUT_LIVE_TESTS=1 to run live data source tests")

    tool = BizBuySellTool()
    listings = tool.search(ListingQuery("car wash", "california", 5), use_cache=False)
    assert isinstance(listings, list)
    if not listings:
        pytest.skip("BizBuySell returned no listings (possible bot block)")


@pytest.mark.skipif(
    not (os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET")),
    reason="Missing Reddit API credentials",
)
def test_reddit_smoke():
    _skip_live("Set SCOUT_LIVE_TESTS=1 to run live data source tests")

    scraper = RedditSentimentScraper(
        client_id=ScraperConfig.REDDIT_CLIENT_ID,
        client_secret=ScraperConfig.REDDIT_CLIENT_SECRET,
        user_agent=ScraperConfig.REDDIT_USER_AGENT,
    )
    result = scraper.search("hvac", max_posts=10, days_back=30, extract_quotes=False, use_cache=False)
    assert result.get("source") == "reddit_sentiment"
    assert isinstance(result.get("posts"), list)
