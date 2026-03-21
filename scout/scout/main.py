"""Scout CLI for pipelines and lead review."""

from __future__ import annotations

import click

from scout.operator.tui.app import ScoutResearchApp
from scout.operator.tui.dataset_loader import dataset_names, load_dataset_state
from scout.operator.tui.mock_data import build_mock_state
from scout.pipeline.runner import Runner
from scout.shared.query_parser import parse_query


@click.group()
def cli() -> None:
    """Scout data pipeline and lead viewer CLI."""


@cli.command("run")
@click.argument("query")
@click.option("--max-results", default=100, show_default=True, type=int)
@click.option("--no-cache", is_flag=True, default=False)
@click.option(
    "--store",
    type=click.Choice(["sqlite", "supabase"]),
    default="sqlite",
    show_default=True,
    help="Persistence backend for pipeline results.",
)
def run_pipeline(query: str, max_results: int, no_cache: bool, store: str) -> None:
    """Run one ETL pipeline execution from a natural-language query.

    Example: scout run "HVAC businesses in Los Angeles"
    """
    try:
        industry, location = parse_query(query)
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc

    data_store = None
    if store == "supabase":
        from scout.pipeline.data_store import get_supabase_store

        data_store = get_supabase_store()

    runner = Runner(data_store=data_store)
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


def _build_view_state(query: str | None, mock: bool, dataset: str | None):
    if dataset:
        return load_dataset_state(dataset, query=query)

    if not query:
        raise click.ClickException("QUERY is required unless --dataset is provided.")

    if not mock:
        raise click.ClickException(
            "Live viewer mode is not implemented yet. Use the default mock mode."
        )

    return build_mock_state(query)


def _run_viewer(query: str | None, mock: bool, dataset: str | None) -> None:
    app = ScoutResearchApp(_build_view_state(query, mock, dataset))
    app.run()


@cli.command("view")
@click.argument("query", required=False)
@click.option(
    "--dataset",
    type=click.Choice(dataset_names()),
    default=None,
    help="Load a packaged lead dataset instead of generating mock rows from a query.",
)
@click.option("--mock/--live", default=True, show_default=True)
def view(query: str | None, dataset: str | None, mock: bool) -> None:
    """Launch the Scout lead viewer."""
    _run_viewer(query, mock, dataset)


if __name__ == "__main__":
    cli()
