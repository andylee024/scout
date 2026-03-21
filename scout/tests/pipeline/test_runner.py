from scout.pipeline.models.market_dataset import MarketDataset
from scout.pipeline.models.query import Query
from scout.pipeline.runner import Runner


class StubWorkflow:
    def __init__(self):
        self.last_query = None

    def run(self, query: Query) -> MarketDataset:
        self.last_query = query
        return MarketDataset(query=query)


def test_runner_builds_query_and_calls_workflow():
    workflow = StubWorkflow()
    runner = Runner(workflow=workflow)

    dataset = runner.run(industry="plumbing", location="Denver, CO", max_results=42, use_cache=False)

    assert dataset.query.industry == "plumbing"
    assert dataset.query.location == "Denver, CO"
    assert dataset.query.max_results == 42
    assert dataset.query.use_cache is False
    assert workflow.last_query is dataset.query


def test_runner_default_sources_focus_on_businesses_and_listings(monkeypatch):
    class StubSource:
        def __init__(self, name: str):
            self.name = name

    class StubStore:
        pass

    monkeypatch.setattr("scout.pipeline.runner.GoogleMapsDataSource", lambda: StubSource("google_maps"))
    monkeypatch.setattr("scout.pipeline.runner.BizBuySellDataSource", lambda: StubSource("bizbuysell"))
    monkeypatch.setattr("scout.pipeline.runner.get_supabase_store", StubStore)

    runner = Runner()

    assert [source.name for source in runner.workflow.data_sources] == [
        "google_maps",
        "bizbuysell",
    ]
