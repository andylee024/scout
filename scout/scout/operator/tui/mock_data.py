"""Mock lead data for the stripped-down Scout viewer."""

from __future__ import annotations

from scout.operator.tui.models import Lead, LeadNote, OwnerProfile, ScoutTuiState
from scout.shared.query_parser import parse_query


def build_mock_state(query: str) -> ScoutTuiState:
    """Return deterministic lead rows for TUI experimentation."""

    try:
        industry, location = parse_query(query)
    except Exception:
        industry = query.strip() or "fire protection"
        location = "United States"

    leads = _build_leads(industry, location)
    leads[0].status = "keep"
    leads[0].note = "Strong owner-retirement signal and direct email."
    leads[0].notes = [
        LeadNote(body="Strong owner-retirement signal and direct email.", created_at="2026-03-17 09:10"),
        LeadNote(body="Commercial-heavy service mix. Good first batch candidate.", created_at="2026-03-16 17:42"),
    ]

    leads[2].status = "keep"
    leads[2].note = "Likely worth exporting for partner follow-up."
    leads[2].notes = [
        LeadNote(body="Likely worth exporting for partner follow-up.", created_at="2026-03-17 08:55")
    ]

    leads[3].status = "exported"
    leads[3].exported_at = "2026-03-17"
    leads[3].note = "Already handed off to partner sheet."
    leads[3].notes = [
        LeadNote(body="Already handed off to partner sheet.", created_at="2026-03-17 08:02")
    ]

    leads[4].status = "pass"
    leads[4].note = "Install-heavy and owner signal is weak."
    leads[4].notes = [
        LeadNote(body="Install-heavy and owner signal is weak.", created_at="2026-03-16 19:18")
    ]

    return ScoutTuiState(
        query=query,
        batch_label=f"{industry.title()} | {location.title()}",
        leads=leads,
    )


def _build_leads(industry: str, location: str) -> list[Lead]:
    state = _state_for(location)
    category = industry.title()
    if "fire" in industry.lower():
        names = [
            "CITY OF ANGELS FIRE PROTECTION",
            "Black Bird Fire Protection",
            "FireProTech",
            "Reliable Fire Protection",
            "Sure Fire Protection",
            "U.S. Fire Protection",
            "Fire Protection Group Inc.",
            "L A Fire Protection Inc",
            "Metro Fire Life Safety",
            "Guardian Fire & Safety",
            "Pacific Fire Systems",
            "Mission Fire Services",
            "Code Red Compliance",
            "Atlas Fire Prevention",
            "Sentinel Fire Inspection",
            "West Coast Fire Controls",
            "American Fire Watch",
            "Harbor Fire Defense",
        ]
        cities = [
            "Los Angeles",
            "Brea",
            "Glendale",
            "Los Angeles",
            "Pasadena",
            "Sun Valley",
            "Los Angeles",
            "Burbank",
            "Torrance",
            "Long Beach",
            "Irvine",
            "Santa Clarita",
            "Anaheim",
            "Riverside",
            "Ontario",
            "Santa Ana",
            "Hawthorne",
            "Gardena",
        ]
        summaries = [
            "Commercial fire inspections, alarm testing, and recurring compliance contracts.",
            "Mix of inspection, repair, and install work for industrial and multifamily accounts.",
            "Commercial inspections, monitoring coordination, and recurring alarm service routes.",
            "Recurring sprinkler service and annual testing for warehouse and retail customers.",
            "Install-heavy mix with some annual compliance work for local operators.",
            "Low-voltage fire alarm retrofits with light recurring service coverage.",
            "Commercial extinguisher inspections and route-based compliance work.",
            "Local inspection and sprinkler testing for owner-managed properties.",
            "Life-safety service and recurring maintenance for small commercial accounts.",
            "Commercial fire systems, inspections, and emergency repairs.",
            "Inspection-driven service mix with recurring municipal and school work.",
            "Recurring fire service contracts and field response across Santa Clarita.",
            "Code compliance visits and annual inspection work for local facilities.",
            "Fire prevention testing and route density across Inland Empire accounts.",
            "Inspection, tagging, and recurring compliance work for industrial customers.",
            "Service-driven fire controls maintenance with commercial accounts.",
            "Fire watch, inspections, and short-cycle commercial contracts.",
            "Recurring fire defense service with local warehouse coverage.",
        ]
    else:
        base = category.rstrip("s")
        names = [
            f"Summit {base}",
            f"Atlas {base} Group",
            f"Precision {base}",
            f"Reliable {base}",
            f"Metro {base} Services",
            f"Prime {base} Solutions",
            f"Local {base} Co.",
            f"West Coast {base}",
        ]
        cities = [location.title()] * len(names)
        summaries = [
            f"{name} appears active in {cities[index]} with a visible {category.lower()} footprint."
            for index, name in enumerate(names)
        ]

    leads: list[Lead] = []
    for index, name in enumerate(names, start=1):
        reviews = max(3, 420 - index * 18)
        has_website = index % 6 != 0
        has_phone = index % 7 != 0
        owner = _owner_profile_for(index=index, has_website=has_website)
        domain = name.lower().replace(" ", "").replace(".", "")
        email = f"{owner.name.split()[0].lower()}@{domain}.com" if owner.name != "-" and has_website else "-"
        phone = "(555) 010-0110" if has_phone else None
        leads.append(
            Lead(
                id=f"lead-{index}",
                company=name,
                city=cities[index - 1],
                state=state,
                category=category,
                summary=summaries[index - 1],
                website=f"https://{domain}.com" if has_website else None,
                phone=phone,
                rating=round(4.9 - (index * 0.03), 1),
                reviews=reviews,
                source="agent_import",
                owner_profile=owner,
                best_email=email,
                best_phone=phone or "-",
                contact_confidence=_contact_confidence_for(owner, email, phone),
            )
        )
    return leads


