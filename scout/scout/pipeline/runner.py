"""Runner entrypoint for workflow execution."""

from __future__ import annotations

from scout.pipeline.data_sources.bizbuysell import BizBuySellDataSource
from scout.pipeline.data_sources.google_maps import GoogleMapsDataSource
from scout.pipeline.data_store.base import DataStore
from scout.pipeline.data_store.sqlite import SQLiteDataStore
from scout.pipeline.models.market_dataset import MarketDataset
from scout.pipeline.models.query import Query
from scout.pipeline.workflow import Workflow


class Runner:
    """Starts one workflow run."""

    def __init__(
        self,
        workflow: Workflow | None = None,
        data_store: DataStore | None = None,
    ) -> None:
        self.workflow = workflow or Workflow(
            data_sources=[
                GoogleMapsDataSource(),
                BizBuySellDataSource(),
            ],
            data_store=data_store or SQLiteDataStore(),
        )

    def run(self, industry: str, location: str, max_results: int = 100, use_cache: bool = True) -> MarketDataset:
        query = Query(
            industry=industry,
            location=location,
            max_results=max_results,
            use_cache=use_cache,
        )
        return self.workflow.run(query)
