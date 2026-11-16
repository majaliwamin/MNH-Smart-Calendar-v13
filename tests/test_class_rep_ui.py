from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cara_floating_assistant_is_mounted_with_launcher():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="class-rep-assistant"' in html
    assert '/js/class-rep.js?v=5' in html
    assert '/css/class-rep.css?v=4' in html


def test_cara_floating_ui_uses_theme_tokens_and_mobile_layout():
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert ".cara-widget{position:fixed" in css
    assert ".cr-head{position:fixed" in css
    assert ".cr-transcript{flex:1 1 auto;min-height:0" in css
    assert ".cara-launcher" in css
    assert "var(--panel)" in css and "var(--gold)" in css and "var(--text)" in css
    assert "@media(max-width:760px)" in css


def test_cara_starts_closed_and_has_requested_identity():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    assert 'el("button", "cara-launcher", "CARA")' in js
    assert 'CARA (Classroom and Academic Relations Assistant)' in js
    assert '/api/class-rep/auth/register' in js
    assert '/api/class-rep/memories' in js
    assert 'Your intelligent academic relations assistant' in js
    assert 'root.classList.remove("is-open")' in js
    assert 'function demoReply(message)' in js
    assert 'Built-in fallback · AI not configured' in js
    assert 'please check the live weekly timetable' in js
