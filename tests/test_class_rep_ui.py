from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cara_floating_assistant_is_mounted_with_launcher():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="class-rep-assistant"' in html
    assert '/js/class-rep.js?v=13' in html
    assert '/css/class-rep.css?v=8' in html


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
    assert 'el("button", "cara-launcher", "CRARA")' in js
    assert 'CRARA (Classroom Representative & Academic Relations Assistant)' in js
    assert '"/api/class-rep/auth/" + authMode' in js
    assert "memory" not in js.lower()
    assert 'Your intelligent academic relations assistant' in js
    assert 'root.classList.remove("is-open")' in js
    assert 'function demoReply(message)' in js
    assert 'Built-in fallback · AI not configured' in js
    assert 'please check the live weekly timetable' in js



def test_cara_signup_advertises_four_character_password_minimum_and_page_lock():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert "Password (at least 4 characters)" in js
    assert "authPassword.minLength = mode === \"register\" ? 4 : 0" in js
    assert 'document.body.classList.add("cara-open")' in js
    assert "html.cara-open,body.cara-open{overflow:hidden!important" in css



def test_cara_composer_hides_memory_control_and_uses_paperclip_file_picker():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert 'cr-account", "Memory"' not in js
    assert 'header.append(identity, signOut, toggle)' in js
    assert 'setAttribute("aria-label", "Attach a file")' in js
    assert 'paperclipPath' in js
    assert '".pdf,.docx,.pptx,.xlsx,.csv,.svg,.txt,.md,.png,.jpg,.jpeg' in js
    assert '.cr-record svg,.cr-attach svg' in css


def test_cara_upload_success_is_silent_and_mobile_back_closes_assistant():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    assert "File indexed successfully" not in js
    assert "caraAssistantOpen: true" in js
    assert 'window.addEventListener("popstate"' in js
    assert "function closeCRARA()" in js


def test_cara_header_and_composer_controls_have_no_button_shapes():
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert ".cr-toggle,.cr-account,.cr-icon-button{border:0!important" in css
    assert "background:transparent!important" in css
    assert "border-radius:0!important" in css


def test_main_header_stays_frozen_and_install_icon_is_available():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    assert 'id="install-app-btn"' in html
    assert 'window.addEventListener("beforeinstallprompt"' in html
    assert 'window.addEventListener("appinstalled"' in html
    assert ".site-header{\n  position:-webkit-sticky!important;\n  position:sticky!important;" in css
    assert ".view-tabs{\n  position:-webkit-sticky!important;\n  position:sticky!important;" in css
    assert "--mnh-sticky-header-offset:82px" in css


def test_crara_login_hides_assistant_header_and_uses_full_viewport():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert "header.hidden = !open || !state.user" in js
    assert "header.hidden = !state.user" in js
    assert "header.hidden = true; body.hidden = true; authPanel.hidden = false" in js
    assert ".cr-auth-panel{position:fixed;z-index:25;top:0;right:0;bottom:0;left:0;" in css
    assert "@media(max-width:760px){.cr-auth-panel{top:0;bottom:0;" in css
