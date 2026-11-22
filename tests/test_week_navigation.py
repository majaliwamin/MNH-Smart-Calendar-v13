"""Structural checks for the academic week navigation and the week-aware PDF export."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
SERVER_PDF = (ROOT / "backend" / "app" / "services" / "pdf_export.py").read_text(encoding="utf-8")


def _tabs():
    start = HTML.index('id="view-tabs"')
    return HTML[start:HTML.index("</nav>", start)]


def test_week_control_is_in_primary_navigation_and_analytics_is_in_the_menu():
    tabs = _tabs()
    assert 'data-view="weekly"' in tabs
    assert 'class="week-nav"' in tabs
    assert 'data-view="analytics"' in HTML
    assert HTML.index('data-view="analytics"') < HTML.index('id="view-tabs"')
    for control in ('id="week-prev"', 'id="week-next"', 'id="week-now"'):
        assert control in tabs
    # Every label carries its own Monday–Sunday date range.
    assert 'id="week-now-range"' in tabs
    assert "Nov 9" in tabs


def test_week_model_is_shared_and_loaded_before_the_app():
    model = ROOT / "frontend" / "js" / "week-model.js"
    assert model.is_file()
    assert HTML.index("/js/week-model.js") < HTML.index("/js/app.js"), "the week model must load before app.js"
    source = model.read_text(encoding="utf-8")
    assert "new Date(Date.UTC(2026, 8, 7))" in source, "numbered teaching weeks start on Monday 7 September 2026"
    schedule = (ROOT / "backend" / "app" / "services" / "schedule.py").read_text(encoding="utf-8")
    assert "WEEK_START = date(2026, 11, 9)" in schedule, "the current block begins Monday 9 November 2026"
    assert "WEEKDAYS = 7" in source, "teaching weeks are Monday to Sunday"
    assert 'return value === -1 ? "Orientation Week" : "Week " + (value + 1);' in source


def test_week_dates_are_generated_not_hardcoded():
    assert 'const dates=["9 Nov"' not in APP, "the day dates must come from the week model"
    assert "let dates=WK.dateLabels(weekOffset)" in APP
    assert "let WEEK_START=WK.startParts(weekOffset)" in APP
    for fn in ("function setWeek(", "function applyWeekView(", "function renderWeekNav(", "function initWeekNav("):
        assert fn in APP
    assert 'getElementById("week-next").addEventListener' in APP or 'document.getElementById("week-next")' in APP
    assert 'id="week-prev"' in HTML


def test_pdf_export_follows_the_selected_week():
    assert 'txt("Weekly Schedule · Monday–Sunday, 9–15 Nov 2026"' not in APP, "the PDF header must not be hardcoded"
    assert "WK.label(weekOffset)" in APP and "WK.range(weekOffset)" in APP
    assert "WK.isoMonday(weekOffset)" in APP, "the PDF file name must be based on the selected week"
    assert "MNH-PhD-Timetable-" in APP
    assert "MNH-PhD-Weekly-Calendar.pdf" not in APP
    assert "day_w = (table_w - time_w) / len(WEEKDAY_NAMES)" in SERVER_PDF
    assert SERVER_PDF.count("range(len(WEEKDAY_NAMES))") >= 2


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
    # Filled cells are printed once as text; only empty cells carry a field, so no label is
    # drawn twice on top of its own form-field appearance.
    assert "if(editable&&!value){" in APP
    # The time column shows the real interval (11:00–13:30), matching the on-screen row header.
    assert 'const timeText=clean(th.textContent||tr.dataset.startTime||"")' in APP
    assert "pdf.splitTextToSize(timeText,cw0-1.6)" in APP


def test_week_control_layout_is_kept_out_of_the_printed_sheet():
    assert ".week-nav{" in CSS
    assert ".week-step{" in CSS and ".week-now{" in CSS
    assert "@media print{.week-nav{display:none!important}}" in CSS
    assert ".week-now .week-range{font:600 calc(12px * var(--text-scale))/1.1 Arial,Helvetica,sans-serif" in CSS


def test_other_views_use_the_selected_week_dates():
    assert "todayIndexFor(weekOffset)" in APP, "the schedule cards must highlight today inside the selected week"
    assert "dayEntries(c,WK.currentOffset())" in APP, "the header bell always describes the real current week"
    assert 'id="schedule-lead"' in HTML


def test_days_are_short_and_weekends_share_a_grey_editable_column():
    assert 'const days=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]' in APP
    assert 'const dayNames=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]' in APP
    assert 'weekendClass=index=>index>=5?"weekend-day":""' in APP
    assert 'th.className="daycell "+weekendClass(c)' in APP
    assert 'td.className=weekendClass(dayIndex)' in APP
    assert "--weekend-ink:#aab4c2;--weekend-bg:#222b36;--weekend-head-bg:#2c3643" in CSS
    assert 'body[data-theme="white"],body[data-theme="red"]{--weekend-ink:#4b5563;--weekend-bg:#eef1f5;--weekend-head-bg:#e2e7ed}' in CSS
    assert "#view-weekly thead th.daycell.weekend-day," in CSS
    assert "#view-weekly thead th.daycell.today-day.weekend-day" in CSS
    assert "#view-weekly tbody td.weekend-day," in CSS
    assert "#view-weekly tbody td.weekend-day .activity{pointer-events:auto;cursor:pointer}" in CSS
    assert "#view-weekly .wrap tbody td.weekend-day," in CSS
    assert "background-color:var(--weekend-bg)!important" in CSS
    assert "#view-weekly .wrap tbody td.weekend-day .activity-name," in CSS
    assert "thead th.daycell.today-day.weekend-saturday" not in CSS
    assert "thead th.daycell.today-day.weekend-sunday" not in CSS
    assert "--saturday-ink" not in CSS and "--sunday-ink" not in CSS
    assert 'const cssVar=(n,el=document.documentElement)=>getComputedStyle(el).getPropertyValue(n).trim()' in APP
    assert 'const acroColor=c=>({ch1:c[0],ch2:c[1],ch3:c[2]})' in APP
    assert "f.color=acroColor(cellInk)" in APP
    assert 'cssVar("--weekend-ink",document.body)' in APP
    assert 'cssVar("--weekend-bg",document.body)' in APP
    assert "WEEKEND_HEADER_INK" in SERVER_PDF
    assert "WEEKEND_BG" in SERVER_PDF
