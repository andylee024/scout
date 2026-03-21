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
  -> raw snapshots
  -> canonical businesses + listings
  -> MarketDataset
```

SQLite is the default local store. Supabase is the shared review target.

## Immediate Priorities

1. Add `place_id` to the canonical `Business` model and persistence layer.
2. Add Clodo owner/contact ingestion.
3. Add Google reviews as a review-signal source keyed by `place_id`.
4. Add a merge stage that produces canonical `Lead` and `OwnerContact` records.
5. Persist merged records to Supabase.
6. Make downstream consumers read merged pipeline output instead of mock or packaged data.

## Guardrails

1. Keep one pipeline path only.
2. Persist raw payloads before normalization.
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
