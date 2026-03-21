"""Packaged lead datasets for the Scout TUI."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from importlib import resources

from scout.operator.tui.models import Lead, OwnerProfile, ScoutTuiState

_DATASET_PACKAGE = "scout.operator.tui.datasets"


@dataclass(frozen=True)
class DatasetSpec:
    """Metadata for one packaged lead dataset."""

    slug: str
    label: str
    default_query: str
    filename: str
    source: str = "packaged_dataset"


FIRE_PROTECTION_CA_OWNER_CONTACTS = DatasetSpec(
    slug="fire-protection-ca-owner-contacts",
    label="CA Fire Protection Owner Contacts",
    default_query="fire protection owner contacts in california",
    filename="fire_protection_ca_owner_contacts.csv",
    source="linkedin_contacts",
)

DATASETS: dict[str, DatasetSpec] = {
    FIRE_PROTECTION_CA_OWNER_CONTACTS.slug: FIRE_PROTECTION_CA_OWNER_CONTACTS,
}


def dataset_names() -> tuple[str, ...]:
    """Return the available packaged dataset names."""

    return tuple(DATASETS)


def load_dataset_state(name: str, *, query: str | None = None) -> ScoutTuiState:
    """Build TUI state from a packaged dataset."""

    normalized = name.strip().lower()
    spec = DATASETS.get(normalized)
    if spec is None:
        choices = ", ".join(sorted(DATASETS))
        raise ValueError(f"Unknown dataset `{name}`. Choose one of: {choices}")

    resource = resources.files(_DATASET_PACKAGE).joinpath(spec.filename)
    with resource.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        leads = [_lead_from_row(index, row, spec) for index, row in enumerate(reader, start=1)]

    return ScoutTuiState(
        query=query or spec.default_query,
        batch_label=spec.label,
        leads=leads,
    )


def _lead_from_row(index: int, row: dict[str, str], spec: DatasetSpec) -> Lead:
    name = _clean(row.get("name")) or f"Contact {index}"
    company = _clean(row.get("company")) or name
    title = _clean(row.get("title")) or "-"
    location = _clean(row.get("location")) or "California, United States"
    industry = _clean(row.get("industry")) or "unclassified"
    email = _clean(row.get("email")) or "-"
    linkedin = _normalize_linkedin(_clean(row.get("linkedin")))
    website = _infer_website(email)
    city, state = _parse_location(location)
    confidence = _contact_confidence(email=email, linkedin=linkedin)

    return Lead(
        id=f"{spec.slug}-{index}",
        company=company,
        city=city,
        state=state,
        category=industry,
        summary=_summary_for(title=title, company=company, industry=industry, email=email),
        website=website,
        source=spec.source,
        owner_profile=OwnerProfile(
            name=name,
            role=title,
            linkedin=linkedin,
            confidence=confidence,
            source="LinkedIn",
        ),
        best_email=email,
        best_phone="-",
        contact_confidence=confidence,
    )


def _summary_for(*, title: str, company: str, industry: str, email: str) -> str:
    lead_in = f"{title} at {company}" if title != "-" else f"Contact at {company}"
    email_suffix = " Direct email available." if email != "-" else ""
    return f"{lead_in}. LinkedIn industry tagged as {industry}.{email_suffix}"


def _parse_location(raw: str) -> tuple[str, str]:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        return "-", "-"

    if len(parts) >= 3:
        return parts[0], _normalize_state(parts[1])

    if len(parts) == 2:
        first, second = parts
        if _normalize_state(first) == "CA" and second.lower() == "united states":
            return "Statewide", "CA"
        return first, _normalize_state(second)

    token = parts[0]
    if _normalize_state(token) == "CA":
        return "Statewide", "CA"
    return token, "-"


def _normalize_state(raw: str) -> str:
    lowered = raw.strip().lower()
    if lowered in {"california", "ca"}:
        return "CA"
    if len(raw.strip()) == 2:
        return raw.strip().upper()
    return raw.strip()


def _normalize_linkedin(raw: str) -> str:
    if not raw:
        return "-"
    value = raw.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://{value.lstrip('/')}"


def _contact_confidence(*, email: str, linkedin: str) -> str:
    if email != "-" and linkedin != "-":
        return "high"
    if email != "-" or linkedin != "-":
        return "medium"
    return "low"


def _clean(raw: str | None) -> str:
    if raw is None:
        return ""
    return raw.strip()


def _infer_website(email: str) -> str | None:
    if not email or email == "-" or "@" not in email:
        return None
    domain = email.split("@", 1)[1].strip().lower()
    if not domain or domain in {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "icloud.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
    }:
        return None
    return f"https://{domain}"
