from scout.collaboration.linear import LinearAdapter, LinearIssueRef
from scout.collaboration.models import CuratedLead
from scout.collaboration.store import SyncLinkStore
from scout.collaboration.sync import CuratedLeadLinearSyncService


class FakeLinearAdapter:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, str]] = []
        self.update_calls: list[dict[str, str]] = []
        self._next_id = 1

    def create_issue(self, *, title: str, description: str) -> LinearIssueRef:
        issue_id = f"lin-{self._next_id}"
        self._next_id += 1
        self.create_calls.append({"title": title, "description": description})
        return LinearIssueRef(
            id=issue_id,
            identifier=f"SCOUT-{100 + self._next_id}",
            url=f"https://linear.app/scout/issue/{issue_id}",
        )

    def update_issue(self, *, issue_id: str, title: str, description: str) -> LinearIssueRef:
        self.update_calls.append({"issue_id": issue_id, "title": title, "description": description})
        return LinearIssueRef(
            id=issue_id,
            identifier="SCOUT-UPDATED",
            url=f"https://linear.app/scout/issue/{issue_id}",
        )


def test_first_sync_creates_linear_issue_and_persists_link():
    adapter = FakeLinearAdapter()
    store = SyncLinkStore(":memory:")
    service = CuratedLeadLinearSyncService(linear_adapter=adapter, link_store=store)
    lead = CuratedLead(
        lead_id="lead-001",
        name="Atlas HVAC",
        location="Austin, TX",
        summary="Strong recurring maintenance contracts.",
        source_url="https://example.com/atlas-hvac",
        notes="Prioritize owner outreach this week.",
    )

    result = service.sync_lead(lead)

    assert result.action == "created"
    assert result.provider == "linear"
    assert result.external_id == "lin-1"
    assert len(adapter.create_calls) == 1
    assert len(adapter.update_calls) == 0
    assert "`lead-001`" in adapter.create_calls[0]["description"]
    assert "Atlas HVAC" in adapter.create_calls[0]["title"]

    link = store.get_link("lead-001", provider="linear")
    assert link is not None
    assert link.external_id == "lin-1"
    assert link.last_action == "created"
    assert store.count_links() == 1


def test_repeat_sync_updates_existing_issue_without_duplicate_records():
    adapter = FakeLinearAdapter()
    store = SyncLinkStore(":memory:")
    service = CuratedLeadLinearSyncService(linear_adapter=adapter, link_store=store)
    lead = CuratedLead(
        lead_id="lead-002",
        name="Summit Plumbing",
        location="Denver, CO",
        summary="Initial summary",
    )

    first = service.sync_lead(lead)
    lead.summary = "Updated summary after operator review"
    second = service.sync_lead(lead)

    assert first.action == "created"
    assert second.action == "updated"
    assert len(adapter.create_calls) == 1
    assert len(adapter.update_calls) == 1
    assert adapter.update_calls[0]["issue_id"] == first.external_id
    assert "Updated summary" in adapter.update_calls[0]["description"]

    link = store.get_link("lead-002", provider="linear")
    assert link is not None
    assert link.external_id == first.external_id
    assert link.last_action == "updated"
    assert store.count_links() == 1


def test_linear_adapter_create_then_update_uses_expected_payload_shape():
    seen_payloads: list[dict[str, object]] = []

    def fake_request(url: str, payload: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
        assert url == "https://api.linear.app/graphql"
        assert headers["Authorization"] == "token"
        seen_payloads.append(payload)

        query = payload.get("query", "")
        if "IssueCreate" in query:
            return {
                "data": {
                    "issueCreate": {
                        "success": True,
                        "issue": {
                            "id": "lin-created",
                            "identifier": "SCOUT-200",
                            "url": "https://linear.app/scout/issue/SCOUT-200",
                        },
                    }
                }
            }
        return {
            "data": {
                "issueUpdate": {
                    "success": True,
                    "issue": {
                        "id": "lin-created",
                        "identifier": "SCOUT-200",
                        "url": "https://linear.app/scout/issue/SCOUT-200",
                    },
                }
            }
        }

    adapter = LinearAdapter(api_key="token", team_id="team-1", request_fn=fake_request)

    created = adapter.create_issue(title="Lead title", description="Lead body")
    updated = adapter.update_issue(issue_id=created.id, title="Lead title v2", description="Lead body v2")

    assert created.id == "lin-created"
    assert updated.id == "lin-created"
    assert len(seen_payloads) == 2
    assert seen_payloads[0]["variables"]["input"]["teamId"] == "team-1"
    assert seen_payloads[1]["variables"]["id"] == "lin-created"
