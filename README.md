# Scout

Scout is a data pipeline for SMB (small and medium business) acquisition research. Given a natural-language query like *"HVAC businesses in Los Angeles"*, it pulls business and listing data into a unified local dataset for partner review and outbound outreach.

## What it does

Scout runs an ETL pipeline across two core runtime data sources:

| Source | What it collects |
|---|---|
| **BizBuySell** | Business-for-sale listings (price, cash flow, broker, etc.) |
| **Google Maps** | Nearby businesses (address, phone, website, rating, reviews) |

Each source is scraped, normalized into canonical `Listing` or `Business` models, and persisted to a local SQLite database. The output is a `MarketDataset` containing businesses, listings, and per-source coverage stats. The lead-review TUI is still available for working through packaged owner-contact datasets while the Supabase review flow is being finalized.

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
# Add Reddit keys if you want supplemental sentiment

# Run a query
scout run "HVAC businesses in Los Angeles"

# Optional: open the packaged lead-review TUI
scout view --dataset fire-protection-ca-owner-contacts
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
│   ├── operator/           # Lead-review TUI and packaged datasets
│   ├── pipeline/
│   │   ├── runner.py       # Configures sources + store, kicks off a run
│   │   ├── workflow.py     # ETL orchestration (fetch → normalize → persist)
│   │   ├── models/         # Domain models (Query, Business, Listing, MarketDataset)
│   │   ├── data_sources/   # Pipeline-level source adapters
│   │   └── data_store/     # Persistence layer (SQLite)
│   ├── domain/             # Shared domain types
│   └── shared/             # Utilities (query parsing, etc.)
├── data_sources/           # Raw scraper implementations
│   ├── marketplaces/       # BizBuySell scraper + validation helpers
│   ├── maps/               # Google Maps / Places API
│   ├── sentiment/          # Supplemental Reddit sentiment
│   └── shared/             # Shared scraper utilities
├── tests/                  # Pytest suite (mirrors source structure)
├── scripts/                # One-off validation and playground scripts
├── docs/                   # Architecture notes and feature specs
├── outputs/                # Cached results and exports (gitignored)
├── pyproject.toml          # Package config, tool settings
└── requirements.txt        # Pinned dependencies
```

## Key concepts

- **Query** -- A parsed user request (industry + location + options).
- **DataSource** -- An adapter that can `fetch` raw data and `normalize` it into domain models.
- **Workflow** -- Iterates over data sources, runs fetch/normalize/persist for each one, and assembles the final `MarketDataset`.
- **Runner** -- Top-level entry point that wires up the default sources and store, then calls the workflow.
- **MarketDataset** -- The output of a pipeline run: businesses, listings, and coverage stats.

## API keys

Copy `.env.example` to `.env` and fill in:

| Key | Required for | Where to get it |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | Google Maps source | [Google Cloud Console](https://console.cloud.google.com/) (enable Places API) |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Optional Reddit sentiment | Reddit app credentials |

## Near-Term Merge Target

```text
google_maps      -> businesses ----\
bizbuysell       -> listings ------ +--> lead merge --> leads for review/outreach
clodo            -> owners --------/
google_reviews   -> review signals /

reddit sentiment -> supplemental context (sidecar, not in default merge)
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
```
