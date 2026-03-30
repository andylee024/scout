"""Models for outbound lead collaboration sync."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CuratedLead:
    """Canonical lead selected in Scout for collaboration workflows."""

    lead_id: str
    name: str
    location: str = ""
    summary: str = ""
    source_url: str = ""
    notes: str = ""


@dataclass
class SyncLink:
    """Local pointer from a canonical Scout lead to an external record."""

    lead_id: str
    provider: str
    external_id: str
    external_identifier: str = ""
    external_url: str = ""
    last_synced_at: str = ""
    last_action: str = ""


@dataclass
class LeadSyncResult:
    """Result emitted after syncing one curated lead to an external provider."""

    lead_id: str
    provider: str
    action: str
    external_id: str
    external_identifier: str = ""
    external_url: str = ""
    synced_at: str = ""
