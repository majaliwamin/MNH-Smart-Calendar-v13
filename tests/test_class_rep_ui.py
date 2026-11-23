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
    assert "var(--panel)" in css and "var(--cara-silver)" in css and "var(--text)" in css
    assert "@media(max-width:760px)" in css


def test_crara_uses_a_scoped_silver_palette_including_the_graduation_cap():
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert ".cara-widget,.view-tabs .cara-launcher{" in css
    assert "--gold:#cbd5e1" in css
    assert "--cara-silver:#cbd5e1" in css
    assert "--cara-silver-rgb:203,213,225" in css
    assert "color:var(--cara-silver);border-right:2px solid rgba(var(--cara-silver-rgb),.8)" in css
    assert "filter:drop-shadow(0 2px 5px rgba(var(--cara-silver-rgb),.18))" in css
    for legacy in ("#d7ad45", "#c9a43b", "#f1d58a", "#e8c66d", "#b88b2d",
                   "#f6f1e6", "#d8d2c6", "#fff1c7", "#f5d36d",
                   "rgba(212,175,55", "rgba(215,173,69"):
        assert legacy not in css


def test_cara_starts_closed_and_has_requested_identity():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    assert 'el("button", "cara-launcher", "CRARA")' in js
    assert 'Class Rep & Academic Relations Assistant' in js
    assert 'Back to Home' in js
    assert 'homeNav.click()' in js
    assert 'cr-home-back' in js
    assert 'cr-brand-mark' in js
    assert '"/api/class-rep/auth/" + authMode' in js
    assert "cr-memory-panel" not in js
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
    assert 'brand.append(brandMark, identity)' in js
    assert 'header.append(brand, languageSwitch, signIn, homeBack)' in js
    assert 'cr-toggle' not in js
    assert 'Sign out' not in js
    assert 'Close CRARA' not in js
    assert 'setAttribute("aria-label", "Attach a file")' in js
    assert 'paperclipPath' in js
    assert '".pdf,.docx,.pptx,.xlsx,.csv,.svg,.txt,.md,.png,.jpg,.jpeg' in js
    assert '.cr-record svg,.cr-attach svg' in css


def test_cara_upload_reports_indexed_file_and_mobile_back_closes_assistant():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    assert "File indexed successfully" not in js
    assert '"Indexed " + file.name' in js
    assert "cr-upload-status" in js
    assert "caraAssistantOpen: true" in js
    assert 'window.addEventListener("popstate"' in js
    assert "function closeCRARA()" in js


def test_crara_reads_audio_uploads_and_adds_copy_and_disclaimer_to_replies():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert "audio/*,.mp3,.wav,.m4a,.aac,.ogg,.opus,.flac,.webm" in js
    assert 'const isAudio = /^audio\\//i.test(file.type || "")' in js
    assert "Audio files must be 5 MB or smaller" in js
    assert '(isAudio ? "Transcribing " : "Reading ")' in js
    assert '" · ask CRARA to summarise it"' in js
    assert "function decorateAssistantResponse(bubble, response)" in js
    assert "async function copyText(text)" in js
    assert '"Copy reply"' in js
    assert "navigator.clipboard.writeText(value)" in js
    assert 'document.execCommand("copy")' in js
    assert "I can sometimes make mistakes — please verify important details." in js
    assert "decorateAssistantResponse(bubble, answer);" in js
    assert "pending.dataset.query = message;" in js
    assert ".cr-response-actions{" in css
    assert ".cr-copy-button,.cr-feedback-button{" in css
    assert ".cr-disclaimer{" in css
    assert ".cr-upload-status{" in css


def test_cara_header_and_composer_controls_have_no_button_shapes():
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert ".cr-toggle,.cr-account,.cr-icon-button{border:0!important" in css
    assert "background:transparent!important" in css
    assert "border-radius:0!important" in css


