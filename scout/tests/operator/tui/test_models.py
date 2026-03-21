from pathlib import Path

from scout.operator.tui.dataset_loader import load_dataset_state
from scout.operator.tui.mock_data import build_mock_state
from scout.operator.tui.models import Mode


def test_build_mock_state_has_expected_capabilities() -> None:
    state = build_mock_state("fire protection businesses in california")

    assert len(state.leads) >= 10
    assert state.mode == Mode.LEADS
    assert state.batch_label == "Fire Protection | California"
    assert state.leads[0].owner_profile.source == "Clodo"
    assert state.leads[0].owner_profile.age_band != "-"


def test_owner_filters_surface_retirement_candidates() -> None:
    state = build_mock_state("fire protection businesses in california")
    state.set_filter("retire:high age:65+ has:owner")

    rows = list(state.filtered_leads())

    assert rows
    assert all(row.owner_profile.retirement_signal == "high" for row in rows)
    assert all(row.owner_profile.age_band == "65+" for row in rows)


def test_open_lead_and_add_note_updates_state() -> None:
    state = build_mock_state("fire protection businesses in california")
    state.set_selected_index(1)

    message = state.open_lead()

    assert "Opened" in message
    assert state.mode == Mode.LEAD
    lead = state.current_lead()
    assert lead is not None

    reply = state.submit_prompt("Owner looks worth partner follow-up.")

    assert "Added note" in reply
    assert lead.note == "Owner looks worth partner follow-up."
    assert lead.notes[0].body == "Owner looks worth partner follow-up."


def test_toggle_keep_and_cycle_status() -> None:
    state = build_mock_state("fire protection businesses in california")
    state.set_selected_index(1)

    message = state.toggle_keep()
    lead = state.current_lead()

    assert "keep" in message
    assert lead is not None
    assert lead.status == "keep"

    message = state.cycle_status()

    assert "pass" in message
    assert lead.status == "pass"


def test_export_leads_writes_csv(tmp_path: Path) -> None:
    state = build_mock_state("fire protection businesses in california")

    path = Path(state.export_leads(tmp_path))

    assert path.exists()
    assert state.exported_count == len(state.leads)
    text = path.read_text(encoding="utf-8")
    assert (
        "company,city,state,status,owner,owner_role,age_band,retire,email,phone,website,linkedin,rating,reviews,note,exported_at"
        in text
    )


def test_packaged_dataset_loads_contact_directory() -> None:
    state = load_dataset_state("fire-protection-ca-owner-contacts")

    assert len(state.leads) >= 90
    assert state.batch_label == "CA Fire Protection Owner Contacts"
    assert state.leads[0].company == "Faith Fire Protection"
    assert state.leads[0].owner_profile.name == "Mark Cfei"
    assert state.leads[0].owner_profile.linkedin.startswith("https://linkedin.com/")
    assert state.email_count(state.leads) > 0
    assert state.unique_company_count(state.leads) < len(state.leads)
    assert state.leads[1].website == "https://wcfireprotection.com"


def test_score_filters_surface_high_fit_outreach_candidates() -> None:
    state = load_dataset_state("fire-protection-ca-owner-contacts")
    state.set_filter("fit>=70 exit>=55 has:email")

    rows = list(state.filtered_leads())

    assert rows
    assert all(state.lead_scorecard(row).fit >= 70 for row in rows)
    assert all(state.lead_scorecard(row).exit >= 55 for row in rows)
    assert all(row.has_email for row in rows)
