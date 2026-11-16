from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_class_rep_assistant_is_mounted_beneath_weekly_timetable():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    start = html.index('id="view-weekly"')
    end = html.index('id="view-my-schedule"', start)
    weekly = html[start:end]
    assert weekly.index('id="calendar-body"') < weekly.index('id="class-rep-assistant"')
    assert 'class="class-rep-assistant"' in weekly
    assert '/js/class-rep.js?v=1' in html
    assert '/css/class-rep.css?v=1' in html


def test_class_rep_ui_uses_theme_tokens_and_mobile_layout():
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert "var(--panel)" in css and "var(--gold)" in css and "var(--text)" in css
    assert "@media(max-width:760px)" in css
