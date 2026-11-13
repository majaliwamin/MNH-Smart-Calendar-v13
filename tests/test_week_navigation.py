"""Structural checks for the academic week navigation and the week-aware PDF export."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")


def _tabs():
    start = HTML.index('id="view-tabs"')
    return HTML[start:HTML.index("</nav>", start)]


def test_week_control_sits_beside_analytics_in_the_primary_navigation():
    tabs = _tabs()
    assert 'data-view="analytics"' in tabs
    assert 'class="week-nav"' in tabs
    assert tabs.index('data-view="analytics"') < tabs.index('class="week-nav"'), "the week control must follow Analytics"
    for control in ('id="week-prev"', 'id="week-next"', 'id="week-now"'):
        assert control in tabs
    # Every label carries its own Monday–Friday date range.
    assert 'id="week-now-label"' in tabs and 'id="week-now-range"' in tabs
    assert "This week" in tabs and "Nov 9" in tabs


def test_week_model_is_shared_and_loaded_before_the_app():
    model = ROOT / "frontend" / "js" / "week-model.js"
    assert model.is_file()
    assert HTML.index("/js/week-model.js") < HTML.index("/js/app.js"), "the week model must load before app.js"
    source = model.read_text(encoding="utf-8")
    assert "new Date(2026, 10, 9)" in source, "the teaching block starts on Monday 9 November 2026"
    assert "WEEKDAYS = 5" in source, "teaching weeks are Monday to Friday"
    assert 'return value > 0 ? "Week " + value : "This week";' in source


def test_week_dates_are_generated_not_hardcoded():
    assert 'const dates=["9 Nov"' not in APP, "the day dates must come from the week model"
    assert "let dates=WK.dateLabels(0)" in APP
    assert "let WEEK_START=WK.startParts(0)" in APP
    for fn in ("function setWeek(", "function applyWeekView(", "function renderWeekNav(", "function initWeekNav("):
        assert fn in APP
    assert 'getElementById("week-next").addEventListener' in APP or 'document.getElementById("week-next")' in APP
    assert 'id="week-prev"' in HTML


def test_pdf_export_follows_the_selected_week():
    assert 'txt("Weekly Schedule · Monday–Friday, 9–13 Nov 2026"' not in APP, "the PDF header must not be hardcoded"
    assert "WK.label(weekOffset)" in APP and "WK.range(weekOffset)" in APP
    assert "WK.isoMonday(weekOffset)" in APP, "the PDF file name must be based on the selected week"
    assert "MNH-PhD-Timetable-" in APP
    assert "MNH-PhD-Weekly-Calendar.pdf" not in APP


def test_pdf_reads_the_button_cells_that_the_grid_actually_renders():
    # Regression: the grid renders <button class="activity">, so a textarea-only lookup
    # returned null and threw "parameter 1 is not of type 'Element'" on every export.
    assert 'td.querySelector("textarea")||td.querySelector(".activity")' in APP
    assert "const cellLabel=area=>{" in APP
    assert 'if(tr.classList.contains("lunch-row")){' in APP, "the merged Lunch Break row must be drawn across all days"


def test_pdf_draws_cell_text_and_full_intervals_not_only_form_fields():
    # Regression: fields-only exports render as empty coloured boxes in mobile readers.
    assert "if(!done&&value)" not in APP, "cell labels must always be drawn, not only when the field fails"
    assert "if(value){\n     pdf.setFont(\"helvetica\",\"bold\");pdf.setFontSize(size)" in APP
    assert "f.fieldName=\"cell_\"+r+\"_\"+c" in APP, "cells stay editable form fields"
    # The time column shows the real interval (11:00–13:30), matching the on-screen row header.
    assert 'const timeText=clean(th.textContent||tr.dataset.startTime||"")' in APP
    assert "pdf.splitTextToSize(timeText,cw0-1.6)" in APP


def test_week_control_layout_is_kept_out_of_the_printed_sheet():
    assert ".week-nav{" in CSS
    assert ".week-step{" in CSS and ".week-now{" in CSS
    assert "@media print{.week-nav{display:none!important}}" in CSS
    assert ".week-now .week-range{font:600 calc(11px * var(--text-scale))/1.1 Arial,Helvetica,sans-serif" in CSS


def test_other_views_use_the_selected_week_dates():
    assert "todayIndexFor(weekOffset)" in APP, "the schedule cards must highlight today inside the selected week"
    assert "dayEntries(c,WK.currentOffset())" in APP, "the header bell always describes the real current week"
    assert 'id="schedule-lead"' in HTML
