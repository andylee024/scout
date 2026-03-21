# AGENTS.md

## Farm-Orchestrated Coding (Required)

For any coding task in this repository:

1. Read `/Users/andylee/Projects/farm/AGENTS.md` before starting.
2. Use Farm CLI as the control plane for Linear coding task lifecycle.
3. Do not create or move coding tasks via Linear MCP tools or ad-hoc scripts.
4. Keep planning/business logic in Farm skills/docs, not in repository orchestration scripts.

Recommended defaults:

- `FARM_CONFIG=/Users/andylee/Projects/farm/config.yaml`
- `REPO_KEY=scout`

Farm runtime commands (coding tasks):

```bash
farm run --config "$FARM_CONFIG" --repo "$REPO_KEY" --issue "<child-issue-id>"
farm update --config "$FARM_CONFIG" --repo "$REPO_KEY" --issue "<child-issue-id>" --phase running --summary "Current step"
farm finish --config "$FARM_CONFIG" --repo "$REPO_KEY" --issue "<child-issue-id>" --outcome completed --summary "Complete" --pr-url "<optional-pr-url>"
farm status --config "$FARM_CONFIG" --repo "$REPO_KEY" --issue "<child-issue-id>"
```

This file contains Scout-specific build, test, and coding guidance only.

## Repository Guidelines

## Project Structure & Module Organization
- `scout/` is the project root (Python package + configs). Key areas:
- `scout/scout/` — application code (CLI, pipeline, domain, adapters, shared).
- `scout/data_sources/` — acquisition layer (maps, marketplaces, sentiment).
- `scout/tests/` — pytest suite organized by area (`scout/`, `data_sources/`, `integration/`, `shared/`).
- `scout/config/` — config helpers.
- `scout/outputs/` — optional local CSV exports from helper commands.
- `scout/docs/` — architecture and feature notes.

## Build, Test, and Development Commands
Run commands from `scout/` (the project root):
- `python3 -m venv venv` and `source venv/bin/activate` — create/activate a virtualenv.
- `pip install -r requirements.txt` — install runtime dependencies.
- `pip install -e .` — editable install with CLI entrypoint (`scout`).
- `pip install -e ".[dev]"` — add dev tools (pytest, black, ruff).
- `scout run "HVAC in Los Angeles"` — run one pipeline query.
- `scout scrape-businesses "fire protection" "California"` — export Google Maps businesses to CSV.
- `scout upload-businesses outputs/businesses.csv` — upsert business rows into Supabase.
- `scout verify businesses` — smoke check a Supabase table.
- `pytest -v` — run the full test suite.
- `SCOUT_LIVE_TESTS=1 pytest tests/data_sources/test_smoke.py -v` — live smoke tests (uses external APIs).

## Coding Style & Naming Conventions
- Python, 4-space indentation.
- Formatting: `black` with 100-character lines.
- Linting: `ruff` with 100-character lines.
- Naming: `snake_case` for functions/vars, `CamelCase` for classes.
- Tests follow `test_*.py` and `test_*` function names (see pytest config).

## Testing Guidelines
- Framework: `pytest` (see `pyproject.toml`).
- Test locations: `tests/` with subpackages mirroring app areas.
- Keep unit tests deterministic; mark or gate live tests behind `SCOUT_LIVE_TESTS=1`.

## Commit & Pull Request Guidelines
- Commit messages follow a Conventional Commits style: `type: short summary` (e.g., `refactor: reorganize data_sources`).
- PRs should include a clear summary, testing notes (commands run), and link related issues.
- Include terminal captures or sample command output when behavior changes are CLI/data-flow visible.

## Security & Configuration Tips
- Secrets live in `.env` (template: `.env.example`). Do not commit API keys.
- External API calls can incur costs; prefer cached runs unless validating integrations.
