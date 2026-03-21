"""Scout lead-viewer terminal UI."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Input, Static

from scout.operator.tui.models import Lead, Mode, ScoutTuiState

MUTED = "#8b949e"
PRIMARY = "#79c0ff"
SUCCESS = "#7ee787"
WARN = "#e3b341"
ACCENT = "#ffa657"
DANGER = "#ff7b72"
TEXT = "#d7dadc"
DIM = "#30363d"
SURFACE = "#11161c"
BG = "#0d1117"


class ScoutResearchApp(App[None]):
    """Dense, keyboard-first terminal UI for lead review."""

    CSS = f"""
    Screen {{
        background: {BG};
        color: {TEXT};
    }}

    #summary {{
        background: {SURFACE};
        padding: 0 1;
        height: 1;
    }}

    #filter {{
        margin: 0;
        border: none;
        background: {BG};
        color: {TEXT};
        padding: 0 1;
        height: 3;
    }}

    #tabs {{
        background: {SURFACE};
        padding: 0 1;
        height: 1;
    }}

    #body {{
        height: 1fr;
    }}

    #left-pane {{
        width: 58%;
        border-right: solid {DIM};
    }}

    #detail-pane {{
        width: 42%;
    }}

    #stream {{
        padding: 1;
        height: 1fr;
        background: {BG};
    }}

    DataTable {{
        background: {BG};
        color: {TEXT};
        border: none;
        padding: 0;
        height: 1fr;
    }}

    DataTable > .datatable--header {{
        background: {SURFACE};
        color: {MUTED};
        text-style: bold;
    }}

    DataTable > .datatable--cursor {{
        background: #17202b;
        color: #f3f4f5;
        text-style: bold;
    }}

    #detail-title {{
        height: 1;
        color: {MUTED};
        background: {SURFACE};
        padding: 0 1;
    }}

    #detail {{
        padding: 1;
        height: 1fr;
        background: {BG};
    }}

    #composer {{
        margin: 0;
        border: tall {DIM};
        background: #0a0d10;
        color: {TEXT};
        padding: 0 1;
        height: 3;
    }}

    #queue {{
        background: {SURFACE};
        padding: 0 1;
        height: 1;
    }}
    """

    BINDINGS = [
        Binding("1", "mode_leads", "Leads", show=True, priority=True),
        Binding("2", "mode_overview", "Overview", show=True, priority=True),
        Binding("enter", "open_lead", "Open", show=True),
        Binding("escape", "back", "Back", show=True, priority=True),
        Binding("b", "back", "Back", show=False, priority=True),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("space", "toggle_keep", "Keep", show=True),
        Binding("s", "cycle_status", "Status", show=True),
        Binding("n", "add_note", "Note", show=True),
        Binding("d", "dump_leads", "Dump", show=True),
        Binding("/", "focus_filter", "Filter", show=True),
    ]

    def __init__(self, state: ScoutTuiState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        yield Static(id="summary")
        yield Input(
            self.state.filter_text,
            placeholder="/ fuzzy filter: fit>=75 exit>=60 has:email owner los angeles",
            id="filter",
        )
        yield Static(id="tabs")
        with Horizontal(id="body"):
            with Vertical(id="left-pane"):
                yield Static(id="stream")
                yield DataTable(id="table")
            with Vertical(id="detail-pane"):
                yield Static(id="detail-title")
                yield Static(id="detail")
        yield Input("", placeholder=self.state.composer_placeholder(), id="composer")
        yield Static(id="queue")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = False
        self._refresh_view(reset_columns=True)
        self._focus_primary_widget()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filter":
            self.state.set_filter(event.value)
            self._refresh_view(reset_columns=True)
            self.set_focus(None)
            return
        if event.input.id == "composer":
            message = self.state.submit_prompt(event.value)
            event.input.value = ""
            self._refresh_view(reset_columns=False)
            self.set_focus(None)
            self._notify(message)

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        if self.state.mode != Mode.LEADS:
            return
        self.state.set_selected_index(event.coordinate.row)
        self._update_detail()

    def action_mode_leads(self) -> None:
        self._set_mode(Mode.LEADS)

    def action_mode_overview(self) -> None:
        self._set_mode(Mode.OVERVIEW)

    def action_open_lead(self) -> None:
        if self.state.mode == Mode.LEADS:
            self._notify(self.state.open_lead())
            self._refresh_view(reset_columns=False)
            self._focus_primary_widget()

    def action_back(self) -> None:
        if self.state.mode == Mode.LEAD:
            self._notify(self.state.close_lead())
            self._refresh_view(reset_columns=True)
            self._focus_primary_widget()
            return
        if self.state.mode == Mode.OVERVIEW:
            self._set_mode(Mode.LEADS)

    def action_cursor_down(self) -> None:
        if self.state.mode != Mode.LEADS:
            return
        self.state.move_selection(1)
        self._sync_cursor()

    def action_cursor_up(self) -> None:
        if self.state.mode != Mode.LEADS:
            return
        self.state.move_selection(-1)
        self._sync_cursor()

    def action_toggle_keep(self) -> None:
        if self.state.mode not in {Mode.LEADS, Mode.LEAD}:
            return
        self._notify(self.state.toggle_keep())
        self._refresh_view(reset_columns=False)

    def action_cycle_status(self) -> None:
        if self.state.mode not in {Mode.LEADS, Mode.LEAD}:
            return
        self._notify(self.state.cycle_status())
        self._refresh_view(reset_columns=False)

    def action_add_note(self) -> None:
        self.action_focus_composer()

    def action_dump_leads(self) -> None:
        if self.state.mode == Mode.LEAD:
            path = self.state.export_current_lead(Path.cwd())
        else:
            path = self.state.export_leads(Path.cwd())
        self._notify(f"Dumped leads to {path}")
        self._refresh_view(reset_columns=False)

    def action_focus_filter(self) -> None:
        if self.state.mode in {Mode.LEADS, Mode.OVERVIEW}:
            self.query_one("#filter", Input).focus()

    def action_focus_composer(self) -> None:
        if self.state.mode == Mode.LEAD:
            self.query_one("#composer", Input).focus()

    def _set_mode(self, mode: Mode) -> None:
        self.state.set_mode(mode)
        self._refresh_view(reset_columns=True)
        self._focus_primary_widget()

    def _focus_primary_widget(self) -> None:
        self.set_focus(None)

    def _refresh_view(self, reset_columns: bool) -> None:
        list_mode = self.state.mode == Mode.LEADS
        overview_mode = self.state.mode == Mode.OVERVIEW
        lead_mode = self.state.mode == Mode.LEAD
        browse_mode = self.state.mode in {Mode.LEADS, Mode.OVERVIEW}
        self.query_one("#summary", Static).update(self._summary_text())
        self.query_one("#tabs", Static).update(self._tabs_text())
        self.query_one("#detail-title", Static).update(self._section_title_text())
        self._apply_mode_layout(mode=self.state.mode)
        self.query_one("#filter", Input).display = browse_mode
        self.query_one(DataTable).display = list_mode
        self.query_one("#stream", Static).display = lead_mode or overview_mode
        self.query_one("#composer", Input).display = lead_mode
        self.query_one("#composer", Input).placeholder = self.state.composer_placeholder()
        self.query_one("#detail-pane", Vertical).display = list_mode
        self.query_one("#detail-title", Static).display = list_mode
        self.query_one("#queue", Static).update(self._queue_text())
        if list_mode:
            self._populate_table(reset_columns=reset_columns)
        elif overview_mode:
            self.query_one("#stream", Static).update(self._overview_text())
            self.query_one(DataTable).clear(columns=True)
        else:
            self.query_one("#stream", Static).update(self._lead_stream_text())
            self.query_one(DataTable).clear(columns=True)
        self._update_detail()

    def _apply_mode_layout(self, mode: Mode) -> None:
        left = self.query_one("#left-pane", Vertical)
        stream = self.query_one("#stream", Static)
        if mode in {Mode.LEAD, Mode.OVERVIEW}:
            left.styles.width = "100%"
            stream.styles.padding = (0, 1)
            return
        left.styles.width = "58%"
        stream.styles.padding = 1

    def _populate_table(self, reset_columns: bool) -> None:
        table = self.query_one(DataTable)
        if reset_columns:
            table.clear(columns=True)
            for column in self.state.table_columns():
                table.add_column(column)
        else:
            table.clear()
        for row in self._render_rows():
            table.add_row(*row)
        self._sync_cursor()

    def _render_rows(self) -> list[tuple[Text, ...]]:
        return [self._render_lead_row(lead) for lead in self.state.current_rows()]

    def _sync_cursor(self) -> None:
        if self.state.mode != Mode.LEADS:
            return
        table = self.query_one(DataTable)
        rows = self._render_rows()
        if not rows:
            self.state.set_selected_index(0)
            self._update_detail()
            return
        row = min(self.state.selected_rows[Mode.LEADS], len(rows) - 1)
        table.move_cursor(row=row, column=0, animate=False)
        self.state.set_selected_index(row)
        self._update_detail()

    def _update_detail(self) -> None:
        self.query_one("#detail", Static).update(self._detail_text())

    def _summary_text(self) -> Text:
        text = Text()
        text.append("Scout", style=f"bold {TEXT}")
        text.append(" | ", style=MUTED)
        text.append(self.state.batch_label, style=f"bold {PRIMARY}")
        text.append(" | ", style=MUTED)
        text.append(f"{len(self.state.leads)} leads", style=f"bold {TEXT}")
        text.append(" | ", style=MUTED)
        text.append(f"{self.state.unique_company_count()} companies", style=f"bold {PRIMARY}")
        text.append(" | ", style=MUTED)
        text.append(f"{self.state.high_fit_count()} fit>=75", style=f"bold {SUCCESS}")
        text.append(" | ", style=MUTED)
        text.append(f"{self.state.email_count()} direct email", style=f"bold {PRIMARY}")
        text.append(" | ", style=MUTED)
        text.append(f"{self.state.exported_count} exported", style=f"bold {WARN}")
        if self.state.mode == Mode.LEAD and (lead := self.state.current_lead()) is not None:
            text.append(" | ", style=MUTED)
            text.append(lead.company, style=f"bold {PRIMARY}")
        return text

    def _tabs_text(self) -> Text:
        text = Text()
        for index, label in enumerate(self.state.mode_tabs().split("   ")):
            if index:
                text.append("   ", style=MUTED)
            if label.startswith("["):
                text.append(label, style=f"bold {PRIMARY}")
            else:
                text.append(label, style=MUTED)
        return text

    def _section_title_text(self) -> Text:
        return Text(self.state.detail_title(), style=f"bold {MUTED}")

    def _queue_text(self) -> Text:
        text = Text()
        text.append("view", style=f"bold {MUTED}")
        text.append(": ", style=MUTED)
        text.append(str(self.state.filtered_count()), style=f"bold {TEXT}")
        text.append("/", style=MUTED)
        text.append(str(len(self.state.leads)), style=f"bold {TEXT}")
        text.append(" visible", style=MUTED)
        text.append(" | ", style=MUTED)
        text.append("filter ", style=MUTED)
        text.append(
            self.state.filter_text or "-", style=PRIMARY if self.state.filter_text else MUTED
        )
        if self.state.mode == Mode.LEADS:
            text.append(" | ", style=MUTED)
            text.append("hint ", style=MUTED)
            text.append("fit>=75 exit>=60 has:email has:reviews", style=PRIMARY)
        if self.state.last_export_path:
            text.append(" | export ", style=MUTED)
            text.append(Path(self.state.last_export_path).name, style=f"bold {ACCENT}")
        return text

    def _lead_stream_text(self) -> Text:
        lead = self.state.current_lead()
        if lead is None:
            return Text("No lead selected", style=MUTED)
        scorecard = self.state.lead_scorecard(lead)
        text = Text()
        text.append(lead.company, style=f"bold {TEXT}")
        text.append(" | ", style=MUTED)
        text.append(lead.status, style=self._status_style(lead.status))
        text.append(" | ", style=MUTED)
        text.append(f"{lead.city}, {lead.state}", style=TEXT)
        text.append("\n\n")
        self._append_score_block(text, lead, scorecard)
        text.append("\n")
        self._append_reason_block(text, lead)
        text.append("\n")
        self._append_enrichment_block(text, lead)
        text.append("\n")
        self._append_signal_block(text, lead)
        text.append("\n")
        text.append("NOTE     ", style=f"bold {MUTED}")
        text.append(lead.note or "-", style=TEXT if lead.note else MUTED)
        text.append("\n")
        text.append("CMD      ", style=f"bold {MUTED}")
        text.append("n add-note", style=PRIMARY)
        text.append(" | ", style=MUTED)
        text.append("space keep", style=SUCCESS)
        text.append(" | ", style=MUTED)
        text.append("s status", style=PRIMARY)
        text.append(" | ", style=MUTED)
        text.append("d dump", style=ACCENT)
        text.append(" | ", style=MUTED)
        text.append("esc back", style=TEXT)
        text.append("\n\n")
        text.append("NOTES", style=f"bold {MUTED}")
        for note in lead.notes[:8]:
            text.append("\n")
            text.append("note>", style=f"bold {PRIMARY}")
            text.append(" ", style=MUTED)
            text.append(f"[{note.created_at}] ", style=MUTED)
            text.append(note.body, style=TEXT)
        if not lead.notes:
            text.append("\nNo notes yet. Type below and press Enter.", style=MUTED)
        return text

    def _overview_text(self) -> Text:
        leads = self.state.visible_leads()
        if not leads:
            return Text("No leads match the current filter.", style=MUTED)

        text = Text()
        text.append("OVERVIEW", style=f"bold {TEXT}")
        text.append("\n")
        text.append(self.state.batch_label, style=f"bold {PRIMARY}")
        text.append("\n\n")

        self._append_overview_kv(
            text,
            "scope",
            (
                f"{len(leads)} contacts | {self.state.unique_company_count(leads)} companies | "
                f"{len(self.state.city_counts(leads))} cities | {self.state.email_count(leads)} direct email | "
                f"{self.state.linkedin_count(leads)} linkedin"
            ),
        )
        self._append_overview_kv(
            text,
            "multi-contact companies",
            str(sum(1 for _, count in self.state.company_counts(leads) if count > 1)),
        )
        self._append_overview_kv(
            text,
            "active filter",
            self.state.filter_text or "-",
        )
        text.append("\n")

        self._append_distribution(
            text,
            title="CONTACT COVERAGE",
            items=[
                ("email", self.state.email_count(leads)),
                ("linkedin", self.state.linkedin_count(leads)),
                (
                    "high confidence",
                    sum(1 for lead in leads if lead.contact_confidence == "high"),
                ),
                ("missing email", sum(1 for lead in leads if not lead.has_email)),
            ],
            color=SUCCESS,
            total=len(leads),
        )
        text.append("\n")
        self._append_distribution(
            text,
            title="TOP CITIES",
            items=self.state.city_counts(leads)[:8],
            color=PRIMARY,
            total=len(leads),
        )
        text.append("\n")
        self._append_distribution(
            text,
            title="TITLE MIX",
            items=self.state.title_counts(leads)[:8],
            color=WARN,
            total=len(leads),
        )
        text.append("\n")
        self._append_distribution(
            text,
            title="INDUSTRY TAGS",
            items=self.state.industry_counts(leads)[:8],
            color=ACCENT,
            total=len(leads),
        )
        text.append("\n")
        self._append_distribution(
            text,
            title="COMPANY CLUSTERS",
            items=[item for item in self.state.company_counts(leads) if item[1] > 1][:8],
            color=PRIMARY,
            total=len(leads),
        )
        text.append("\n")
        text.append("FILTER IDEAS", style=f"bold {MUTED}")
        text.append("\n")
        text.append("has:email los angeles", style=PRIMARY)
        text.append(" | ", style=MUTED)
        text.append("president construction", style=PRIMARY)
        text.append(" | ", style=MUTED)
        text.append("chief executive officer", style=PRIMARY)
        return text

    def _detail_text(self) -> Text:
        lead = self.state.current_lead()
        if lead is None:
            return Text("No lead selected", style=MUTED)
        scorecard = self.state.lead_scorecard(lead)
        text = Text()
        text.append(lead.company, style=f"bold {TEXT}")
        text.append("\n")
        text.append(f"{lead.city}, {lead.state}", style=TEXT)
        text.append("\n")
        text.append(lead.status, style=self._status_style(lead.status))
        text.append(" | ", style=MUTED)
        text.append(self._review_summary(lead), style=self._review_style(lead.reviews or 0))
        text.append(" | ", style=MUTED)
        text.append(self.state.lead_enrichment_strip(lead), style=f"bold {PRIMARY}")
        text.append("\n\n")
        self._append_score_block(text, lead, scorecard)
        text.append("\n\n")
        self._append_reason_block(text, lead)
        text.append("\n")
        self._append_enrichment_block(text, lead)
        text.append("\n")
        self._append_signal_block(text, lead)
        text.append("\n")
        self._append_field(
            text,
            "latest note",
            lead.note or "No note yet",
            TEXT if lead.note else MUTED,
        )
        return text

    def _render_lead_row(self, lead: Lead) -> tuple[Text, ...]:
        scorecard = self.state.lead_scorecard(lead)
        return (
            self._score_text(scorecard.fit, high_color=SUCCESS),
            self._score_text(scorecard.business, high_color=PRIMARY),
            self._score_text(scorecard.exit, high_color=ACCENT),
            self._score_text(scorecard.reach, high_color=SUCCESS),
            self._enrichment_text(lead),
            Text(lead.company, style=f"bold {self._lead_color(lead.status)}"),
            Text(lead.city, style=MUTED),
            Text(
                self._owner_title_preview(lead),
                style=self._owner_signal_style(lead.owner_profile.retirement_signal),
            ),
        )

    def _owner_preview(self, lead: Lead) -> str:
        owner = lead.owner_profile
        if owner.name == "-":
            return "-"
        surname = owner.name.split()[-1]
        if owner.age_band == "-" and owner.role != "-":
            return f"{surname} | {owner.role}"
        return f"{surname} {owner.age_band}"

    def _owner_title_preview(self, lead: Lead) -> str:
        owner = lead.owner_profile
        if owner.name == "-":
            return "-"
        role = owner.role if owner.role != "-" else "contact"
        return f"{owner.name} / {role}"

    def _contact_preview(self, lead: Lead) -> str:
        if lead.best_email != "-":
            return lead.best_email
        if lead.best_phone != "-" and lead.best_phone:
            return lead.best_phone
        if lead.phone:
            return lead.phone
        return "-"

    def _contact_style(self, lead: Lead) -> str:
        if lead.best_email != "-":
            return f"bold {SUCCESS}"
        if lead.best_phone != "-" or lead.phone:
            return f"bold {PRIMARY}"
        return MUTED

    def _status_style(self, status: str) -> str:
        mapping = {
            "new": TEXT,
            "keep": SUCCESS,
            "pass": DANGER,
            "exported": ACCENT,
        }
        return f"bold {mapping.get(status, TEXT)}"

    def _lead_color(self, status: str) -> str:
        mapping = {
            "new": TEXT,
            "keep": SUCCESS,
            "pass": DANGER,
            "exported": ACCENT,
        }
        return mapping.get(status, TEXT)

    def _review_style(self, reviews: int) -> str:
        if reviews >= 250:
            return f"bold {WARN}"
        if reviews >= 100:
            return f"bold {PRIMARY}"
        if reviews >= 25:
            return f"bold {TEXT}"
        return MUTED

    def _owner_signal_style(self, signal: str) -> str:
        mapping = {"high": ACCENT, "medium": WARN, "low": TEXT, "unknown": MUTED}
        return f"bold {mapping.get(signal, TEXT)}"

    def _confidence_label(self, confidence: str) -> str:
        lowered = confidence.lower()
        if lowered == "high":
            return "high"
        if lowered == "medium":
            return "med"
        return "low"

    def _confidence_style(self, confidence: str) -> str:
        lowered = confidence.lower()
        if lowered == "high":
            return f"bold {SUCCESS}"
        if lowered == "medium":
            return f"bold {WARN}"
        return MUTED

    def _review_summary(self, lead: Lead) -> str:
        if lead.reviews is None:
            return "reviews pending"
        rating = f"{lead.rating:.1f}" if lead.rating is not None else "-"
        reviews = str(lead.reviews)
        return f"{reviews} reviews @ {rating}"

    def _append_field(self, text: Text, label: str, value: str, value_style: str) -> None:
        text.append(label, style=f"bold {MUTED}")
        text.append("\n")
        text.append(value, style=value_style)
        text.append("\n\n")

    def _append_inline_field(self, text: Text, label: str, value: str, value_style: str) -> None:
        text.append(f"{label:<9}", style=f"bold {MUTED}")
        text.append(value, style=value_style)
        text.append("\n")

    def _append_score_block(self, text: Text, lead: Lead, scorecard) -> None:
        text.append("SCORES", style=f"bold {MUTED}")
        text.append("\n")
        self._append_score_line(
            text,
            label="FIT",
            value=scorecard.fit,
            caption="composite outreach fit",
            high_color=SUCCESS,
        )
        self._append_score_line(
            text,
            label="BIZ",
            value=scorecard.business,
            caption=self._business_caption(lead),
            high_color=PRIMARY,
        )
        self._append_score_line(
            text,
            label="EXIT",
            value=scorecard.exit,
            caption=self._exit_caption(lead),
            high_color=ACCENT,
        )
        self._append_score_line(
            text,
            label="RCH",
            value=scorecard.reach,
            caption=self._reach_caption(lead),
            high_color=SUCCESS,
        )

    def _append_score_line(
        self,
        text: Text,
        *,
        label: str,
        value: int,
        caption: str,
        high_color: str,
    ) -> None:
        text.append(f"{label:<5}", style=f"bold {MUTED}")
        text.append(f"{value:>3}", style=self._score_style(value, high_color=high_color))
        text.append("  ", style=MUTED)
        text.append(caption, style=TEXT if value >= 65 else MUTED)
        text.append("\n")

    def _append_reason_block(self, text: Text, lead: Lead) -> None:
        text.append("WHY THIS MAKES THE CUT", style=f"bold {MUTED}")
        text.append("\n")
        reasons = self.state.lead_reasons(lead)
        if not reasons:
            text.append("- no qualifying signals yet", style=MUTED)
            text.append("\n")
            return
        for reason in reasons:
            text.append("- ", style=MUTED)
            text.append(reason, style=TEXT)
            text.append("\n")

    def _append_enrichment_block(self, text: Text, lead: Lead) -> None:
        text.append("ENRICHMENT", style=f"bold {MUTED}")
        text.append("\n")
        flags = self.state.lead_enrichment_flags(lead)
        for index, flag in enumerate(flags):
            if index and index % 2 == 0:
                text.append("\n")
            elif index:
                text.append("   ", style=MUTED)
            text.append("[x]" if flag.present else "[ ]", style=self._flag_style(flag.present))
            text.append(" ", style=MUTED)
            text.append(flag.label, style=TEXT if flag.present else MUTED)
        text.append("\n")
        missing = self.state.lead_missing_enrichments(lead)
        if missing:
            text.append("missing: ", style=MUTED)
            text.append(", ".join(missing), style=WARN)
            text.append("\n")

    def _append_signal_block(self, text: Text, lead: Lead) -> None:
        text.append("SIGNALS", style=f"bold {MUTED}")
        text.append("\n")
        self._append_inline_field(
            text,
            "business",
            self._business_basis(lead),
            self._review_style(lead.reviews or 0) if lead.reviews is not None else MUTED,
        )
        self._append_inline_field(
            text,
            "exit",
            self._exit_basis(lead),
            self._owner_signal_style(lead.owner_profile.retirement_signal),
        )
        self._append_inline_field(
            text,
            "contact",
            self._reach_basis(lead),
            self._contact_style(lead),
        )
        self._append_inline_field(
            text,
            "source",
            lead.source,
            MUTED,
        )

    def _business_caption(self, lead: Lead) -> str:
        if lead.reviews is not None and lead.reviews >= 100:
            return "strong business signal"
        if lead.reviews is not None:
            return "business signal present"
        if lead.has_website:
            return "proxy score, reviews missing"
        return "needs review enrichment"

    def _exit_caption(self, lead: Lead) -> str:
        owner = lead.owner_profile
        if owner.retirement_signal in {"high", "medium"}:
            return "likely succession window"
        if owner.retirement_signal == "low":
            return "owner signal present"
        if owner.name != "-" and owner.role != "-":
            return "owner-led heuristic"
        return "owner timing unclear"

    def _reach_caption(self, lead: Lead) -> str:
        if lead.has_email:
            return "direct outreach path"
        if lead.owner_profile.linkedin != "-":
            return "linkedin-first outreach"
        return "reach path incomplete"

    def _business_basis(self, lead: Lead) -> str:
        parts: list[str] = []
        if lead.reviews is not None:
            parts.append(self._review_summary(lead))
        else:
            parts.append("reviews pending")
        if lead.has_website:
            parts.append("website present")
        company_hits = self.state.company_contact_count(lead.company)
        if company_hits > 1:
            parts.append(f"{company_hits} contacts at company")
        return " | ".join(parts)

    def _exit_basis(self, lead: Lead) -> str:
        owner = lead.owner_profile
        preview = self._retirement_preview(owner)
        if preview != "signal:unknown":
            return preview
        if owner.role != "-" and owner.name != "-":
            return f"{owner.role} | owner-led heuristic"
        if owner.name != "-":
            return "owner present | tenure missing"
        return "owner signal missing"

    def _reach_basis(self, lead: Lead) -> str:
        parts: list[str] = []
        if lead.has_email:
            parts.append(lead.best_email)
        elif lead.has_phone or (lead.best_phone not in {"", "-"}):
            parts.append(lead.best_phone or lead.phone or "-")
        else:
            parts.append("no direct contact")
        if lead.owner_profile.linkedin != "-":
            parts.append("linkedin")
        if lead.has_website:
            parts.append("website")
        return " | ".join(parts)

    def _append_overview_kv(self, text: Text, label: str, value: str) -> None:
        text.append(label.upper(), style=f"bold {MUTED}")
        text.append("  ", style=MUTED)
        text.append(value, style=TEXT)
        text.append("\n")

    def _append_distribution(
        self,
        text: Text,
        *,
        title: str,
        items: list[tuple[str, int]],
        color: str,
        total: int,
    ) -> None:
        text.append(title, style=f"bold {MUTED}")
        text.append("\n")
        if not items:
            text.append("No data", style=MUTED)
            text.append("\n")
            return

        scale = max(count for _, count in items) or 1
        for label, count in items:
            self._append_bar_row(
                text, label=label, count=count, scale=scale, total=total, color=color
            )

    def _append_bar_row(
        self,
        text: Text,
        *,
        label: str,
        count: int,
        scale: int,
        total: int,
        color: str,
    ) -> None:
        width = 18
        filled = 0 if count <= 0 else max(1, round((count / scale) * width))
        filled = min(width, filled)
        empty = width - filled
        percent = 0 if total <= 0 else round((count / total) * 100)
        text.append(f"{self._trim_label(label):<22}", style=MUTED)
        text.append(" ", style=MUTED)
        text.append("#" * filled, style=f"bold {color}")
        text.append("." * empty, style=DIM)
        text.append(" ", style=MUTED)
        text.append(f"{count:>3}  {percent:>3}%", style=TEXT)
        text.append("\n")

    def _trim_label(self, value: str, max_width: int = 22) -> str:
        if len(value) <= max_width:
            return value
        return f"{value[: max_width - 3]}..."

    def _score_text(self, value: int, *, high_color: str) -> Text:
        return Text(f"{value:>3}", style=self._score_style(value, high_color=high_color))

    def _score_style(self, value: int, *, high_color: str) -> str:
        if value >= 82:
            return f"bold {high_color}"
        if value >= 68:
            return f"bold {TEXT}"
        if value >= 55:
            return f"bold {WARN}"
        return f"bold {DANGER}"

    def _enrichment_text(self, lead: Lead) -> Text:
        text = Text()
        for flag in self.state.lead_enrichment_flags(lead):
            text.append(flag.token, style=self._flag_style(flag.present))
        return text

    def _flag_style(self, present: bool) -> str:
        return f"bold {SUCCESS}" if present else MUTED

    def _retirement_preview(self, owner: object) -> str:
        if not hasattr(owner, "age_band"):
            return "Unknown"
        age_band = getattr(owner, "age_band", "-")
        signal = getattr(owner, "retirement_signal", "unknown")
        years = getattr(owner, "years_at_company", "-")
        parts = []
        if age_band != "-":
            parts.append(age_band)
        if signal != "unknown":
            parts.append(f"retire:{signal}")
        if years != "-":
            parts.append(years)
        return " | ".join(parts) if parts else "signal:unknown"

    def _notify(self, message: str) -> None:
        self.notify(message, timeout=2)