def test_main_header_stays_frozen_and_download_menu_is_available():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    dialog_css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert 'id="install-app-btn"' not in html
    assert 'class="hd-install-btn"' not in html
    assert 'notice.id="install-app-notice"' not in html
    assert "tap here to install" not in html
    assert "Choose “Install app” from your browser’s address bar or menu" not in html
    assert "To install on iPhone or iPad" not in html
    assert "Your browser may offer" not in html
    assert 'typeof navigator.install==="function"' in html
    assert "await navigator.install();" in html
    assert "if(isLikelyAndroid())openInstallChoice();" in html
    assert "if(accept)accept.hidden=true;" in html
    assert 'window.addEventListener("beforeinstallprompt"' in html
    assert '__mnh_open_refresh' not in html
    assert "window.__mnhDeferredInstallPrompt = null;" in html
    assert 'const registerOptions = { scope: "/", updateViaCache: "none" };' in html
    assert "if(deferredPrompt)openInstallChoice();" in html
    assert 'window.addEventListener("appinstalled"' in html
    assert "Download MNH Calendar" not in html
    assert '"Show instructions"' not in html
    assert "Download statement permission" not in html
    assert "Choosing Close downloads nothing" not in html
    assert 'id="mnh-install-statement"' not in html
    assert 'id="mnh-first-open-gate" class="mnh-install-choice" role="dialog" aria-modal="true" aria-label="Install MNH Calendar" aria-describedby="mnh-install-copy"' in html
    assert 'id="mnh-install-accept">Install<' in html
    assert 'aria-label="Install MNH Calendar"' in html
    assert html.index('id="mnh-first-open-gate"') < html.index('class="activity-marquee-shell"')
    assert "Android|iPhone|iPad|iPod|Mobile" in html
    assert 'else if (mobile || forceGate) document.documentElement.classList.add("mnh-gate-open");' in html
    assert "\n ensureDialog();\n" in html
    assert "openInstallChoice();" in html
    assert "accept.hidden=false;" in html
    assert 'accept.textContent="Install";' in html
    assert ".mnh-install-statement{" not in dialog_css
    assert ".mnh-install-help{" not in dialog_css
    assert ".mnh-install-actions button[hidden]" in dialog_css
    assert ".hd-install-btn{" not in css
    assert "install-app-notice" not in css
    # The timetable export menu remains in the header after removing the install icon.
    assert 'id="dl-btn"' in html
    assert 'id="dl-menu"' in html
    assert 'data-fmt="pdf"' in html
    assert 'data-fmt="image"' in html
    assert 'data-fmt="xlsx"' in html
    assert ".hd-dlbtn{" in css
    assert "@media(max-width:720px)" in css
    assert ".site-header{\n  position:-webkit-sticky!important;\n  position:sticky!important;" in css
    assert ".view-tabs{\n  position:-webkit-sticky!important;\n  position:sticky!important;" in css
    assert "--mnh-sticky-header-offset:82px" in css


def test_crara_opens_chat_directly_with_optional_account_access():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert "function showHeader(visible)" in js
    assert "root.append(body, authPanel)" in js
    assert "root.insertBefore(header, body)" in js
    assert "header.remove()" in js
    assert "function applyChatPresentation()" in js
    assert "function openAuthPanel()" in js
    assert "function closeAuthPanel()" in js
    assert 'el("button", "cr-sign-in", "Sign in")' in js
    assert 'el("button", "cr-auth-back", "Back to chat")' in js
    assert "setAuthPresentation(false)" in js
    assert "authPanel.hidden = true" in js
    assert "body.hidden = !open || !state.user" in js
    assert 'if (!message || state.busy) return;' in js
    assert ".cr-sign-in[hidden]{display:none!important}" in css
    assert ".cr-auth-back{" in css
    assert "body.cara-auth-open #view-weekly> :not(#class-rep-assistant)" in css
    assert "async function requestJson(path, options = {})" in js
    assert 'credentials: "same-origin"' in js
    assert "Could not connect to CRARA services" in js


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
    assert "await typeReply(pending, reply)" in js
    assert ".cr-message ul,.cr-message ol" in css


def test_crara_never_shows_login_wall_when_session_check_fails():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    assert "retrySessionCheck" not in js
    assert "Retry connection" not in js
    assert "Your saved CRARA session is still protected" not in js
    assert "status(\"Services unavailable · guest chat cannot start\", false);" in js
    assert "authFeedback.textContent = error.message" in js
    assert "applyChatPresentation();" in js



def test_crara_restores_saved_session_on_app_start_without_flashing_login_form():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    assert "let authCheckComplete = true" in js
    assert "let authCheckRunning = false" in js
    assert "state.user = { id: ensureGuestId(), name: \"Guest\", email: \"\" };" in js
    assert "document.cookie = GUEST_COOKIE_NAME" in js
    assert "void checkAuth();" in js
    assert "state.user = result.user;" in js
    assert "state.guest = Boolean(result.guest);" in js
    assert "await loadPreviousConversation();" in js


def test_crara_renderer_normalizes_equations_inside_markdown_lines():
    renderer = (ROOT / "frontend" / "js" / "class-rep-renderer.js").read_text(encoding="utf-8")
    assert "equation.trim()" in renderer
    assert "doubled || single" in renderer



def test_cara_header_has_explicit_persistent_chichewa_english_selector():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert 'cr-language-switch' in js
    assert 'cr-language-option' in js
    assert 'dataset.language = "CH"' in js
    assert 'dataset.language = "EN"' in js
    assert 'PUT", headers' in js
    assert '/api/class-rep/language' in js
    assert 'response_language: state.responseLanguage' in js
    assert '.cr-language-option.is-active' in css


