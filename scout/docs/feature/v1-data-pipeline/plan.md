# v1 Data Pipeline Plan

**Status:** Active roadmap  
**Last Updated:** 2026-03-21  
**Scope:** Data pipeline only

## Current State

```text
scout run
  -> Query
  -> Runner
  -> Workflow
      -> GoogleMapsDataSource
      -> BizBuySellDataSource
  -> Supabase businesses
  -> MarketDataset businesses + listings
  
helper commands
  -> scrape-businesses / ingest-contacts
  -> upload-businesses / upload-contacts
  -> match-contacts / pull-leads / verify
  -> CSV exports + Supabase tables/views
```

Supabase is the active store. Raw snapshot persistence is not active, and listings are not yet persisted by the current store.

## Immediate Priorities

1. Wire Clodo owner/contact ingestion into the canonical pipeline instead of keeping it in helper commands.
2. Add Google reviews as a review-signal source keyed by `place_id`.
3. Add a merge stage that produces canonical `Lead` and `OwnerContact` records.
4. Persist merged records to Supabase.
5. Decide whether marketplace listings should become first-class persisted records or remain run-level output only.

## Guardrails

1. Keep one pipeline path only.
2. Keep the current no-op raw persistence behavior explicit until a real replay store is reintroduced.
3. Keep fail-soft behavior by source.
4. Keep source-specific quirks out of `Workflow`.
5. Prefer a small canonical model set over ad-hoc per-surface shapes.

## Definition Of Done For This Phase

1. A run can fetch businesses and listings reliably.
2. Owner contacts and reviews can be attached to the right businesses.
3. The database contains one clean lead-level review surface.
4. Reruns remain idempotent and auditable.

## Out Of Scope

1. Broad UI exploration.
2. Workflow orchestration beyond lead generation.
3. CRM replacement features.
4. Additional low-priority data sources before merge quality is correct.
