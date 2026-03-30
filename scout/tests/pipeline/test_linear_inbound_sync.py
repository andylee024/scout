import json

import httpx

from scout.pipeline.linear_inbound_sync import (
    LeadCollaborationState,
    LeadCollaborationStore,
    LinearInboundSyncService,
    LinearIssueClient,
    snapshot_from_linear_issue,
)


def _mock_linear_transport(expected_issue_id: str, issue_payload: dict[str, object]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        variables = body.get("variables", {})
        assert variables.get("id") == expected_issue_id
        return httpx.Response(200, json={"data": {"issue": issue_payload}})

    return httpx.MockTransport(handler)


def _issue_payload(
    issue_id: str,
    updated_at: str,
    owner_email: str,
    description: str,
    comments: list[dict[str, object]] | None = None,
    labels: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "id": issue_id,
        "updatedAt": updated_at,
        "description": description,
        "assignee": {"email": owner_email, "name": "Owner Name"},
        "labels": {"nodes": labels or []},
        "comments": {"nodes": comments or []},
    }


def test_sync_linked_lead_pulls_and_reconciles_owner_notes_and_requested_action():
    store = LeadCollaborationStore(":memory:")
    store.link_lead("lead-1", "lin-123")

    issue_payload = _issue_payload(
        issue_id="lin-123",
        updated_at="2026-03-11T07:00:00Z",
        owner_email="owner@scout.test",
        description="Requested action: Schedule intro call",
        comments=[
            {
                "id": "c-1",
                "body": "First collaborator note.",
                "createdAt": "2026-03-11T06:40:00Z",
                "updatedAt": "2026-03-11T06:40:00Z",
                "user": {"email": "analyst@scout.test"},
            },
            {
                "id": "c-2",
                "body": "Second collaborator note.",
                "createdAt": "2026-03-11T06:50:00Z",
                "updatedAt": "2026-03-11T06:55:00Z",
                "user": {"name": "Ops Reviewer"},
            },
        ],
    )

    client = LinearIssueClient(
        api_key="test-key",
        transport=_mock_linear_transport(expected_issue_id="lin-123", issue_payload=issue_payload),
    )
    service = LinearInboundSyncService(store=store, linear_client=client)

    result = service.sync_linked_lead("lead-1")

    state = store.get_state("lead-1")
    assert state is not None
    assert state.linear_issue_id == "lin-123"
    assert state.owner == "owner@scout.test"
    assert state.requested_action == "Schedule intro call"

    notes = store.list_notes("lead-1", source="linear")
    assert len(notes) == 2
    assert {note.external_id for note in notes} == {"c-1", "c-2"}

    assert result.owner_applied is True
    assert result.requested_action_applied is True
    assert result.notes_upserted == 2
    assert result.conflicts == ()


def test_reconcile_is_idempotent_for_linear_comments():
    store = LeadCollaborationStore(":memory:")
    service = LinearInboundSyncService(store=store)

    issue_payload = _issue_payload(
        issue_id="lin-abc",
        updated_at="2026-03-11T08:00:00Z",
        owner_email="owner@scout.test",
        description="Requested action: Validate comps",
        comments=[
            {
                "id": "c-1",
                "body": "Shared context from Linear.",
                "createdAt": "2026-03-11T07:55:00Z",
                "updatedAt": "2026-03-11T07:55:00Z",
                "user": {"email": "team@scout.test"},
            }
        ],
    )

    first = service.reconcile_issue_payload(
        lead_id="lead-2",
        issue_payload=issue_payload,
        pulled_at="2026-03-11T08:01:00Z",
    )
    second = service.reconcile_issue_payload(
        lead_id="lead-2",
        issue_payload=issue_payload,
        pulled_at="2026-03-11T08:02:00Z",
    )

    notes = store.list_notes("lead-2", source="linear")
    assert len(notes) == 1
    assert first.notes_upserted == 1
    assert second.notes_upserted == 0


def test_stale_linear_field_updates_do_not_overwrite_newer_local_state():
    store = LeadCollaborationStore(":memory:")
    store.link_lead("lead-3", "lin-789")
    store.upsert_state(
        LeadCollaborationState(
            lead_id="lead-3",
            linear_issue_id="lin-789",
            owner="local-owner@scout.test",
            owner_updated_at="2026-03-11T09:00:00Z",
            requested_action="Call seller this afternoon",
            requested_action_updated_at="2026-03-11T09:05:00Z",
            last_synced_at="2026-03-11T09:05:00Z",
        )
    )

    service = LinearInboundSyncService(store=store)
    issue_payload = _issue_payload(
        issue_id="lin-789",
        updated_at="2026-03-10T18:00:00Z",
        owner_email="older-owner@scout.test",
        description="Requested action: Send old follow-up",
        comments=[],
    )

    result = service.reconcile_issue_payload(
        lead_id="lead-3",
        issue_payload=issue_payload,
        pulled_at="2026-03-11T10:00:00Z",
    )

    state = store.get_state("lead-3")
    assert state is not None
    assert state.owner == "local-owner@scout.test"
    assert state.requested_action == "Call seller this afternoon"
    assert state.last_synced_at == "2026-03-11T10:00:00Z"

    conflict_fields = {conflict.field_name for conflict in result.conflicts}
    assert conflict_fields == {"owner", "requested_action"}
    assert result.owner_applied is False
    assert result.requested_action_applied is False


def test_snapshot_requested_action_extraction_prefers_labels_then_falls_back_to_comments():
    from_label = _issue_payload(
        issue_id="lin-label",
        updated_at="2026-03-11T11:00:00Z",
        owner_email="owner@scout.test",
        description="Requested action: From description",
        labels=[{"name": "requested-action:Book site visit"}],
    )
    label_snapshot = snapshot_from_linear_issue("lead-4", from_label, pulled_at="2026-03-11T11:01:00Z")

    assert label_snapshot.requested_action == "Book site visit"
    assert label_snapshot.requested_action_updated_at == "2026-03-11T11:00:00Z"

    from_comment = _issue_payload(
        issue_id="lin-comment",
        updated_at="2026-03-11T11:10:00Z",
        owner_email="owner@scout.test",
        description="",
        comments=[
            {
                "id": "c-1",
                "body": "Requested action: Old action",
                "createdAt": "2026-03-11T11:00:00Z",
                "updatedAt": "2026-03-11T11:00:00Z",
                "user": {"name": "One"},
            },
            {
                "id": "c-2",
                "body": "Requested action: New action",
                "createdAt": "2026-03-11T11:04:00Z",
                "updatedAt": "2026-03-11T11:05:00Z",
                "user": {"name": "Two"},
            },
        ],
    )
    comment_snapshot = snapshot_from_linear_issue("lead-5", from_comment, pulled_at="2026-03-11T11:11:00Z")

    assert comment_snapshot.requested_action == "New action"
    assert comment_snapshot.requested_action_updated_at == "2026-03-11T11:05:00Z"