def test_crara_language_toggle_is_only_rendered_for_designated_signed_in_email():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert 'LANGUAGE_TOGGLE_OWNER_EMAIL = "majaliwamin@gmail.com"' in js
    assert 'function canUseLanguageToggle(user = state.user)' in js
    assert 'String(user && user.email || "").trim().toLowerCase() === LANGUAGE_TOGGLE_OWNER_EMAIL' in js
    assert 'languageSwitch.hidden = !visible || !canUseLanguageToggle()' in js
    assert 'if (state.user && canUseLanguageToggle())' in js
    assert '.cr-language-switch[hidden]{display:none!important}' in css


def test_crara_math_packages_are_served_locally_for_mobile_reliability():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    sw = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    vendor = ROOT / "frontend" / "vendor"
    for asset in ("katex/katex.min.js", "katex/katex.min.css", "katex/auto-render.min.js",
                  "marked.min.js", "purify.min.js", "chart.umd.min.js"):
        assert (vendor / asset).is_file(), asset
        assert '/vendor/' + asset in html, asset
    assert "cdnjs.cloudflare.com/ajax/libs/KaTeX" not in html
    assert "cdnjs.cloudflare.com/ajax/libs/Chart.js" not in html
    assert 'app.mount("/vendor"' in main
    assert 'url.pathname.startsWith("/vendor/")' in sw
    assert (vendor / "katex" / "fonts" / "KaTeX_Main-Regular.woff2").is_file()


def test_crara_renderer_repairs_math_and_has_readable_fallback():
    renderer = (ROOT / "frontend" / "js" / "class-rep-renderer.js").read_text(encoding="utf-8")
    assert "function repairMath(source)" in renderer
    assert "function renderPlainMath(bubble)" in renderer
    assert "STATS_MACROS" in renderer
    assert "inline delimiters nested inside display math" in renderer
    assert "window.katex && window.renderMathInElement" in renderer
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert ".cr-math-fallback" in css


def test_service_worker_precaches_every_katex_font():
    sw = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    font_dir = ROOT / "frontend" / "vendor" / "katex" / "fonts"
    fonts = sorted(path.name for path in font_dir.iterdir() if path.is_file())
    assert len(fonts) >= 40
    assert "const KATEX_FONTS = [" in sw
    assert "...KATEX_FONTS.map((name) => \"/vendor/katex/fonts/\" + name)" in sw
    for name in fonts:
        assert '"' + name + '"' in sw, name


def test_crara_wraps_bare_math_notations_in_the_shared_renderer():
    renderer = (ROOT / "frontend" / "js" / "class-rep-renderer.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "function wrapUnicodeNotation(text)" in renderer
    assert "function wrapProseNotation(text)" in renderer
    assert "var UNICODE_LATEX = {" in renderer
    assert "χ" in renderer and "ℝ" in renderer
    assert "wrapUnicodeNotation(repairProse(part))" in renderer
    # Mobile and desktop share one renderer; there is no separate phone-only path.
    assert html.count('src="/js/class-rep-renderer.js') == 1
    assert "mobile-class-rep" not in html


def test_crara_math_fallback_uses_readable_unicode_notation():
    renderer = (ROOT / "frontend" / "js" / "class-rep-renderer.js").read_text(encoding="utf-8")
    assert "SUPERSCRIPT_DIGITS" in renderer
    assert "SUBSCRIPT_DIGITS" in renderer
    assert "function unicodeDigits(value, table)" in renderer
    assert "√($1)" in renderer
    assert '"ℝ"' in renderer


def test_crara_never_stringifies_validation_errors_as_object_object():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    assert "function readableError(value)" in js
    assert "function apiError(response, result, fallback)" in js
    assert "function cleanHistory(history, max = 10)" in js
    assert "/^\\[object\\b/i.test(text)" in js
    assert "history: cleanHistory(state.history)" in js
    assert "I couldn't read part of this conversation" in js
    assert "const detail = readableError(error);" in js
    assert 'const reply = typeof result.reply === "string"' in js
    assert "state.history = cleanHistory(latest.messages, 12)" in js


def test_mobile_pwa_recovers_from_a_stale_cached_page():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    sw = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "async function recoverStaleBuild(liveBuild)" in html
    assert 'key.indexOf("mnh_auto_refresh_build_")' in html
    assert "navigator.serviceWorker.getRegistrations()" in html
    assert "caches.keys()" in html
    assert 'params.has("mnh_recover")' in html
    assert 'request.mode === "navigate" ? "/index.html" : url.pathname' in sw
    assert 'event.data.type === "MNH_CLEAR_CACHE"' in sw
    assert 'response.headers["X-MNH-Build"] = BUILD_ID' in main
    assert "RequestValidationError" in main
