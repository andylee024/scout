"""Canonical contact model."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

# Clodo CSV column name → Contact field name
_CLODO_FIELD_MAP = {
    "First Name": "first_name",
    "Last Name": "last_name",
    "Title": "title",
    "Company": "company",
    "Company Website": "website",
    "Website": "website",  # fallback alias
    "Email": "email",
    "LinkedIn": "linkedin",
    "Intent": "intent",
    "City": "city",
    "State": "state",
    "Why": "why",
    "Signals": "signals",
}

# Full state name → 2-letter abbreviation
_STATE_ABBREV = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}


def _normalize_state(raw: str) -> str:
    """Convert a state name or abbreviation to 2-letter code."""
    s = raw.strip()
    if len(s) == 2:
        return s.upper()
    return _STATE_ABBREV.get(s.lower(), s)


@dataclass
class Contact:
    first_name: str = ""
    last_name: str = ""
    title: str = ""
    company: str = ""
    email: str = ""
    linkedin: str = ""
    website: str = ""
    intent: str = ""
    city: str = ""
    state: str = ""
    why: str = ""
    signals: str = ""
    source: str = "clodo"
    business_id: str | None = None

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Contact:
        """Create from a Clodo CSV row (original column headers)."""
        kwargs: dict[str, Any] = {}
        for csv_col, field_name in _CLODO_FIELD_MAP.items():
            raw = row.get(csv_col)
            if raw is None:
                continue  # don't overwrite an already-set value with ""
            val = str(raw).strip()
            if field_name == "state" and val:
                val = _normalize_state(val)
            kwargs[field_name] = val
        kwargs["source"] = "clodo"
        return cls(**kwargs)

    @classmethod
    def from_normalized_row(cls, row: dict[str, str]) -> Contact:
        """Create from a normalized CSV row (snake_case headers)."""
        return cls(
            first_name=str(row.get("first_name", "")).strip(),
            last_name=str(row.get("last_name", "")).strip(),
            title=str(row.get("title", "")).strip(),
            company=str(row.get("company", "")).strip(),
            email=str(row.get("email", "")).strip(),
            linkedin=str(row.get("linkedin", "")).strip(),
            website=str(row.get("website", "")).strip(),
            intent=str(row.get("intent", "")).strip(),
            city=str(row.get("city", "")).strip(),
            state=str(row.get("state", "")).strip(),
            why=str(row.get("why", "")).strip(),
            signals=str(row.get("signals", "")).strip(),
            source=str(row.get("source", "clodo")).strip(),
            business_id=row.get("business_id") or None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    def to_supabase_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "title": self.title,
            "company": self.company,
            "email": self.email,
            "linkedin": self.linkedin,
            "website": self.website,
            "intent": self.intent,
            "city": self.city,
            "state": self.state,
            "why": self.why,
            "signals": self.signals,
            "source": self.source,
        }
        if self.business_id:
            row["business_id"] = self.business_id
        return row
