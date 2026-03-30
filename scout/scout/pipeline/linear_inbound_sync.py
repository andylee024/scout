"""Inbound Linear sync for lead-linked collaboration state."""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"
REQUESTED_ACTION_PATTERN = re.compile(r"(?im)^\s*(?:requested|next)\s*action\s*:\s*(.+?)\s*$")
REQUESTED_ACTION_LABEL_PREFIXES = ("requested-action:", "requested_action:", "action:")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None

    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _is_newer_or_equal(incoming: str, current: str) -> bool:
    incoming_ts = _parse_timestamp(incoming)
    current_ts = _parse_timestamp(current)

    if incoming_ts and current_ts:
        return incoming_ts >= current_ts
    if incoming_ts and not current_ts:
        return True
    if not incoming_ts and current_ts:
        return False

    return False


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value.strip():
            return value
    return ""


@dataclass(frozen=True)
class LinearCommentSnapshot:
    external_id: str
    body: str
    author: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class LinearLeadSnapshot:
    lead_id: str
    linear_issue_id: str
    owner: str = ""
    owner_updated_at: str = ""
    requested_action: str = ""
    requested_action_updated_at: str = ""
    comments: tuple[LinearCommentSnapshot, ...] = ()
    pulled_at: str = field(default_factory=_utc_now_iso)


@dataclass(frozen=True)
class LeadCollaborationState:
    lead_id: str
    linear_issue_id: str
    owner: str = ""
    owner_updated_at: str = ""
    requested_action: str = ""
    requested_action_updated_at: str = ""
    last_synced_at: str = ""


@dataclass(frozen=True)
class LeadCollaborationNote:
    lead_id: str
    source: str
    external_id: str
    author: str
    body: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class FieldConflict:
    field_name: str
    local_value: str
    incoming_value: str
    local_updated_at: str
    incoming_updated_at: str


@dataclass(frozen=True)
class ReconciliationResult:
    lead_id: str
    linear_issue_id: str
    owner_applied: bool
    requested_action_applied: bool
    notes_upserted: int
    conflicts: tuple[FieldConflict, ...] = ()


