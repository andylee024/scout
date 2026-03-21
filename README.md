# Scout

Scout is a data pipeline for SMB (small and medium business) acquisition research. Given a natural-language query like *"HVAC businesses in Los Angeles"*, it pulls business and listing data into Supabase-backed records and helper exports for partner review and outbound outreach.

## What it does

Scout runs an ETL pipeline across two core runtime data sources:

| Source | What it collects |
|---|---|
| **BizBuySell** | Business-for-sale listings (price, cash flow, broker, etc.) |
| **Google Maps** | Nearby businesses (address, phone, website, rating, reviews, `place_id`) |

`scout run` scrapes both sources, normalizes them into canonical `Business` and `Listing` models, upserts businesses into Supabase, and returns a `MarketDataset` with businesses, listings, and per-source coverage stats.

Today’s important boundary:
- `Business` rows are persisted to Supabase.
- `Listing` rows are returned in the run dataset, but the active Supabase store does not persist them yet.
- Raw source payload persistence is not active in the current store.

Reddit sentiment is retained as a supplemental source for market context, but it is not part of the default lead-building runner. The near-term merge target is `businesses + listings + clodo owner data + reviews`.

## Quick start

```bash
# Clone and set up
cd scout
python3 -m venv venv && source venv/bin/activate
pip install -e .

# Configure API keys
cp .env.example .env
# Edit .env with your Google Maps key
# Add SUPABASE_URL and SUPABASE_KEY for pipeline/database commands
# Add Reddit keys if you want supplemental sentiment

# Run a query
scout run "HVAC businesses in Los Angeles"

```

Output looks like:

```
run_id: abc123
industry: hvac
location: los angeles
businesses: 42
listings: 18
source=google_maps status=success records=42 duration_ms=3200
source=bizbuysell status=success records=18 duration_ms=5100
```

## Project structure

```
scout/
├── scout/                  # Application package
│   ├── main.py             # CLI entry point (Click)
│   ├── pipeline/
│   │   ├── runner.py       # Configures sources + store, kicks off a run
│   │   ├── workflow.py     # ETL orchestration (fetch → normalize → persist)
│   │   ├── models/         # Domain models (Query, Business, Listing, Contact, MarketDataset)
│   │   ├── data_sources/   # Pipeline-level source adapters
│   │   ├── data_store/     # Persistence layer (Supabase)
│   │   └── supabase_service.py  # CSV/Supabase helper commands
│   ├── domain/             # Shared domain types
│   └── shared/             # Utilities (query parsing, etc.)
├── data_sources/           # Raw scraper implementations
│   ├── marketplaces/       # BizBuySell scraper + validation helpers
│   ├── maps/               # Google Maps / Places API
│   ├── sentiment/          # Supplemental Reddit sentiment
│   └── shared/             # Shared scraper utilities
├── tests/                  # Pytest suite (mirrors source structure)
├── scripts/                # Schema and helper scripts
├── docs/                   # Architecture notes and feature specs
├── outputs/                # Local CSV exports from helper commands (gitignored)
├── pyproject.toml          # Package config, tool settings
└── requirements.txt        # Pinned dependencies
```

## Key concepts

- **Query** -- A parsed user request (industry + location + options).
- **DataSource** -- An adapter that can `fetch` raw data and `normalize` it into domain models.
- **Workflow** -- Iterates over data sources, runs fetch/normalize/persist for each one, and assembles the final `MarketDataset`.
- **Runner** -- Top-level entry point that wires up the default sources and store, then calls the workflow.
- **MarketDataset** -- The output of a pipeline run: businesses, listings, and coverage stats.
- **Contact** -- Normalized owner/contact record used by the Clodo ingestion/upload flow.

## API keys

Copy `.env.example` to `.env` and fill in:

| Key | Required for | Where to get it |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | Google Maps source | [Google Cloud Console](https://console.cloud.google.com/) (enable Places API) |
| `SUPABASE_URL` / `SUPABASE_KEY` | `scout run` and database helper commands | Supabase project settings |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Optional Reddit sentiment | Reddit app credentials |

## Near-Term Merge Target

```text
google_maps      -> businesses ----\
bizbuysell       -> listings ------ +--> lead merge --> leads for review/outreach
clodo            -> owners --------/
google_reviews   -> review signals /

reddit sentiment -> supplemental context (sidecar, not in default merge)
```

Current helper flow:

```text
scrape-businesses -> businesses.csv (includes place_id)
ingest-contacts   -> contacts.csv
upload-*          -> Supabase tables
match-contacts    -> businesses <-> contacts links
pull-leads        -> leads CSV export
verify            -> table smoke check
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Run live integration tests (hits real APIs)
SCOUT_LIVE_TESTS=1 pytest tests/data_sources/test_smoke.py -v

# Format and lint
black .
ruff check .
```

## CLI reference

```bash
scout run "HVAC businesses in Los Angeles"       # default: up to 100 results, cache enabled
scout run "plumbing in Texas" --max-results 50    # limit results
scout run "car wash in California" --no-cache     # skip cache, force fresh scrape
scout scrape-businesses "fire protection" "California"
scout ingest-contacts data/clodo.csv
scout upload-businesses outputs/businesses_fire_protection_California.csv
scout upload-contacts outputs/contacts.csv
scout match-contacts
scout pull-leads --output outputs/leads.csv
scout verify businesses
```
