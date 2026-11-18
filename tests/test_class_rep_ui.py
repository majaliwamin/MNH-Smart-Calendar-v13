from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cara_floating_assistant_is_mounted_with_launcher():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="class-rep-assistant"' in html
    assert '/js/class-rep.js?' in html
    assert '/css/class-rep.css?' in html


def test_cara_floating_ui_uses_theme_tokens_and_mobile_layout():
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert ".cara-widget{position:static" in css
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
    assert 'header.append(identity)' in js
    assert 'cr-toggle' not in js
    assert 'Sign out' not in js
    assert 'Close CRARA' not in js
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
    assert 'notice.id="install-app-notice"' in html
    assert 'window.addEventListener("beforeinstallprompt"' in html
    assert 'window.addEventListener("appinstalled"' in html
    assert ".site-header{\n  position:-webkit-sticky!important;\n  position:sticky!important;" in css
    assert ".view-tabs{\n  position:-webkit-sticky!important;\n  position:sticky!important;" in css
    assert "--mnh-sticky-header-offset:82px" in css


def test_crara_login_hides_assistant_header_and_uses_full_viewport():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert "function showHeader(visible)" in js
    assert "root.append(body, authPanel)" in js
    assert "root.insertBefore(header, body)" in js
    assert "header.remove()" in js
    assert "showHeader(false); body.hidden = true;" in js
    assert "authPanel.hidden = !root.classList.contains(\"is-open\")" in js
    assert "showHeader(Boolean(open && state.user))" in js
    assert "function setAuthPresentation(active)" in js
    assert "body.cara-auth-open .site-header" in css
    assert "body.cara-auth-open .view-tabs" in css
    assert "body.cara-auth-open .bottom-nav" in css
    assert "body.cara-auth-open #view-weekly> :not(#class-rep-assistant)" in css
    assert "async function requestJson(path, options = {})" in js
    assert 'credentials: "same-origin"' in js
    assert "Could not connect to CRARA services" in js
    assert ".cr-auth-panel{position:fixed;z-index:25;top:0;right:0;bottom:0;left:0;" in css
    assert "@media(max-width:760px){.cr-auth-panel{top:0;bottom:0;" in css


def test_crara_is_sticky_in_landing_navigation_and_hidden_during_scheduling():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert 'landingNav.appendChild(launcher)' in js
    assert 'window.setCRARALandingVisible' in js
    assert 'window.setCRARASchedulingVisible' in js
    assert 'window.setCRARALandingVisible(name==="weekly")' in app
    assert 'window.setCRARASchedulingVisible(true)' in app
    assert 'window.setCRARASchedulingVisible(false)' in app
    assert '.view-tabs .cara-launcher{position:fixed;left:14px;right:auto;bottom:14px' in css
    assert '.cara-widget{position:static' in css


def test_crara_formats_markdown_and_reveals_answers_progressively():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert "function renderMarkdown(bubble, value)" in js
    assert 'token.startsWith("**") ? "strong" : "em"' in js
    assert 'const type = bullet ? "ul" : "ol"' in js
    assert "async function typeReply(bubble, value)" in js
    assert "await typeReply(pending, result.reply)" in js
    assert ".cr-message ul,.cr-message ol" in css


def test_crara_keeps_login_form_hidden_when_saved_session_cannot_be_verified():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    assert "let retrySessionCheck = false" in js
    assert "A temporary network/API failure is not proof that the saved session expired." in js
    assert 'authSubmit.textContent = "Retry connection"' in js
    assert "if (retrySessionCheck)" in js
    assert 'authName.hidden = true; authEmail.hidden = true; authPassword.hidden = true;' in js



def test_crara_restores_saved_session_on_app_start_without_flashing_login_form():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    assert "let authCheckComplete = false" in js
    assert "let authCheckRunning = false" in js
    assert "void checkAuth();" in js
    assert "|| !authCheckComplete" in js
    assert "authPanel.hidden = !root.classList.contains(\"is-open\") || Boolean(state.user);" in js


def test_crara_renderer_normalizes_equations_inside_markdown_lines():
    renderer = (ROOT / "frontend" / "js" / "class-rep-renderer.js").read_text(encoding="utf-8")
    assert "equation.trim()" in renderer
    assert "doubled || single" in renderer
