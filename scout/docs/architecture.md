# Scout Architecture

**Purpose:** Keep one simple, implementation-ready data pipeline architecture.  
**Last Updated:** 2026-03-21

## Canonical Terms

1. **Model**: typed data shape shared between components.
2. **Workflow**: stage-based orchestration engine.
3. **Runner**: entrypoint that starts one workflow run.
4. **DataSource**: source-specific fetch component.
5. **DataStore**: persistence layer for raw + canonical data.

## Current Canonical Models

1. `Query`
2. `Business`
3. `Listing`
4. `MarketDataset`

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
   fetch -> persist raw -> normalize -> upsert -> build dataset
          |
          +-----------------------------------+
          |                                   |
          v                                   v
[raw snapshots]                  [canonical store: SQLite / Supabase]
          \                                   /
           \                                 /
            +-------------v-----------------+
                          |
                   [MarketDataset]
```

## Current Runtime

```text
scout run
  -> Query
  -> Workflow
      -> GoogleMapsDataSource -> businesses
      -> BizBuySellDataSource -> listings
  -> SQLiteDataStore by default
  -> SupabaseDataStore optionally
  -> MarketDataset
```

This is the current production path for partner-review dataset generation.

## Source Roles

1. `GoogleMapsDataSource` discovers operating businesses.
2. `BizBuySellDataSource` discovers businesses-for-sale.
3. `RedditDataSource` is optional supplemental sentiment and is not part of the default runner.
4. Clodo owner enrichment and Google reviews are the next merge inputs.

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
│   └── market_dataset.py
├── data_sources/
│   ├── base.py
│   ├── google_maps.py
│   ├── bizbuysell.py
│   └── reddit.py
└── data_store/
    ├── base.py
    ├── raw_snapshot.py
    ├── sqlite.py
    └── supabase.py
```

## Architecture Rules

1. Keep provider-specific behavior inside provider and DataSource code.
2. Keep `Workflow` generic: orchestration, fail-soft handling, and dataset assembly only.
3. Persist raw payloads before normalization.
4. Normalize into canonical models before writing canonical tables.
5. Treat each source as optional; partial runs are valid.
6. Keep one canonical pipeline path. The TUI is a consumer, not a parallel architecture.

## Historical Carry-Forward

These lessons are still worth keeping from the earlier listings work:

1. Marketplace ingestion must be treated as a pipeline, not an ad-hoc live query.
2. Query fidelity requires post-fetch normalization and relevance validation.
3. Idempotent canonical storage is required for repeatable runs and benchmarking.
4. Source quirks should stay isolated inside provider-specific code.
5. Source payload persistence is useful for replay, debugging, and schema drift handling.

## Source-Specific Notes

- `docs/feature/v1-data-pipeline/bizbuysell-notes.md`
