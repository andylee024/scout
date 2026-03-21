"""State model for the stripped-down Scout lead viewer."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import re
from typing import Iterable


class Mode(str, Enum):
    """Top-level terminal modes."""

    LEADS = "leads"
    OVERVIEW = "overview"
    LEAD = "lead"


@dataclass(frozen=True)
class OwnerProfile:
    """Owner-level enrichment preview attached to a lead."""

    name: str = "-"
    role: str = "-"
    age_band: str = "-"
    retirement_signal: str = "unknown"
    years_at_company: str = "-"
    linkedin: str = "-"
    confidence: str = "low"
    source: str = "Clodo"


@dataclass(frozen=True)
class LeadNote:
    """Operator note attached to a lead."""

    body: str
    created_at: str = "now"


@dataclass
class Lead:
    """One lead row rendered in the viewer."""

    id: str
    company: str
    city: str
    state: str
    category: str = ""
    summary: str = ""
    website: str | None = None
    phone: str | None = None
    rating: float | None = None
    reviews: int | None = None
    source: str = "agent_import"
    owner_profile: OwnerProfile = field(default_factory=OwnerProfile)
    best_email: str = "-"
    best_phone: str = "-"
    contact_confidence: str = "low"
    status: str = "new"
    note: str = ""
    notes: list[LeadNote] = field(default_factory=list)
    exported_at: str | None = None

    @property
    def has_website(self) -> bool:
        return bool(self.website)

    @property
    def has_phone(self) -> bool:
        return bool(self.phone)

    @property
    def has_owner(self) -> bool:
        return self.owner_profile.name != "-"

    @property
    def has_email(self) -> bool:
        return self.best_email != "-"

    @property
    def note_count(self) -> int:
        return len(self.notes)


@dataclass(frozen=True)
class LeadScorecard:
    """Decision-oriented scorecard for one lead."""

    fit: int
    business: int
    exit: int
    reach: int


@dataclass(frozen=True)
class EnrichmentFlag:
    """One compact enrichment indicator."""

    code: str
    label: str
    present: bool

    @property
    def token(self) -> str:
        return self.code if self.present else "."


@dataclass
class ScoutTuiState:
    """Mutable state backing the minimal lead-review TUI."""

    query: str
    batch_label: str
    leads: list[Lead]
    mode: Mode = Mode.LEADS
    filter_text: str = ""
    selected_rows: dict[Mode, int] = field(default_factory=dict)
    focused_lead_id: str | None = None
    last_export_path: str | None = None

    def __post_init__(self) -> None:
        for mode in Mode:
            self.selected_rows.setdefault(mode, 0)

    @property
    def keep_count(self) -> int:
        return sum(1 for lead in self.leads if lead.status == "keep")

    @property
    def pass_count(self) -> int:
        return sum(1 for lead in self.leads if lead.status == "pass")

    @property
    def exported_count(self) -> int:
        return sum(1 for lead in self.leads if lead.status == "exported")

    @property
    def retire_high_count(self) -> int:
        return sum(1 for lead in self.leads if lead.owner_profile.retirement_signal == "high")

    @property
    def ready_count(self) -> int:
        return sum(1 for lead in self.leads if lead.has_owner and lead.has_email)

    def filtered_count(self) -> int:
        return len(list(self.filtered_leads()))

    def set_mode(self, mode: Mode) -> None:
        self.mode = mode
        self._clamp_selection(mode)

    def set_filter(self, raw: str) -> None:
        self.filter_text = raw.strip()
        self._clamp_selection(Mode.LEADS)

    def set_selected_index(self, index: int) -> None:
        self.selected_rows[self.mode] = max(0, index)
        self._clamp_selection(self.mode)

    def move_selection(self, delta: int) -> None:
        rows = self.current_rows()
        if not rows:
            self.selected_rows[self.mode] = 0
            return
        current = self.selected_rows[self.mode]
        self.selected_rows[self.mode] = max(0, min(len(rows) - 1, current + delta))

    def summary_line(self) -> str:
        return (
            f"Scout | {self.batch_label} | {len(self.leads)} leads | "
            f"{self.unique_company_count()} companies | {self.keep_count} keep | "
            f"{self.ready_count} ready | {self.exported_count} exported"
        )

    def mode_tabs(self) -> str:
        labels = {Mode.LEADS: "1 Leads", Mode.OVERVIEW: "2 Overview"}
        rendered: list[str] = []
        for mode in (Mode.LEADS, Mode.OVERVIEW):
            label = labels[mode]
            rendered.append(f"[{label}]" if mode == self.mode else label)
        if self.mode == Mode.LEAD:
            rendered.append("[Lead]")
        return "   ".join(rendered)

    def detail_title(self) -> str:
        if self.mode == Mode.LEAD:
            return "NOTES"
        return "QUALIFY"

    def composer_placeholder(self) -> str:
        if self.mode == Mode.LEAD:
            return "Add note or rationale for this lead"
        return ""

    def current_rows(self) -> list[Lead]:
        if self.mode == Mode.LEADS:
            return sorted(self.filtered_leads(), key=self._lead_sort_key)
        return []

    def current_lead(self) -> Lead | None:
        if self.mode == Mode.LEAD and self.focused_lead_id:
            return self.lead_by_id(self.focused_lead_id)
        rows = self._rows_for(Mode.LEADS)
        if not rows:
            return None
        return rows[self.selected_rows[Mode.LEADS]]

    def lead_by_id(self, lead_id: str) -> Lead | None:
        return next((lead for lead in self.leads if lead.id == lead_id), None)

    def submit_prompt(self, raw: str) -> str:
        lead = self.current_lead()
        if lead is None:
            return "No lead selected"
        if self.mode != Mode.LEAD:
            return "Notes only work in Lead view"
        note = raw.strip()
        if not note:
            return "Note is empty"
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        lead.notes.insert(0, LeadNote(body=note, created_at=created_at))
        lead.note = note
        return f"Added note for {lead.company}"

    def open_lead(self) -> str:
        lead = self.current_lead()
        if lead is None:
            return "No lead selected"
        self.focused_lead_id = lead.id
        self.mode = Mode.LEAD
        return f"Opened {lead.company}"

    def close_lead(self) -> str:
        self.mode = Mode.LEADS
        return "Back to leads"

    def toggle_keep(self) -> str:
        lead = self.current_lead()
        if lead is None:
            return "No lead selected"
        lead.status = "new" if lead.status == "keep" else "keep"
        return f"{lead.company}: {lead.status}"

    def cycle_status(self) -> str:
        lead = self.current_lead()
        if lead is None:
            return "No lead selected"
        order = ["new", "keep", "pass", "exported"]
        current = lead.status if lead.status in order else "new"
        lead.status = order[(order.index(current) + 1) % len(order)]
        if lead.status == "exported":
            lead.exported_at = datetime.utcnow().strftime("%Y-%m-%d")
        return f"{lead.company}: {lead.status}"

    def export_leads(self, root: Path) -> str:
        leads = list(self.filtered_leads())
        exported_on = datetime.utcnow().strftime("%Y-%m-%d")
        for lead in leads:
            self._mark_exported(lead, exported_on=exported_on)
        rows = [self._lead_export_row(lead) for lead in leads]
        export_dir = root / "outputs" / "tui"
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        path = export_dir / f"leads-{timestamp}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=_export_fieldnames())
            writer.writeheader()
            writer.writerows(rows)
        self.last_export_path = str(path)
        return str(path)

    def export_current_lead(self, root: Path) -> str:
        lead = self.current_lead()
        if lead is None:
            return self.export_leads(root)
        exported_on = datetime.utcnow().strftime("%Y-%m-%d")
        self._mark_exported(lead, exported_on=exported_on)
        export_dir = root / "outputs" / "tui"
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        path = export_dir / f"lead-{lead.id}-{timestamp}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=_export_fieldnames())
            writer.writeheader()
            writer.writerow(self._lead_export_row(lead))
        self.last_export_path = str(path)
        return str(path)

    def _lead_export_row(self, lead: Lead) -> dict[str, str | int | float | None]:
        return {
            "company": lead.company,
            "city": lead.city,
            "state": lead.state,
            "status": lead.status,
            "owner": lead.owner_profile.name,
            "owner_role": lead.owner_profile.role,
            "age_band": lead.owner_profile.age_band,
            "retire": lead.owner_profile.retirement_signal,
            "email": lead.best_email,
            "phone": lead.best_phone or lead.phone or "-",
            "website": lead.website or "-",
            "linkedin": lead.owner_profile.linkedin,
            "rating": lead.rating,
            "reviews": lead.reviews,
            "note": lead.note,
            "exported_at": lead.exported_at or "-",
        }

    def filtered_leads(self) -> Iterable[Lead]:
        return [lead for lead in self.leads if self._lead_matches(lead)]

    def table_columns(self) -> tuple[str, ...]:
        return ("FIT", "BIZ", "EXIT", "RCH", "ENR", "Company", "City", "Owner / Title")

    def visible_leads(self) -> list[Lead]:
        return list(self.filtered_leads())

    def unique_company_count(self, leads: Iterable[Lead] | None = None) -> int:
        rows = self._coerce_leads(leads)
        return len({lead.company for lead in rows if lead.company})

    def email_count(self, leads: Iterable[Lead] | None = None) -> int:
        return sum(1 for lead in self._coerce_leads(leads) if lead.has_email)

    def linkedin_count(self, leads: Iterable[Lead] | None = None) -> int:
        return sum(1 for lead in self._coerce_leads(leads) if lead.owner_profile.linkedin != "-")

    def company_counts(self, leads: Iterable[Lead] | None = None) -> list[tuple[str, int]]:
        rows = self._coerce_leads(leads)
        return Counter(lead.company for lead in rows if lead.company).most_common()

    def city_counts(self, leads: Iterable[Lead] | None = None) -> list[tuple[str, int]]:
        rows = self._coerce_leads(leads)
        return Counter(lead.city for lead in rows if lead.city and lead.city != "-").most_common()

    def title_counts(self, leads: Iterable[Lead] | None = None) -> list[tuple[str, int]]:
        rows = self._coerce_leads(leads)
        return Counter(
            lead.owner_profile.role
            for lead in rows
            if lead.owner_profile.role and lead.owner_profile.role != "-"
        ).most_common()

    def industry_counts(self, leads: Iterable[Lead] | None = None) -> list[tuple[str, int]]:
        rows = self._coerce_leads(leads)
        return Counter(lead.category for lead in rows if lead.category).most_common()

    def high_fit_count(self, threshold: int = 75, leads: Iterable[Lead] | None = None) -> int:
        return sum(
            1 for lead in self._coerce_leads(leads) if self.lead_scorecard(lead).fit >= threshold
        )

    def company_contact_count(self, company: str) -> int:
        return sum(1 for lead in self.leads if lead.company == company)

    def lead_scorecard(self, lead: Lead) -> LeadScorecard:
        owner = lead.owner_profile
        duplicate_company_hits = self.company_contact_count(lead.company)

        business = 35
        if lead.reviews is not None:
            business += min(26, round(min(1.0, lead.reviews / 250) * 26))
        if lead.rating is not None:
            business += max(0, min(12, round((lead.rating - 4.0) * 12)))
        if lead.has_website:
            business += 8
        if duplicate_company_hits > 1:
            business += 10
        if _is_owner_operator(owner.role):
            business += 8
        business += _industry_quality_bonus(lead.category)
        if lead.has_phone or (lead.best_phone not in {"", "-"}):
            business += 4
        business = _clamp_score(business)

        if owner.retirement_signal != "unknown":
            exit = {"high": 82, "medium": 68, "low": 44}.get(owner.retirement_signal, 36)
            exit += min(10, max(0, (_owner_age_floor(owner.age_band) - 45) // 5 * 2))
            exit += min(10, (_years_floor(owner.years_at_company) // 5) * 2)
        else:
            exit = 28
            if lead.has_owner:
                exit += 14
            exit += _owner_exit_bonus(owner.role)
            if duplicate_company_hits > 1:
                exit += 6
            if lead.has_website:
                exit += 4
        exit = _clamp_score(exit)

        reach = 18
        if lead.has_email:
            reach += 34
        if lead.has_phone or (lead.best_phone not in {"", "-"}):
            reach += 14
        if lead.has_website:
            reach += 12
        if owner.linkedin != "-":
            reach += 14
        if lead.has_owner:
            reach += 8
        reach += {"high": 10, "medium": 5, "low": 0}.get(lead.contact_confidence, 0)
        reach = _clamp_score(reach)

        fit = round((business * 0.42) + (exit * 0.33) + (reach * 0.25))
        if duplicate_company_hits > 1:
            fit += 4
        if not lead.has_email and owner.linkedin == "-":
            fit -= 10
        fit = _clamp_score(fit)

        return LeadScorecard(fit=fit, business=business, exit=exit, reach=reach)

    def lead_enrichment_flags(self, lead: Lead) -> tuple[EnrichmentFlag, ...]:
        return (
            EnrichmentFlag(code="W", label="website", present=lead.has_website),
            EnrichmentFlag(code="O", label="owner", present=lead.has_owner),
            EnrichmentFlag(
                code="C",
                label="contact",
                present=lead.has_email or lead.has_phone or (lead.best_phone not in {"", "-"}),
            ),
            EnrichmentFlag(code="L", label="linkedin", present=lead.owner_profile.linkedin != "-"),
            EnrichmentFlag(code="R", label="reviews", present=lead.reviews is not None),
        )

    def lead_enrichment_strip(self, lead: Lead) -> str:
        return "".join(flag.token for flag in self.lead_enrichment_flags(lead))

    def lead_missing_enrichments(self, lead: Lead) -> list[str]:
        missing = [flag.label for flag in self.lead_enrichment_flags(lead) if not flag.present]
        owner = lead.owner_profile
        if owner.years_at_company == "-" and owner.retirement_signal == "unknown":
            missing.append("tenure")
        return missing

    def lead_reasons(self, lead: Lead) -> list[str]:
        reasons: list[str] = []
        owner = lead.owner_profile
        duplicate_company_hits = self.company_contact_count(lead.company)
        if lead.reviews is not None and lead.reviews >= 100:
            reasons.append("strong review density")
        elif lead.reviews is None:
            reasons.append("reviews still missing")
        if duplicate_company_hits > 1:
            reasons.append("multi-contact company hit")
        if owner.retirement_signal in {"high", "medium"}:
            reasons.append("clear exit signal")
        elif _is_owner_operator(owner.role):
            reasons.append("owner-led operator")
        if lead.has_email:
            reasons.append("direct email available")
        elif owner.linkedin != "-":
            reasons.append("linkedin outreach path")
        if lead.has_website:
            reasons.append("website present")
        return reasons[:3]

    def _lead_matches(self, lead: Lead) -> bool:
        owner = lead.owner_profile
        scorecard = self.lead_scorecard(lead)
        checks = {
            "has:web": lead.has_website,
            "has:website": lead.has_website,
            "has:phone": lead.has_phone,
            "has:owner": lead.has_owner,
            "has:email": lead.has_email,
            "has:contact": lead.has_email or lead.has_phone or (lead.best_phone not in {"", "-"}),
            "has:linkedin": owner.linkedin != "-",
            "has:reviews": lead.reviews is not None,
            f"status:{lead.status}": True,
            f"retire:{owner.retirement_signal.lower()}": owner.retirement_signal != "unknown",
            f"age:{owner.age_band.lower()}": owner.age_band != "-",
            f"state:{lead.state.lower()}": True,
            f"city:{lead.city.lower()}": True,
        }
        return _matches_tokens(
            self.filter_text,
            searchable=[
                lead.company,
                lead.city,
                lead.state,
                lead.category,
                lead.summary,
                lead.note,
                lead.best_email,
                owner.linkedin,
                owner.name,
                owner.role,
                owner.age_band,
                owner.retirement_signal,
                lead.website or "",
            ],
            checks=checks,
            numeric={
                "reviews": lead.reviews or 0,
                "owner_age": _owner_age_floor(owner.age_band),
                "fit": scorecard.fit,
                "biz": scorecard.business,
                "business": scorecard.business,
                "exit": scorecard.exit,
                "reach": scorecard.reach,
                "rch": scorecard.reach,
            },
        )

    def _clamp_selection(self, mode: Mode) -> None:
        rows = self.current_rows() if mode == self.mode else self._rows_for(mode)
        if not rows:
            self.selected_rows[mode] = 0
            return
        self.selected_rows[mode] = max(0, min(len(rows) - 1, self.selected_rows[mode]))

    def _rows_for(self, mode: Mode) -> list[Lead]:
        current_mode = self.mode
        self.mode = mode
        rows = self.current_rows()
        self.mode = current_mode
        return rows

    def _mark_exported(self, lead: Lead, exported_on: str) -> None:
        lead.status = "exported"
        lead.exported_at = exported_on

    def _coerce_leads(self, leads: Iterable[Lead] | None) -> list[Lead]:
        if leads is None:
            return list(self.leads)
        return list(leads)

    def _lead_sort_key(self, lead: Lead) -> tuple[int, int, int, int, str, str]:
        scorecard = self.lead_scorecard(lead)
        return (
            -scorecard.fit,
            -scorecard.business,
            -scorecard.exit,
            -scorecard.reach,
            lead.company.lower(),
            lead.owner_profile.name.lower(),
        )


def _export_fieldnames() -> list[str]:
    return [
        "company",
        "city",
        "state",
        "status",
        "owner",
        "owner_role",
        "age_band",
        "retire",
        "email",
        "phone",
        "website",
        "linkedin",
        "rating",
        "reviews",
        "note",
        "exported_at",
    ]


def _matches_tokens(
    filter_text: str,
    searchable: list[str],
    checks: dict[str, bool],
    numeric: dict[str, int],
) -> bool:
    tokens = [token for token in filter_text.lower().split() if token]
    haystack = " ".join(searchable).lower()
    for token in tokens:
        if token in checks:
            if not checks[token]:
                return False
            continue
        match = re.match(r"([a-z_]+)([><]=?)(\d+(?:k|m)?)", token)
        if match:
            field, operator, raw_value = match.groups()
            if field not in numeric:
                return False
            value = _parse_compact_number(raw_value)
            current = numeric[field]
            if operator == ">" and not current > value:
                return False
            if operator == ">=" and not current >= value:
                return False
            if operator == "<" and not current < value:
                return False
            if operator == "<=" and not current <= value:
                return False
            continue
        if token.startswith("status:"):
            return False
        if token not in haystack:
            return False
    return True


def _parse_compact_number(raw: str) -> int:
    raw = raw.lower()
    if raw.endswith("m"):
        return int(float(raw[:-1]) * 1_000_000)
    if raw.endswith("k"):
        return int(float(raw[:-1]) * 1_000)
    return int(raw)


def _owner_age_floor(age_band: str) -> int:
    lowered = age_band.strip().lower()
    if not lowered or lowered == "-":
        return 0
    if lowered.endswith("+"):
        return int(lowered[:-1])
    match = re.match(r"(\d+)-(\d+)", lowered)
    if match:
        return int(match.group(1))
    return 0


def _years_floor(raw: str) -> int:
    match = re.search(r"(\d+)", raw or "")
    if not match:
        return 0
    return int(match.group(1))


def _clamp_score(value: int, *, floor: int = 0, ceiling: int = 95) -> int:
    return max(floor, min(ceiling, value))


def _owner_exit_bonus(title: str) -> int:
    lowered = title.lower()
    bonuses = {
        "owner": 20,
        "founder": 18,
        "company owner": 18,
        "business owner": 18,
        "managing partner": 16,
        "co-owner": 16,
        "ceo": 14,
        "chief executive officer": 14,
        "president": 12,
        "principal": 12,
        "chairman": 12,
        "vice president": 8,
    }
    return max((bonus for key, bonus in bonuses.items() if key in lowered), default=0)


def _is_owner_operator(title: str) -> bool:
    lowered = title.lower()
    return any(
        token in lowered
        for token in (
            "owner",
            "founder",
            "president",
            "ceo",
            "chief executive officer",
            "managing partner",
            "principal",
            "chairman",
        )
    )


def _industry_quality_bonus(category: str) -> int:
    lowered = category.strip().lower()
    if lowered in {
        "construction",
        "facilities services",
        "public safety",
        "security & investigations",
        "design",
    }:
        return 6
    if lowered in {"government administration", "wholesale", "telecommunications"}:
        return 3
    return 0
