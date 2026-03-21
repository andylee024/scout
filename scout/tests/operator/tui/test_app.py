import asyncio

from scout.operator.tui.app import ScoutResearchApp
from scout.operator.tui.dataset_loader import load_dataset_state
from scout.operator.tui.mock_data import build_mock_state
from scout.operator.tui.models import Mode


def test_app_flow_enters_lead_adds_note_and_exports() -> None:
    async def scenario() -> None:
        app = ScoutResearchApp(build_mock_state("fire protection businesses in california"))
        async with app.run_test() as pilot:
            app.action_open_lead()
            await pilot.pause()
            app.action_add_note()
            lead_composer = app.query_one("#composer")
            lead_composer.value = "High-confidence owner and email."
            await lead_composer.action_submit()
            await pilot.pause()
            app.action_dump_leads()
            await pilot.pause()
            assert app.state.mode == Mode.LEAD
            assert app.state.current_lead() is not None
            assert app.state.current_lead().note == "High-confidence owner and email."
            assert app.state.current_lead().status == "exported"
            assert app.state.last_export_path is not None

    asyncio.run(scenario())


def test_lead_workspace_shows_note_and_contact_context() -> None:
    state = build_mock_state("fire protection businesses in california")
    state.set_selected_index(2)
    state.open_lead()

    app = ScoutResearchApp(state)
    stream = app._lead_stream_text().plain

    assert "SCORES" in stream
    assert "ENRICHMENT" in stream
    assert "SIGNALS" in stream
    assert "NOTE" in stream
    assert "NOTES" in stream
    assert "space keep" in stream
    assert "n add-note" in stream


def test_list_row_renders_scores_and_enrichment_strip() -> None:
    state = load_dataset_state("fire-protection-ca-owner-contacts")

    app = ScoutResearchApp(state)
    row = app._render_lead_row(state.current_rows()[0])

    assert row[0].plain.strip().isdigit()
    assert row[4].plain
    assert "/" in row[7].plain


def test_lead_mode_hides_detail_pane() -> None:
    async def scenario() -> None:
        app = ScoutResearchApp(build_mock_state("fire protection businesses in california"))
        async with app.run_test() as pilot:
            app.action_open_lead()
            await pilot.pause()
            assert app.state.mode == Mode.LEAD
            assert app.query_one("#detail-pane").display is False

    asyncio.run(scenario())


def test_overview_mode_renders_dataset_aggregates() -> None:
    state = load_dataset_state("fire-protection-ca-owner-contacts")
    state.set_mode(Mode.OVERVIEW)

    app = ScoutResearchApp(state)
    overview = app._overview_text().plain

    assert "CONTACT COVERAGE" in overview
    assert "TOP CITIES" in overview
    assert "TITLE MIX" in overview
    assert "COMPANY CLUSTERS" in overview


def test_detail_pane_shows_qualification_scorecard() -> None:
    state = load_dataset_state("fire-protection-ca-owner-contacts")

    app = ScoutResearchApp(state)
    detail = app._detail_text().plain

    assert "SCORES" in detail
    assert "WHY THIS MAKES THE CUT" in detail
    assert "ENRICHMENT" in detail
    assert "FIT" in detail
    assert "BIZ" in detail
    assert "EXIT" in detail
    assert "RCH" in detail
