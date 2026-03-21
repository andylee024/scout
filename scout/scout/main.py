"""Scout CLI for pipeline and database workflows."""

from __future__ import annotations

import json

import click

from scout.pipeline.runner import Runner
from scout.shared.query_parser import parse_query


@click.group()
def cli() -> None:
    """Scout data pipeline CLI."""


# -------------------------------------------------------------------
# Legacy pipeline command
# -------------------------------------------------------------------


@cli.command("run")
@click.argument("query")
@click.option("--max-results", default=100, show_default=True, type=int)
@click.option("--no-cache", is_flag=True, default=False)
def run_pipeline(query: str, max_results: int, no_cache: bool) -> None:
    """Run one ETL pipeline execution from a natural-language query.

    Example: scout run "HVAC businesses in Los Angeles"
    """
    try:
        industry, location = parse_query(query)
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc

    runner = Runner()
    try:
        dataset = runner.run(
            industry=industry,
            location=location,
            max_results=max_results,
            use_cache=not no_cache,
        )
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc

    click.echo(f"run_id: {dataset.query.run_id}")
    click.echo(f"industry: {dataset.query.industry}")
    click.echo(f"location: {dataset.query.location}")
    click.echo(f"businesses: {len(dataset.businesses)}")
    click.echo(f"listings: {len(dataset.listings)}")

    for item in dataset.coverage:
        suffix = f" error={item.error}" if item.error else ""
        click.echo(
            f"source={item.source} status={item.status} records={item.records} "
            f"duration_ms={item.duration_ms}{suffix}"
        )


# -------------------------------------------------------------------
# Data pipeline commands (agent-friendly)
# -------------------------------------------------------------------


@cli.command("scrape-businesses")
@click.argument("industry")
@click.argument("location")
@click.option("--max-results", default=100, show_default=True, type=int)
@click.option("--no-cache", is_flag=True, default=False)
@click.option("--output", default=None, help="Output CSV path.")
def scrape_businesses_cmd(
    industry: str, location: str, max_results: int, no_cache: bool, output: str | None
) -> None:
    """Scrape Google Maps businesses to CSV.

    Example: scout scrape-businesses "fire protection" "California"
    """
    from scout.pipeline.supabase_service import scrape_businesses

    try:
        path = scrape_businesses(
            industry=industry,
            location=location,
            max_results=max_results,
            use_cache=not no_cache,
            output=output,
        )
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc
    click.echo(path)


@cli.command("ingest-contacts")
@click.argument("clodo_csv")
@click.option("--output", default=None, help="Output CSV path.")
def ingest_contacts_cmd(clodo_csv: str, output: str | None) -> None:
    """Normalize a Clodo CSV to a clean contacts CSV.

    Example: scout ingest-contacts data/clodo-ai-leads.csv
    """
    from scout.pipeline.supabase_service import ingest_contacts

    try:
        path = ingest_contacts(clodo_csv, output=output)
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc
    click.echo(path)


@cli.command("upload-businesses")
@click.argument("csv_path")
def upload_businesses_cmd(csv_path: str) -> None:
    """Upload a businesses CSV to Supabase.

    Example: scout upload-businesses outputs/businesses.csv
    """
    from scout.pipeline.supabase_service import upload_businesses

    try:
        count = upload_businesses(csv_path)
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{count} businesses upserted")


@cli.command("upload-contacts")
@click.argument("csv_path")
def upload_contacts_cmd(csv_path: str) -> None:
    """Upload a contacts CSV to Supabase.

    Example: scout upload-contacts outputs/contacts.csv
    """
    from scout.pipeline.supabase_service import upload_contacts

    try:
        count = upload_contacts(csv_path)
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{count} contacts upserted")


@cli.command("match-contacts")
def match_contacts_cmd() -> None:
    """Match unlinked contacts to businesses in Supabase."""
    from scout.pipeline.supabase_service import match_contacts

    try:
        count = match_contacts()
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{count} contacts matched")


@cli.command("backfill")
@click.option("--output", default=None, help="Output CSV path for new businesses.")
def backfill_cmd(output: str | None) -> None:
    """Look up unmatched contacts on Google Maps, upload, and re-match.

    Example: scout backfill
    """
    from scout.pipeline.supabase_service import backfill_from_contacts

    try:
        result = backfill_from_contacts(output=output)
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc
    click.echo(f"searched: {result['searched']}")
    click.echo(f"found: {result['found']}")
    click.echo(f"uploaded: {result['uploaded']}")
    click.echo(f"matched: {result['matched']}")


@cli.command("pull-leads")
@click.option("--output", default=None, help="Output CSV path.")
def pull_leads_cmd(output: str | None) -> None:
    """Pull merged leads from Supabase to CSV.

    Example: scout pull-leads --output leads.csv
    """
    from scout.pipeline.supabase_service import pull_leads

    try:
        path = pull_leads(output=output)
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc
    click.echo(path)


@cli.command("verify")
@click.argument("table")
def verify_cmd(table: str) -> None:
    """Print row count and sample rows for a Supabase table.

    Example: scout verify businesses
    """
    from scout.pipeline.supabase_service import verify

    try:
        result = verify(table)
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc
    click.echo(f"table: {result['table']}")
    click.echo(f"rows: {result['row_count']}")
    for row in result["sample_rows"]:
        click.echo(json.dumps(row, default=str))


if __name__ == "__main__":
    cli()