def _owner_profile_for(index: int, has_website: bool) -> OwnerProfile:
    first_names = [
        "Bill",
        "Maria",
        "David",
        "Carol",
        "Anthony",
        "Rita",
        "Frank",
        "Elena",
        "Scott",
        "Diane",
        "Victor",
        "Linda",
        "Mark",
        "Sandra",
        "Paul",
        "Nina",
        "George",
        "Tina",
    ]
    last_names = [
        "Mendez",
        "Soto",
        "Harper",
        "Lawson",
        "Khan",
        "Vega",
        "Parker",
        "Roman",
        "Fischer",
        "Lopez",
        "Mills",
        "Dominguez",
        "Nguyen",
        "Price",
        "Carson",
        "Gibbs",
        "Ortiz",
        "Briggs",
    ]
    age_bands = [
        "65+",
        "55-64",
        "65+",
        "55-64",
        "45-54",
        "65+",
        "55-64",
        "-",
        "45-54",
        "65+",
        "55-64",
        "45-54",
        "65+",
        "55-64",
        "45-54",
        "65+",
        "55-64",
        "45-54",
    ]
    age_band = age_bands[index - 1]
    if age_band == "-":
        return OwnerProfile()

    retirement_signal = {"65+": "high", "55-64": "medium", "45-54": "low"}[age_band]
    confidence = "high" if age_band in {"65+", "55-64"} else "medium"
    years_at_company = {"65+": "26y", "55-64": "18y", "45-54": "9y"}[age_band]
    linkedin = (
        f"linkedin.com/in/{first_names[index - 1].lower()}-{last_names[index - 1].lower()}"
        if has_website
        else "-"
    )
    role = "Founder / owner" if age_band in {"65+", "55-64"} else "President"
    return OwnerProfile(
        name=f"{first_names[index - 1]} {last_names[index - 1]}",
        role=role,
        age_band=age_band,
        retirement_signal=retirement_signal,
        years_at_company=years_at_company,
        linkedin=linkedin,
        confidence=confidence,
    )


def _contact_confidence_for(owner: OwnerProfile, email: str, phone: str | None) -> str:
    if owner.name != "-" and email != "-" and phone:
        return "high"
    if owner.name != "-" and (email != "-" or phone):
        return "medium"
    return "low"


def _state_for(location: str) -> str:
    lower = location.lower()
    if "california" in lower or "los angeles" in lower:
        return "CA"
    if "texas" in lower or "houston" in lower:
        return "TX"
    if "florida" in lower or "miami" in lower:
        return "FL"
    return "US"
