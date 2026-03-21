# BizBuySell Integration Notes

**Status:** Active implementation notes  
**Last Updated:** 2026-03-21  
**Scope:** Source-specific notes for the shared data pipeline

## Current Role

BizBuySell is the marketplace listing source in the canonical pipeline:

1. `Runner` creates a `Query`.
2. `Workflow` calls `BizBuySellDataSource.fetch()`.
3. `BizBuySellDataSource` converts `Query` into `ListingQuery`.
4. `BizBuySellProvider` resolves route slugs and fetches marketplace pages.
5. Listings are normalized into canonical `Listing` records.
6. Validation telemetry is emitted alongside normalized listings.

## Important Behaviors

### Slug routing

BizBuySell routes are slug-based, so natural-language query text must be mapped into provider-specific paths before fetch.

### Relevance filtering

For fire-related queries, the provider applies keyword filtering on listing name and description. If that yields no matches, it falls back to the unfiltered provider result.

### Validation telemetry

The pipeline keeps listing relevance validation attached to BizBuySell signals so query precision can be inspected without reintroducing a parallel pipeline.

### Provider isolation

Slug resolution, anti-bot behavior, and scraping quirks should stay inside the BizBuySell provider and adapter, not in `Workflow`.

## Known Constraints

1. Industry slug mapping is still partially curated.
2. Browser and anti-bot behavior can affect reliability.
3. There is still no explicit entity match between listings and businesses.

## Next Work

1. Keep relevance validation in the active pipeline.
2. Improve slug coverage without leaking route logic into shared models.
3. Attach listings cleanly to merged `Lead` records once the merge stage exists.
