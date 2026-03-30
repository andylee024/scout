"""Idempotent curated-lead sync into Linear."""

from __future__ import annotations

from datetime import datetime, timezone

from scout.collaboration.linear import LinearAdapter
from scout.collaboration.models import CuratedLead, LeadSyncResult, SyncLink
from scout.collaboration.store import SyncLinkStore


class CuratedLeadLinearSyncService:
    """Push curated leads to Linear and persist local external-record links."""

    def __init__(
        self,
        *,
        linear_adapter: LinearAdapter,
        link_store: SyncLinkStore,
        provider: str = "linear",
    ) -> None:
        self.linear_adapter = linear_adapter
        self.link_store = link_store
        self.provider = provider

    def sync_lead(self, lead: CuratedLead) -> LeadSyncResult:
        title = self._build_title(lead)
        description = self._build_description(lead)
        synced_at = datetime.now(tz=timezone.utc).isoformat()
        existing = self.link_store.get_link(lead.lead_id, provider=self.provider)

        if existing is None:
            issue = self.linear_adapter.create_issue(title=title, description=description)
            action = "created"
        else:
            issue = self.linear_adapter.update_issue(
                issue_id=existing.external_id,
                title=title,
                description=description,
            )
            action = "updated"

        link = SyncLink(
            lead_id=lead.lead_id,
            provider=self.provider,
            external_id=issue.id,
            external_identifier=issue.identifier,
            external_url=issue.url,
            last_synced_at=synced_at,
            last_action=action,
        )
        self.link_store.upsert_link(link)

        return LeadSyncResult(
            lead_id=lead.lead_id,
            provider=self.provider,
            action=action,
            external_id=issue.id,
            external_identifier=issue.identifier,
            external_url=issue.url,
            synced_at=synced_at,
        )

    @staticmethod
    def _build_title(lead: CuratedLead) -> str:
        if not lead.location:
            return lead.name
        return f"{lead.name} ({lead.location})"

    @staticmethod
    def _build_description(lead: CuratedLead) -> str:
        lines = [
            "## Scout Curated Lead",
            "",
            f"- Scout Lead ID: `{lead.lead_id}`",
            f"- Name: {lead.name}",
            f"- Location: {lead.location or 'N/A'}",
            f"- Source URL: {lead.source_url or 'N/A'}",
            "",
            "### Summary",
            lead.summary or "N/A",
            "",
            "### Notes",
            lead.notes or "N/A",
        ]
        return "\n".join(lines)
