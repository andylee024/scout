"""SQLite persistence for external lead sync links."""

from __future__ import annotations

import sqlite3

from scout.collaboration.models import SyncLink


class SyncLinkStore:
    """Persistent mapping between Scout leads and external collaboration records."""

    def __init__(self, db_path: str = "outputs/collaboration_sync.db") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sync_links (
                lead_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                external_id TEXT NOT NULL,
                external_identifier TEXT,
                external_url TEXT,
                last_synced_at TEXT NOT NULL,
                last_action TEXT NOT NULL,
                PRIMARY KEY (lead_id, provider)
            );
            CREATE INDEX IF NOT EXISTS idx_sync_links_provider_external
            ON sync_links(provider, external_id);
            """
        )
        self.conn.commit()

    def get_link(self, lead_id: str, provider: str = "linear") -> SyncLink | None:
        row = self.conn.execute(
            """
            SELECT lead_id, provider, external_id, external_identifier, external_url,
                   last_synced_at, last_action
            FROM sync_links
            WHERE lead_id = ? AND provider = ?
            """,
            (lead_id, provider),
        ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        return SyncLink(
            lead_id=str(payload["lead_id"]),
            provider=str(payload["provider"]),
            external_id=str(payload["external_id"]),
            external_identifier=str(payload.get("external_identifier") or ""),
            external_url=str(payload.get("external_url") or ""),
            last_synced_at=str(payload.get("last_synced_at") or ""),
            last_action=str(payload.get("last_action") or ""),
        )

    def upsert_link(self, link: SyncLink) -> None:
        self.conn.execute(
            """
            INSERT INTO sync_links (
                lead_id, provider, external_id, external_identifier, external_url,
                last_synced_at, last_action
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lead_id, provider) DO UPDATE SET
                external_id=excluded.external_id,
                external_identifier=excluded.external_identifier,
                external_url=excluded.external_url,
                last_synced_at=excluded.last_synced_at,
                last_action=excluded.last_action
            """,
            (
                link.lead_id,
                link.provider,
                link.external_id,
                link.external_identifier,
                link.external_url,
                link.last_synced_at,
                link.last_action,
            ),
        )
        self.conn.commit()

    def count_links(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS count FROM sync_links").fetchone()
        if row is None:
            return 0
        return int(row["count"])
