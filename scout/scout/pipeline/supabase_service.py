"""Supabase service layer for the Scout data pipeline.

Stateless methods that an AI agent (or CLI) can call to scrape, ingest,
upload, match, pull, and verify lead data.
"""

from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scout.pipeline.models.business import Business
from scout.pipeline.models.contact import Contact

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}


def _extract_city(address: str) -> str:
    """Parse city from a Google Maps formatted address.

    Typical formats:
        "123 Main St, Houston, TX 77001, USA"
        "Houston, TX, USA"
        "Los Angeles, CA"
    """
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",")]
    # Walk backwards looking for the part just before a state token
    for i in range(len(parts) - 1, 0, -1):
        token = parts[i].strip().split()[0] if parts[i].strip() else ""
        if token.upper() in _US_STATES:
            return parts[i - 1].strip()
    # Fallback: second-to-last comma-separated part often is the city
    if len(parts) >= 2:
        return parts[-2].strip()
    return ""


def _extract_state(address: str) -> str:
    """Parse 2-letter state code from a formatted address."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",")]
    for part in reversed(parts):
        tokens = part.strip().split()
        for token in tokens:
            cleaned = token.strip().rstrip(".,")
            if cleaned.upper() in _US_STATES:
                return cleaned.upper()
    return ""


def _extract_domain(url: str) -> str:
    """Normalize a URL to its bare domain (no www, no path)."""
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return ""
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _get_client():
    """Create a Supabase PostgREST client from env vars.

    Uses postgrest-py directly to avoid the supabase-py JWT format
    validation, which rejects newer ``sb_publishable_`` / ``sb_secret_``
    key formats.
    """
    from postgrest import SyncPostgrestClient

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be set as environment variables"
        )
    return SyncPostgrestClient(
        base_url=f"{url}/rest/v1",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
        },
    )


def _ensure_output_dir() -> Path:
    path = Path("outputs")
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Service methods
# ---------------------------------------------------------------------------


def scrape_businesses(
    industry: str,
    location: str,
    max_results: int = 100,
    use_cache: bool = True,
    output: str | None = None,
) -> str:
    """Scrape Google Maps for businesses, write CSV, return path."""
    from data_sources.maps.google_maps import GoogleMapsTool

    tool = GoogleMapsTool()
    payload = tool.search(
        industry=industry,
        location=location,
        max_results=max_results,
        use_cache=use_cache,
    )

    results: list[dict[str, Any]] = payload.get("results", []) or []

    out_dir = _ensure_output_dir()
    slug = f"{industry.replace(' ', '_')}_{location.replace(' ', '_')}"
    out_path = Path(output) if output else out_dir / f"businesses_{slug}.csv"

    fieldnames = [
        "source", "name", "place_id", "address", "city", "state",
        "phone", "website", "category", "rating", "reviews",
    ]
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in results:
            addr = str(item.get("address", ""))
            writer.writerow({
                "source": "google_maps",
                "name": str(item.get("name", "")),
                "place_id": str(item.get("place_id", "")),
                "address": addr,
                "city": _extract_city(addr),
                "state": _extract_state(addr),
                "phone": str(item.get("phone", "")),
                "website": str(item.get("website", "")),
                "category": str(item.get("category", industry)),
                "rating": item.get("rating", ""),
                "reviews": item.get("reviews", ""),
            })

    return str(out_path)


def ingest_contacts(clodo_csv_path: str, output: str | None = None) -> str:
    """Read a Clodo CSV, normalize columns, write clean CSV, return path."""
    contacts: list[Contact] = []
    with open(clodo_csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            contacts.append(Contact.from_csv_row(row))

    out_dir = _ensure_output_dir()
    out_path = Path(output) if output else out_dir / "contacts.csv"

    fieldnames = [
        "first_name", "last_name", "title", "company", "email",
        "linkedin", "website", "intent", "city", "state",
        "why", "signals", "source",
    ]
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for c in contacts:
            writer.writerow(c.to_dict())

    return str(out_path)


def upload_businesses(csv_path: str) -> int:
    """Read a businesses CSV and upsert rows to Supabase. Returns count."""
    client = _get_client()

    rows: list[dict[str, Any]] = []
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not row.get("name"):
                continue
            rows.append({
                "source": row.get("source", "google_maps"),
                "name": row["name"],
                "place_id": row.get("place_id", ""),
                "address": row.get("address", ""),
                "city": row.get("city", ""),
                "state": row.get("state", ""),
                "phone": row.get("phone", ""),
                "website": row.get("website", ""),
                "category": row.get("category", ""),
                "rating": _to_float(row.get("rating")),
                "reviews": _to_int(row.get("reviews")),
            })

    if not rows:
        return 0

    batch_size = 500
    count = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        client.table("businesses").upsert(
            batch, on_conflict="source,name,address"
        ).execute()
        count += len(batch)
    return count


def upload_contacts(csv_path: str) -> int:
    """Read a contacts CSV and insert rows to Supabase. Returns count.

    Skips rows whose email already exists in the table to avoid duplicates.
    The contacts table has no unique constraint on email, so we filter
    client-side before inserting.
    """
    client = _get_client()

    # Fetch existing emails to skip duplicates
    existing_resp = client.table("contacts").select("email").execute()
    existing_emails: set[str] = {
        r["email"].lower() for r in (existing_resp.data or []) if r.get("email")
    }

    rows: list[dict[str, Any]] = []
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            contact = Contact.from_normalized_row(row)
            if not contact.company:
                continue  # company is NOT NULL in the table
            if contact.email and contact.email.lower() in existing_emails:
                continue  # skip duplicate
            rows.append(contact.to_supabase_row())

    if not rows:
        return 0

    batch_size = 500
    count = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        client.table("contacts").insert(batch).execute()
        count += len(batch)
    return count


def match_contacts() -> int:
    """Match contacts to businesses by domain, then by company name + state.

    Returns the number of contacts updated.
    """
    client = _get_client()

    # Pull all contacts without a business_id
    resp = (
        client.table("contacts")
        .select("id,company,website,city,state")
        .is_("business_id", "null")
        .execute()
    )
    unmatched = resp.data or []
    if not unmatched:
        return 0

    # Pull all businesses
    biz_resp = client.table("businesses").select("id,name,website,city,state").execute()
    businesses = biz_resp.data or []

    # Build lookup indices
    domain_to_biz: dict[str, str] = {}
    name_state_to_biz: dict[tuple[str, str], str] = {}
    for b in businesses:
        biz_id = b["id"]
        domain = _extract_domain(b.get("website", ""))
        if domain:
            domain_to_biz[domain] = biz_id
        name_key = (b.get("name", "").strip().lower(), (b.get("state") or "").upper())
        if name_key[0]:
            name_state_to_biz[name_key] = biz_id

    updated = 0
    for contact in unmatched:
        contact_id = contact["id"]
        match_id: str | None = None

        # Strategy 1: domain match
        c_domain = _extract_domain(contact.get("website", ""))
        if c_domain and c_domain in domain_to_biz:
            match_id = domain_to_biz[c_domain]

        # Strategy 2: company name + state
        if not match_id:
            c_key = (
                (contact.get("company") or "").strip().lower(),
                (contact.get("state") or "").upper(),
            )
            if c_key[0] and c_key in name_state_to_biz:
                match_id = name_state_to_biz[c_key]

        if match_id:
            client.table("contacts").update(
                {"business_id": match_id}
            ).eq("id", contact_id).execute()
            updated += 1

    return updated


def backfill_from_contacts(output: str | None = None) -> dict[str, int]:
    """Look up unmatched contacts on Google Maps, upload, and re-match.

    Returns dict with counts: searched, found, uploaded, matched.
    """
    from data_sources.maps.google_maps import GoogleMapsTool

    client = _get_client()
    tool = GoogleMapsTool()

    # 1. Pull unmatched contacts
    unmatched = (
        client.table("contacts")
        .select("company,city,state")
        .is_("business_id", "null")
        .execute()
    ).data or []

    # 2. Dedupe company+state pairs we already have
    existing = {
        (b["name"].strip().lower(), (b.get("state") or "").upper())
        for b in (client.table("businesses").select("name,state").execute().data or [])
    }

    # 3. Build unique lookups
    to_search: list[tuple[str, str]] = []
    seen: set[str] = set()
    for c in unmatched:
        company = (c.get("company") or "").strip()
        state = (c.get("state") or "").strip()
        city = (c.get("city") or "").strip()
        if not company or (company.lower(), state.upper()) in existing:
            continue
        key = f"{company}|{state}"
        if key not in seen:
            seen.add(key)
            location = f"{city}, {state}" if city else state
            to_search.append((company, location))

    # 4. Look up each on Google Maps (dedupe by place_id)
    found: list[dict[str, Any]] = []
    seen_places: set[str] = set()
    for company, location in to_search:
        biz = tool.lookup(company, location)
        if not biz:
            continue
        pid = str(biz.get("place_id", ""))
        if pid in seen_places:
            continue
        seen_places.add(pid)
        addr = str(biz.get("address", ""))
        found.append({
            "source": "google_maps",
            "name": str(biz.get("name", "")),
            "place_id": pid,
            "address": addr,
            "city": _extract_city(addr),
            "state": _extract_state(addr),
            "phone": str(biz.get("phone", "")),
            "website": str(biz.get("website", "")),
            "category": str(biz.get("category", "")),
            "rating": biz.get("rating", ""),
            "reviews": biz.get("reviews", ""),
        })

    # 5. Write CSV + upload + match
    out_path = Path(output) if output else _ensure_output_dir() / "businesses_backfill.csv"
    fieldnames = [
        "source", "name", "place_id", "address", "city", "state",
        "phone", "website", "category", "rating", "reviews",
    ]
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(found)

    uploaded = upload_businesses(str(out_path)) if found else 0
    matched = match_contacts()

    return {
        "searched": len(to_search),
        "found": len(found),
        "uploaded": uploaded,
        "matched": matched,
    }


def pull_leads(output: str | None = None) -> str:
    """Query the leads view and write results to CSV. Returns path."""
    client = _get_client()
    resp = client.table("leads").select("*").execute()
    rows = resp.data or []

    out_dir = _ensure_output_dir()
    out_path = Path(output) if output else out_dir / "leads.csv"

    if not rows:
        out_path.write_text("")
        return str(out_path)

    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return str(out_path)


def verify(table: str) -> dict[str, Any]:
    """Return row count and 5 sample rows for a table."""
    client = _get_client()
    count_resp = client.table(table).select("*", count="exact").limit(0).execute()
    sample_resp = client.table(table).select("*").limit(5).execute()
    return {
        "table": table,
        "row_count": count_resp.count if count_resp.count is not None else 0,
        "sample_rows": sample_resp.data or [],
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
