# Scout Architecture

**Purpose:** Keep one simple, implementation-ready data pipeline architecture.  
**Last Updated:** 2026-03-21

## Canonical Terms

1. **Model**: typed data shape shared between components.
2. **Workflow**: stage-based orchestration engine.
3. **Runner**: entrypoint that starts one workflow run.
4. **DataSource**: source-specific fetch component.
5. **DataStore**: persistence layer for canonical data in Supabase.

## Current Canonical Models

1. `Query`
2. `Business`
3. `Listing`
4. `Contact`
5. `MarketDataset`

## Near-Term Canonical Models

1. `Lead`
2. `OwnerContact`

## ETL Flow

```text
[CLI / Scheduler / API]
          |
          v
       [Runner]
          |
          v
      [Workflow]
   fetch -> persist_raw hook -> normalize -> upsert businesses -> build dataset
          |
          v
 [canonical store: Supabase]
          |
          v
   [MarketDataset]
```

`persist_raw` is still part of the workflow contract, but the active Supabase store no-ops it today.

## Current Runtime

```text
scout run
  -> Query
  -> Workflow
      -> GoogleMapsDataSource -> businesses upserted to Supabase
      -> BizBuySellDataSource -> listings returned in MarketDataset
  -> SupabaseDataStore
  -> MarketDataset
```

This is the current production path for partner-review dataset generation.

## Database Helper Flow

```text
scout scrape-businesses
  -> Google Maps CSV export with place_id

scout ingest-contacts
  -> normalized contacts CSV

scout upload-businesses / upload-contacts
  -> Supabase businesses / contacts tables

scout match-contacts
  -> business_id links on contacts

scout pull-leads
  -> leads view export
```

## Source Roles

1. `GoogleMapsDataSource` discovers operating businesses.
2. `BizBuySellDataSource` discovers businesses-for-sale.
3. Clodo owner enrichment currently enters through `ingest-contacts` and `upload-contacts`, not the default runner.
4. `RedditDataSource` is optional supplemental sentiment and is not part of the default runner.
5. Google reviews are the next review-signal source and will join on `Business.place_id`.

## Merge Target

```text
google_maps      -> businesses ----\
bizbuysell       -> listings ------ +--> lead merge --> leads + owner_contacts
clodo            -> owners --------/
google_reviews   -> review signals /

reddit sentiment -> supplemental context
```

## Code Layout

```text
scout/scout/pipeline/
├── runner.py
├── workflow.py
├── models/
│   ├── query.py
│   ├── business.py
│   ├── listing.py
│   ├── contact.py
│   └── market_dataset.py
├── data_sources/
│   ├── base.py
│   ├── google_maps.py
│   ├── bizbuysell.py
│   └── reddit.py
├── supabase_service.py
└── data_store/
    ├── base.py
    └── supabase.py
```

## Architecture Rules

1. Keep provider-specific behavior inside provider and DataSource code.
2. Keep `Workflow` generic: orchestration, fail-soft handling, and dataset assembly only.
3. The workflow keeps a raw-persistence hook, but the active Supabase store does not persist raw payloads.
4. Normalize into canonical models before writing canonical tables.
5. Treat each source as optional; partial runs are valid.
6. Keep one canonical pipeline path. Shared review happens in database surfaces, not a repo-owned UI.

## Historical Carry-Forward

These lessons are still worth keeping from the earlier listings work:

1. Marketplace ingestion must be treated as a pipeline, not an ad-hoc live query.
2. Query fidelity requires post-fetch normalization and relevance validation.
3. Idempotent canonical storage is required for repeatable runs and benchmarking.
4. Source quirks should stay isolated inside provider-specific code.
5. Source payload persistence is useful for replay, debugging, and schema drift handling, but it is not active in the current store.

## Source-Specific Notes

- `docs/feature/v1-data-pipeline/bizbuysell-notes.md`