class LeadCollaborationStore:
    """SQLite persistence for lead links, canonical collaboration state, and lead-linked notes."""

    def __init__(self, db_path: str | Path = "outputs/pipeline/canonical.db") -> None:
        self.db_path = Path(db_path)
        if self.db_path != Path(":memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        cursor = self.conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS lead_linear_links (
                lead_id TEXT PRIMARY KEY,
                linear_issue_id TEXT NOT NULL,
                linked_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lead_collaboration_state (
                lead_id TEXT PRIMARY KEY,
                linear_issue_id TEXT NOT NULL,
                owner TEXT NOT NULL DEFAULT '',
                owner_updated_at TEXT NOT NULL DEFAULT '',
                requested_action TEXT NOT NULL DEFAULT '',
                requested_action_updated_at TEXT NOT NULL DEFAULT '',
                last_synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lead_collaboration_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                source TEXT NOT NULL,
                external_id TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(lead_id, source, external_id)
            );
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def link_lead(self, lead_id: str, linear_issue_id: str, linked_at: str = "") -> None:
        ts = _first_non_empty(linked_at, _utc_now_iso())
        self.conn.execute(
            """
            INSERT INTO lead_linear_links (lead_id, linear_issue_id, linked_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(lead_id) DO UPDATE SET
                linear_issue_id=excluded.linear_issue_id,
                updated_at=excluded.updated_at
            """,
            (lead_id, linear_issue_id, ts, ts),
        )
        self.conn.commit()

    def get_linked_issue_id(self, lead_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT linear_issue_id FROM lead_linear_links WHERE lead_id = ?", (lead_id,)
        ).fetchone()
        if row is None:
            return None
        return str(row["linear_issue_id"])

    def get_state(self, lead_id: str) -> LeadCollaborationState | None:
        row = self.conn.execute(
            """
            SELECT lead_id, linear_issue_id, owner, owner_updated_at, requested_action,
                   requested_action_updated_at, last_synced_at
            FROM lead_collaboration_state
            WHERE lead_id = ?
            """,
            (lead_id,),
        ).fetchone()

        if row is None:
            return None

        return LeadCollaborationState(
            lead_id=str(row["lead_id"]),
            linear_issue_id=str(row["linear_issue_id"]),
            owner=str(row["owner"]),
            owner_updated_at=str(row["owner_updated_at"]),
            requested_action=str(row["requested_action"]),
            requested_action_updated_at=str(row["requested_action_updated_at"]),
            last_synced_at=str(row["last_synced_at"]),
        )

    def upsert_state(self, state: LeadCollaborationState) -> None:
        self.conn.execute(
            """
            INSERT INTO lead_collaboration_state (
                lead_id, linear_issue_id, owner, owner_updated_at, requested_action,
                requested_action_updated_at, last_synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lead_id) DO UPDATE SET
                linear_issue_id=excluded.linear_issue_id,
                owner=excluded.owner,
                owner_updated_at=excluded.owner_updated_at,
                requested_action=excluded.requested_action,
                requested_action_updated_at=excluded.requested_action_updated_at,
                last_synced_at=excluded.last_synced_at
            """,
            (
                state.lead_id,
                state.linear_issue_id,
                state.owner,
                state.owner_updated_at,
                state.requested_action,
                state.requested_action_updated_at,
                state.last_synced_at,
            ),
        )
        self.conn.commit()

    def upsert_linear_comments(
        self,
        lead_id: str,
        comments: Iterable[LinearCommentSnapshot],
        fallback_ts: str = "",
    ) -> int:
        changed = 0

        for comment in comments:
            if not comment.external_id.strip():
                continue

            body = comment.body.strip()
            if not body:
                continue

            created_at = _first_non_empty(comment.created_at, comment.updated_at, fallback_ts, _utc_now_iso())
            updated_at = _first_non_empty(comment.updated_at, comment.created_at, fallback_ts, created_at)

            existing = self.conn.execute(
                """
                SELECT author, body, updated_at
                FROM lead_collaboration_notes
                WHERE lead_id = ? AND source = 'linear' AND external_id = ?
                """,
                (lead_id, comment.external_id),
            ).fetchone()

            if existing is None:
                self.conn.execute(
                    """
                    INSERT INTO lead_collaboration_notes (
                        lead_id, source, external_id, author, body, created_at, updated_at
                    ) VALUES (?, 'linear', ?, ?, ?, ?, ?)
                    """,
                    (lead_id, comment.external_id, comment.author, body, created_at, updated_at),
                )
                changed += 1
                continue

            existing_updated_at = str(existing["updated_at"])
            should_update = _is_newer_or_equal(updated_at, existing_updated_at)
            is_same = (
                str(existing["author"]) == comment.author
                and str(existing["body"]) == body
                and existing_updated_at == updated_at
            )

            if should_update and not is_same:
                self.conn.execute(
                    """
                    UPDATE lead_collaboration_notes
                    SET author = ?, body = ?, updated_at = ?
                    WHERE lead_id = ? AND source = 'linear' AND external_id = ?
                    """,
                    (comment.author, body, updated_at, lead_id, comment.external_id),
                )
                changed += 1

        self.conn.commit()
        return changed

    def list_notes(self, lead_id: str, source: str | None = None) -> list[LeadCollaborationNote]:
        if source is None:
            rows = self.conn.execute(
                """
                SELECT lead_id, source, external_id, author, body, created_at, updated_at
                FROM lead_collaboration_notes
                WHERE lead_id = ?
                ORDER BY created_at, external_id
                """,
                (lead_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT lead_id, source, external_id, author, body, created_at, updated_at
                FROM lead_collaboration_notes
                WHERE lead_id = ? AND source = ?
                ORDER BY created_at, external_id
                """,
                (lead_id, source),
            ).fetchall()

        return [
            LeadCollaborationNote(
                lead_id=str(row["lead_id"]),
                source=str(row["source"]),
                external_id=str(row["external_id"]),
                author=str(row["author"]),
                body=str(row["body"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]


class LinearInboundReconciler:
    """Reconciles normalized Linear lead snapshots into canonical Scout collaboration state."""

    def __init__(self, store: LeadCollaborationStore) -> None:
        self.store = store

    def reconcile_snapshot(self, snapshot: LinearLeadSnapshot) -> ReconciliationResult:
        self.store.link_lead(snapshot.lead_id, snapshot.linear_issue_id, linked_at=snapshot.pulled_at)
        existing = self.store.get_state(snapshot.lead_id)

        owner = existing.owner if existing else ""
        owner_updated_at = existing.owner_updated_at if existing else ""
        requested_action = existing.requested_action if existing else ""
        requested_action_updated_at = existing.requested_action_updated_at if existing else ""

        owner_result = self._reconcile_field(
            field_name="owner",
            local_value=owner,
            local_updated_at=owner_updated_at,
            incoming_value=snapshot.owner,
            incoming_updated_at=snapshot.owner_updated_at,
        )
        owner = owner_result.value
        owner_updated_at = owner_result.updated_at

        requested_action_result = self._reconcile_field(
            field_name="requested_action",
            local_value=requested_action,
            local_updated_at=requested_action_updated_at,
            incoming_value=snapshot.requested_action,
            incoming_updated_at=snapshot.requested_action_updated_at,
        )
        requested_action = requested_action_result.value
        requested_action_updated_at = requested_action_result.updated_at

        state = LeadCollaborationState(
            lead_id=snapshot.lead_id,
            linear_issue_id=snapshot.linear_issue_id,
            owner=owner,
            owner_updated_at=owner_updated_at,
            requested_action=requested_action,
            requested_action_updated_at=requested_action_updated_at,
            last_synced_at=snapshot.pulled_at,
        )
        self.store.upsert_state(state)

        notes_upserted = self.store.upsert_linear_comments(
            lead_id=snapshot.lead_id,
            comments=snapshot.comments,
            fallback_ts=snapshot.pulled_at,
        )

        conflicts = [item for item in (owner_result.conflict, requested_action_result.conflict) if item]
        return ReconciliationResult(
            lead_id=snapshot.lead_id,
            linear_issue_id=snapshot.linear_issue_id,
            owner_applied=owner_result.applied,
            requested_action_applied=requested_action_result.applied,
            notes_upserted=notes_upserted,
            conflicts=tuple(conflicts),
        )

    @dataclass(frozen=True)
    class _ReconciledField:
        value: str
        updated_at: str
        applied: bool
        conflict: FieldConflict | None = None

    def _reconcile_field(
        self,
        field_name: str,
        local_value: str,
        local_updated_at: str,
        incoming_value: str,
        incoming_updated_at: str,
    ) -> _ReconciledField:
        local_value = local_value or ""
        local_updated_at = local_updated_at or ""
        incoming_value = incoming_value or ""
        incoming_updated_at = incoming_updated_at or ""

        if local_value == incoming_value:
            if _is_newer_or_equal(incoming_updated_at, local_updated_at):
                next_updated_at = _first_non_empty(incoming_updated_at, local_updated_at)
                applied = bool(next_updated_at and next_updated_at != local_updated_at)
                return self._ReconciledField(
                    value=local_value,
                    updated_at=next_updated_at,
                    applied=applied,
                )
            return self._ReconciledField(
                value=local_value,
                updated_at=local_updated_at,
                applied=False,
            )

        if not local_value and not local_updated_at:
            return self._ReconciledField(
                value=incoming_value,
                updated_at=_first_non_empty(incoming_updated_at),
                applied=bool(incoming_value),
            )

        if not incoming_updated_at:
            return self._ReconciledField(
                value=local_value,
                updated_at=local_updated_at,
                applied=False,
                conflict=FieldConflict(
                    field_name=field_name,
                    local_value=local_value,
                    incoming_value=incoming_value,
                    local_updated_at=local_updated_at,
                    incoming_updated_at=incoming_updated_at,
                ),
            )

        if local_value and not local_updated_at:
            return self._ReconciledField(
                value=local_value,
                updated_at=local_updated_at,
                applied=False,
                conflict=FieldConflict(
                    field_name=field_name,
                    local_value=local_value,
                    incoming_value=incoming_value,
                    local_updated_at=local_updated_at,
                    incoming_updated_at=incoming_updated_at,
                ),
            )

        if _is_newer_or_equal(incoming_updated_at, local_updated_at):
            return self._ReconciledField(
                value=incoming_value,
                updated_at=incoming_updated_at,
                applied=True,
            )

        return self._ReconciledField(
            value=local_value,
            updated_at=local_updated_at,
            applied=False,
            conflict=FieldConflict(
                field_name=field_name,
                local_value=local_value,
                incoming_value=incoming_value,
                local_updated_at=local_updated_at,
                incoming_updated_at=incoming_updated_at,
            ),
        )


class LinearIssueClient:
    """Small GraphQL client for pulling one Linear issue by id."""

    ISSUE_QUERY = """
    query($id: String!) {
      issue(id: $id) {
        id
        updatedAt
        description
        assignee {
          name
          email
        }
        labels {
          nodes {
            name
          }
        }
        comments {
          nodes {
            id
            body
            createdAt
            updatedAt
            user {
              name
              email
            }
          }
        }
      }
    }
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str = LINEAR_GRAPHQL_URL,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("LINEAR_API_KEY", "")
        if not self.api_key:
            raise ValueError("LINEAR_API_KEY is required to pull Linear issue state")
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def fetch_issue(self, issue_id: str) -> dict[str, Any]:
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "query": self.ISSUE_QUERY,
            "variables": {"id": issue_id},
        }
        with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
            response = client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

        errors = body.get("errors", [])
        if errors:
            raise RuntimeError(f"Linear GraphQL error: {errors}")

        issue = body.get("data", {}).get("issue")
        if not issue:
            raise RuntimeError(f"Linear issue not found: {issue_id}")
        if not issue.get("id"):
            raise RuntimeError(f"Linear issue payload missing id: {issue_id}")
        return issue


def snapshot_from_linear_issue(
    lead_id: str,
    issue_payload: dict[str, Any],
    pulled_at: str = "",
) -> LinearLeadSnapshot:
    linear_issue_id = str(issue_payload.get("id", "")).strip()
    if not linear_issue_id:
        raise ValueError("issue payload must contain a non-empty id")

    assignee = issue_payload.get("assignee") or {}
    owner = str(assignee.get("email") or assignee.get("name") or "")
    owner_updated_at = str(issue_payload.get("updatedAt") or "")

    requested_action, requested_action_updated_at = _extract_requested_action(issue_payload)

    comments: list[LinearCommentSnapshot] = []
    comments_container = issue_payload.get("comments") or {}
    raw_comments = comments_container.get("nodes", []) if isinstance(comments_container, dict) else []
    for raw_comment in raw_comments:
        external_id = str(raw_comment.get("id") or "").strip()
        body = str(raw_comment.get("body") or "")
        if not external_id or not body.strip():
            continue
        user = raw_comment.get("user") or {}
        author = str(user.get("email") or user.get("name") or "")
        comments.append(
            LinearCommentSnapshot(
                external_id=external_id,
                body=body,
                author=author,
                created_at=str(raw_comment.get("createdAt") or ""),
                updated_at=str(raw_comment.get("updatedAt") or raw_comment.get("createdAt") or ""),
            )
        )

    return LinearLeadSnapshot(
        lead_id=lead_id,
        linear_issue_id=linear_issue_id,
        owner=owner,
        owner_updated_at=owner_updated_at,
        requested_action=requested_action,
        requested_action_updated_at=requested_action_updated_at,
        comments=tuple(comments),
        pulled_at=_first_non_empty(pulled_at, _utc_now_iso()),
    )


def _extract_requested_action(issue_payload: dict[str, Any]) -> tuple[str, str]:
    issue_updated_at = str(issue_payload.get("updatedAt") or "")

    labels_container = issue_payload.get("labels") or {}
    labels = labels_container.get("nodes", []) if isinstance(labels_container, dict) else []
    for label in labels:
        name = str(label.get("name") or "").strip()
        lower_name = name.lower()
        for prefix in REQUESTED_ACTION_LABEL_PREFIXES:
            if lower_name.startswith(prefix):
                value = name[len(prefix) :].strip()
                if value:
                    return value, issue_updated_at

    description = str(issue_payload.get("description") or "")
    description_match = REQUESTED_ACTION_PATTERN.search(description)
    if description_match:
        return description_match.group(1).strip(), issue_updated_at

    latest_value = ""
    latest_ts = ""
    comments_container = issue_payload.get("comments") or {}
    comments = comments_container.get("nodes", []) if isinstance(comments_container, dict) else []
    for raw_comment in comments:
        body = str(raw_comment.get("body") or "")
        comment_match = REQUESTED_ACTION_PATTERN.search(body)
        if not comment_match:
            continue

        candidate_value = comment_match.group(1).strip()
        candidate_ts = str(raw_comment.get("updatedAt") or raw_comment.get("createdAt") or issue_updated_at)
        if not latest_value or _is_newer_or_equal(candidate_ts, latest_ts):
            latest_value = candidate_value
            latest_ts = candidate_ts

    if latest_value:
        return latest_value, latest_ts

    return "", ""


class LinearInboundSyncService:
    """Pulls Linear issue state for linked leads and reconciles into Scout canonical state."""

    def __init__(
        self,
        store: LeadCollaborationStore,
        linear_client: LinearIssueClient | None = None,
        reconciler: LinearInboundReconciler | None = None,
    ) -> None:
        self.store = store
        self.linear_client = linear_client
        self.reconciler = reconciler or LinearInboundReconciler(store=store)

    def sync_linked_lead(self, lead_id: str) -> ReconciliationResult:
        issue_id = self.store.get_linked_issue_id(lead_id)
        if not issue_id:
            raise ValueError(f"lead is not linked to a Linear issue: {lead_id}")
        if self.linear_client is None:
            raise ValueError("linear_client is required for sync_linked_lead")

        issue_payload = self.linear_client.fetch_issue(issue_id)
        return self.reconcile_issue_payload(lead_id=lead_id, issue_payload=issue_payload)

    def reconcile_issue_payload(
        self,
        lead_id: str,
        issue_payload: dict[str, Any],
        pulled_at: str = "",
    ) -> ReconciliationResult:
        snapshot = snapshot_from_linear_issue(
            lead_id=lead_id,
            issue_payload=issue_payload,
            pulled_at=pulled_at,
        )
        return self.reconciler.reconcile_snapshot(snapshot)
