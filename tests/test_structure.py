from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_modular_backend_and_clients_exist():
    assert (ROOT / "backend" / "app" / "main.py").is_file()
    assert (ROOT / "backend" / "app" / "api" / "routes.py").is_file()
    assert (ROOT / "backend" / "app" / "database" / "connection.py").is_file()
    assert (ROOT / "backend" / "app" / "services" / "backup_service.py").is_file()
    assert (ROOT / "frontend" / "index.html").is_file()
    assert (ROOT / "frontend" / "css" / "app.css").is_file()
    assert (ROOT / "frontend" / "js" / "app.js").is_file()
    assert (ROOT / "frontend" / "js" / "api-client.js").is_file()
    assert (ROOT / "mobile" / "pubspec.yaml").is_file()
    assert (ROOT / "mobile" / "lib" / "main.dart").is_file()


def test_health_routes_and_browser_address_guidance():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    main = (root / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    run = (root / "backend" / "run.py").read_text(encoding="utf-8")
    assert '@app.get("/health", include_in_schema=False)' in main
    assert '@app.get("/api/health/ready", include_in_schema=False)' in main
    assert "http://127.0.0.1:" in run


def test_run_script_resolves_backend_from_project_root():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    run = (root / "backend" / "run.py").read_text(encoding="utf-8")
    assert "app_dir=str(BACKEND_DIR)" in run


def test_full_navigation_and_pinned_settings_are_present():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    menu = html[html.index('<div class="menu-links">'):html.index("</div>", html.index('<div class="menu-links">'))]
    for label in ("Monthly Calendar", "Modules", "Facilitators", "Examinations",
                  "Analytics", "WhatsApp &amp; Communications", "Activity History", "Resources"):
        assert label in menu
    for view in ("monthly", "modules", "facilitators", "examinations",
                 "analytics", "communications", "history", "resources"):
        assert f'data-view="{view}"' in menu
    assert 'id="view-analytics"' in html
    assert 'id="view-workspace"' in html

def test_alarm_system_configurations_navigation_opens_existing_alarm_controls():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'id="alarms"' in html
    assert 'id="alarm-dialog"' in html
    assert 'id="alarm-title"' in html and "Alarms" in html
    assert 'document.getElementById("alarms").addEventListener("click",()=>{refreshAlarmUI();showDialog("alarm-dialog");})' in app
    assert 'document.getElementById("alarm-close").addEventListener("click",()=>hideDialog("alarm-dialog"))' in app

def test_talking_alarm_uses_random_time_greetings_without_a_user_name():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    alarm_code = app[app.index("// ---- Alarms"):app.index("function startRing")]
    for forbidden in ("getAlarmUserName", "alarmUserName", "alarmUserPromise", "/api/class-rep/auth/me", "user.name"):
        assert forbidden not in alarm_code
    for token in (
        'const hour=WK.localNow().hour;',
        'hour<12?"Good morning":(hour<17?"Good afternoon":"Good evening")',
        '[byTime,"Hello","Hi"][Math.floor(Math.random()*3)]',
        'sessionName=[ev.label,ev.sub].filter(Boolean).join(", ")',
        'const mins=Math.max(0,Math.round((ev.start.getTime()-Date.now())/60000))',
        'const start=mins>0?"in "+mins+" minute"+(mins===1?"":"s"):"now"',
        'const templates=[',
        'Math.floor(Math.random()*templates.length)',
        'const message=alarmReminderMessage(ev)',
    ):
        assert token in alarm_code, token
    assert alarm_code.count("Please be prepared.") == 6


def test_weekly_calendar_is_monday_to_sunday_and_supports_custom_sessions():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'class="view-tabs"' in html
    tabs = html[html.index('id="view-tabs"'):html.index('</nav>', html.index('id="view-tabs"'))]
    assert 'data-view="weekly"' in tabs
    assert 'class="week-nav"' in html
    assert 'id="view-my-schedule"' in html
    assert 'id="session-day"' in html and 'id="session-start"' in html and 'id="session-end"' in html
    assert 'const days=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]' in app
    assert 'const dayNames=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]' in app
    assert '<option value="5">Sat</option><option value="6">Sun</option>' in html
    assert 'dayIndex,startTime,endTime' in app
    assert 'showView("weekly")' in app
    assert 'history.replaceState(null,"",location.pathname+location.search)' in app
    assert 'hashchange' not in app


def test_scheduling_uses_bounded_date_and_arbitrary_time_pickers():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    mobile = (ROOT / "mobile" / "lib" / "screens" / "home_screen.dart").read_text(encoding="utf-8")
    assert 'i.type=type' in app
    assert 'if(type==="date")' in app
    assert 'i.min=iso(now)' in app
    assert 'i.max=iso(new Date(now.getFullYear()+3' in app
    assert 'id="session-start" type="time"' in html
    assert 'id="session-end" type="time"' in html
    assert "showDatePicker(" in mobile
    assert "firstDate: today" in mobile
    assert "lastDate: DateTime(now.year + 3, now.month, now.day)" in mobile
    assert "showTimePicker(" in mobile
    assert "Icons.calendar_month_outlined" in mobile
    assert "Icons.schedule_outlined" in mobile

def test_recent_activity_panel_is_removed_from_every_view():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    assert 'id="ops-panel"' not in html
    assert 'id="ops-history"' not in html
    assert 'id="ops-status"' not in html
    assert "Recent activity</h2>" not in html
    assert "refreshHistory" not in app
    assert "refreshHealth" not in app
    assert "ops-panel" not in css
    assert "window.exportTimetableCSV" in app
    assert "window.downloadSharedBackup" in app


def test_backend_has_shared_collections_and_public_analytics():
    routes = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '"facilitators", "examinations", "recurring", "communications"' in routes
    assert 'return {"role": "public"}' in routes
    assert 'management_roles' not in routes
    assert 'let editingUnlocked=true;' in app
    assert 'let analyticsUnlocked=true;' in app
    assert 'function requestAnalytics()' in app
    assert 'security-dialog' not in html
    assert 'type="password"' not in html

def test_cells_show_activity_and_lecturer_without_time_ranges_and_dialogs_can_close():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    assert 'name.className="activity-name"' in app
    assert 'lecturer.className="activity-lecturer"' in app
    assert 'area.textContent=entry.label' not in app
    assert 'close.className="dialog-close"' in app
    assert 'id==="call-dialog"?stopRing():hideDialog(id)' in app
    assert '.dialog-close{' in css and '.call-card{position:relative}' in css


def test_windows_startup_helper_and_correct_teaching_dates_are_documented():
    run = (ROOT / "run.ps1").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    backend = (ROOT / "backend" / "app" / "database" / "connection.py").read_text(encoding="utf-8")
    assert "backend\\run.py" in run
    assert "http://127.0.0.1:8000/docs" in run
    assert "9–15 November 2026" in readme
    assert '"1_5"' not in backend


def test_month_view_renders_weekdays_only_from_the_shared_malawi_week_model():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    monthly = app[app.index("function renderMonthly()"):app.index("function localActivityDate(", app.index("function renderMonthly()"))]
    assert '["Mon","Tue","Wed","Thu","Fri"]' in monthly
    assert 'weekday===0||weekday===6' in monthly
    assert 'WK.startParts(weekOffset)' in monthly
    assert 'The monthly calendar displays weekdays only; the weekly timetable includes Saturday and Sunday' in monthly


def test_reported_flutter_lint_patterns_are_corrected():
    home = (ROOT / "mobile" / "lib" / "screens" / "home_screen.dart").read_text(encoding="utf-8")
    section = (ROOT / "mobile" / "lib" / "widgets" / "section_card.dart").read_text(encoding="utf-8")
    assert "withOpacity(" not in home + section
    assert ".withValues(alpha:" in section
    assert "if (!mounted) {" in home
    assert "if (accepted != true) {" in home


def test_footer_is_fixed_above_mobile_navigation_and_image_exports_are_available():
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert '.footer.banner{background:var(--panel);color:var(--text);border-color:var(--line)}' in css
    assert '.footer.banner' in css
    assert 'Download high-resolution timetable photo — PNG' in app
    assert 'Download high-resolution timetable photo — JPEG' in app
    assert 'Download high-resolution timetable photo — WebP' in app
    assert 'scale:4' in app and 'window.downloadTimetableImage=downloadTimetableImage' in app


def test_image_exports_include_a_header_and_use_larger_fonts():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    start = app.index("async function downloadTimetableImage")
    end = app.index("window.downloadTimetableImage=downloadTimetableImage", start)
    export_code = app[start:end]
    for token in (
        'getElementById("hd-title")',
        'getElementById("hd-sub")',
        'WK.label(weekOffset)',
        'WK.range(weekOffset)',
        "MNH SMART TIMETABLE",
        'setProperty("--text-scale","1.85","important")',
        'setProperty("font-size","28px","important")',
        'exportWidth=1200',
        'setTimeout(finish,250)',
    ):
        assert token in export_code, token


def test_image_export_captures_the_full_timetable_without_clipping():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    start = app.index("async function downloadTimetableImage")
    end = app.index("window.downloadTimetableImage=downloadTimetableImage", start)
    export_code = app[start:end]
    for token in (
        "const exportWidth=1200,exportPadding=24,tableWidth=exportWidth-(exportPadding*2);",
        "const captureHeight=Math.max(1800,Math.ceil(target.scrollHeight*3)+600);",
        "windowWidth:exportWidth,windowHeight:captureHeight",
        'const force=(node,prop,value)=>node.style.setProperty(prop,value,"important");',
        'force(wrap,"box-sizing","border-box")',
        'force(wrap,"overflow","visible")',
        'force(table,"width",tableWidth+"px")',
        "timeWidth=130,dayWidth=Math.floor((tableWidth-timeWidth)/7)",
        'force(cell,"position","static")',
        'const weekendBg=variable("--weekend-bg")||cellBg',
        'force(table,"font-family","Arial,Helvetica,sans-serif")',
        'force(cell,"background-color",weekendBg)',
        'force(button,"border-color",onWeekend?weekendInk:line)',
    ):
        assert token in export_code, token


def test_timetable_places_lecturer_directly_after_module_code_and_theme_reaches_footer():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    code_at = app.index('name.className="activity-name"')
    lecturer_at = app.index('lecturer.className="activity-lecturer"', code_at)
    assert code_at < lecturer_at
    assert "getSessionEntries" in app
    assert "endMinutes" in app
    assert '.footer.banner{background:var(--panel);color:var(--text);border-color:var(--line)}' in css

def test_analytics_does_not_present_timetable_templates_as_semester_attendance():
    routes = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert '"semesterTracked": False' in routes
    assert 'Not yet tracked — dated attendance records are required' in app
    assert 'if(m.semesterTracked&&m.targetSessions' in app
    assert 'if(m.semesterTracked&&m.targetHours' in app


def test_analytics_management_dashboard_keeps_reference_layout_and_honest_states():
    routes = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '"dashboard": dashboard' in routes
    assert '"attendance": {' in routes
    assert '"academicYears": academic_years' in routes
    assert 'Analytics – Management Access' in app
    assert 'Session Mode Distribution' in app
    assert 'Weekly Attendance Trend' in app
    assert 'Module Performance' in app
    assert 'Upcoming Actions' in app
    assert 'Insights & Recommendations' in app
    assert 'View Detailed Report' in app
    assert 'Academic Year ' in app
    assert 'No dated attendance records yet' in app
    assert 'Completion is not yet tracked; record dated session outcomes to calculate module completion.' in routes
    assert 'attendance_available = False' in routes
    assert '#view-analytics.vw' in css
    assert '.ana-report[hidden]{display:none}' in css
    assert '<div id="analytics-body"></div>' in html

def test_weekly_timetable_tracks_malawi_local_week_and_live_time_without_weekends():
    week = (ROOT / "frontend" / "js" / "week-model.js").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    mobile = (ROOT / "mobile" / "lib" / "screens" / "home_screen.dart").read_text(encoding="utf-8")
    assert 'const TIME_ZONE = "Africa/Blantyre"' in week
    assert "function currentOffset()" in week and "function currentDayIndex(offset)" in week
    assert "let weekOffset=WK.currentOffset()" in app
    assert "setInterval(syncCurrentAcademicWeek,15000)" in app
    assert "function refreshLiveTimetable()" in app
    assert "today-day" in css and "current-time-row" in css and "current-slot" in css
    assert "DateTime.now().toUtc().add(const Duration(hours: 2))" in mobile
    assert "_currentWeekMonday" in mobile and "_isCurrentSlot" in mobile
    assert "DateTime(2026, 11, 9 +" not in mobile



def test_upcoming_activities_are_future_only_and_use_shared_records():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert "async function getFutureActivities()" in app
    assert "dayEntries(day,WK.currentOffset())" in app
    assert "session.start.getTime()>now" in app
    assert 'loadRows("examinations")' in app
    assert 'loadRows("recurring")' in app
    assert "start.getTime()<=now" in app
    assert "function nextRecurringDate(dayName,timeText,now)" in app
    assert "const items=(await getFutureActivities()).slice(0,12)" in app


def test_pwa_install_requirements_are_met():
    import json

    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    # Manifest exists, is valid JSON, and describes an installable standalone app.
    manifest_path = ROOT / "frontend" / "manifest.json"
    assert manifest_path.is_file()
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    assert manifest["name"] == "MNH Calendar"
    assert manifest["short_name"] == "MNH Calendar"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"

    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert "192x192" in sizes and "512x512" in sizes
    for icon in manifest["icons"]:
        if icon["src"].endswith(".png"):
            assert (ROOT / "frontend" / icon["src"].lstrip("/")).is_file()

    assert 'rel="manifest"' in html and "/manifest.json" in html
    # Installation uses only real browser install APIs. The header icon,
    # blinking weekly notice, and all fallback instruction text are gone.
    assert 'id="install-app-btn"' not in html
    assert 'class="hd-install-btn"' not in html
    assert 'aria-label="Download and install MNH Calendar"' not in html
    assert 'notice.id="install-app-notice"' not in html
    assert "tap here to install" not in html
    assert "Choose “Install app” from your browser’s address bar or menu" not in html
    assert "To install on iPhone or iPad" not in html
    assert "Your browser may offer" not in html
    assert "Installation was not completed" not in html
    assert 'id="mnh-install-help"' not in html
    assert 'typeof navigator.install==="function"' in html
    assert "const canInstall=()=>hasWebInstall()||!!deferredPrompt;" in html
    assert "if(isLikelyAndroid())openInstallChoice();" in html
    assert "await navigator.install();" in html
    assert "markInstalled();\n    closeInstallGate();" in html
    assert "beforeinstallprompt" in html
    assert "event.preventDefault()" in html
    # Android Chrome needs an uninterrupted root-scoped PWA registration. The
    # first-load redirect is gone, the event is captured before any reload can
    # occur, and a captured event is consumed by the install UI immediately.
    assert "__mnh_open_refresh" not in html
    assert "window.__mnhDeferredInstallPrompt = null;" in html
    assert 'window.addEventListener("beforeinstallprompt", function (event)' in html
    assert "  }, true);" in html
    assert 'const registerOptions = { scope: "/", updateViaCache: "none" };' in html
    assert "registerWorker();" in html
    assert "let deferredPrompt=window.__mnhDeferredInstallPrompt||null;" in html
    assert "if(deferredPrompt)openInstallChoice();" in html
    assert "window.__mnhDeferredInstallPrompt=null;" in html
    assert "await promptEvent.prompt();" in html
    assert "userChoice" in html
    assert 'if(choice&&choice.outcome==="accepted"){' in html
    assert "if(accept)accept.hidden=true;" in html
    assert "promptOpen" not in html
    assert 'has("mnh_force_gate")' in html
    assert "appinstalled" in html
    assert "display-mode: standalone" in html
    assert "mnh-install-choice" in html
    # The static gate starts hidden. It is revealed only when the browser
    # supplies navigator.install() or a beforeinstallprompt event. No fake
    # install action is ever shown in browsers that support neither.
    assert "Download MNH Calendar" not in html
    assert '"Show instructions"' not in html
    assert "Download statement permission" not in html
    assert "Choosing Close downloads nothing" not in html
    assert 'id="mnh-install-statement"' not in html
    assert 'id="mnh-first-open-gate" class="mnh-install-choice" role="dialog" aria-modal="true" aria-label="Install MNH Calendar" aria-describedby="mnh-install-copy"' in html
    assert 'id="mnh-install-accept">Install<' in html
    assert 'aria-label="Install MNH Calendar"' in html
    assert html.index('id="mnh-first-open-gate"') < html.index('class="activity-marquee-shell"')
    assert 'else if (mobile || forceGate) document.documentElement.classList.add("mnh-gate-open");' in html
    assert 'document.documentElement.classList.add("mnh-install-exempt")' in html
    assert "Android|iPhone|iPad|iPod|Mobile" in html
    assert "\n ensureDialog();\n" in html
    assert "openInstallChoice();" in html
    assert "accept.hidden=false;" in html
    assert 'accept.textContent="Install";' in html
    dialog_css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    app_css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    assert ".mnh-install-statement{" not in dialog_css
    assert ".mnh-install-help{" not in dialog_css
    assert ".mnh-install-actions button[hidden]" in dialog_css
    assert ".mnh-install-exempt #mnh-first-open-gate" in dialog_css
    assert ".hd-install-btn{" not in app_css
    assert "install-app-notice" not in app_css
    assert '@app.get("/manifest.json", include_in_schema=False)' in main
    assert 'app.mount("/icons"' in main
    assert ">\\n<" not in html
    assert "\\n" not in manifest_text

def test_editable_weekly_grid_pdf_fields_default_to_eighteen_point():
    """The fillable weekly timetable cells default to 18pt when editing.

    An explicit 18pt default keeps typed entries legible both in desktop PDF
    viewers and in Google Drive's PDF editor, which otherwise falls back to a
    small auto-sized appearance. Only the weekly grid cells change; the module
    directory and session register keep their existing 16pt default.
    """
    pdf = (ROOT / "backend" / "app" / "services" / "pdf_export.py").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")

    # Server-side fillable PDF (ReportLab): a named 18pt default drives the weekly grid.
    assert "EDIT_FIELD_FONT_SIZE = 18" in pdf
    assert "preset, font_size=EDIT_FIELD_FONT_SIZE, multiline=True," in pdf
    # Module directory and register fields still request their explicit 16pt.
    assert pdf.count("font_size=16") >= 4

    # Browser-side fillable PDF (jsPDF): empty weekly cells become 18pt form fields.
    assert "f.fontSize=18;f.fontName=" in app


def test_empty_weekly_cells_export_as_fillable_fields_not_plus_placeholders():
    """The browser PDF treats the "+" placeholder as a blank cell.

    Empty weekly cells carry an "empty-activity" class and render a "+"
    placeholder. The export must ignore that placeholder so those cells become
    fillable 18pt fields rather than literal "+" text, which previously also
    suppressed the field entirely because the placeholder read as content.
    """
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    start = app.index("const cellLabel=area=>{")
    block = app[start:app.index("};", start)]
    assert 'classList.contains("empty-activity")' in block



def test_history_records_additions_updates_deletions_and_restores():
    routes = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
    assert "action IN ('added','updated','deleted','restored')" in routes
    assert 'write_activity(c, session["role"], action, collection, item_id, summary)' in routes
    assert 'write_activity(c, "public", "deleted", collection, item_id' in routes
    assert "make_backup()" in routes
    assert "safety_backup_created" in routes


def test_database_backups_are_published_atomically():
    backup = (ROOT / "backend" / "app" / "services" / "backup_service.py").read_text(encoding="utf-8")
    assert "tempfile.mkstemp" in backup
    assert "os.replace(temporary, target)" in backup
    assert "source.backup(destination)" in backup
    assert "Retention is applied only after a new complete snapshot" in backup



def test_shared_writes_are_serialised_across_devices_and_restore():
    routes = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock(20261116, 1500)" in routes
    assert "with DB_LOCK:" in routes
    assert routes.count("@serialised_shared_write") >= 3


def test_upcoming_announcement_ticker_is_open_ended_and_refresh_control_is_ui_hidden():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")

    # Keep the refresh control and its existing handler, but remove it visually.
    assert 'id="mnh-refresh-btn"' in html
    assert 'getElementById("mnh-refresh-btn")' in app
    assert 'button.addEventListener("click",async function(){' in app
    assert ".upcoming-announcements-row #mnh-refresh-btn{display:none!important}" in css

    # The announcement strip has no enclosing frame or rounded ends.
    assert "border:0;" in css and "border-radius:0;" in css
    assert "animation:activity-flow-right 90s linear infinite" in css

    # The animated strip is direct body markup and must render on the home view only.
    assert 'html body > .activity-marquee-shell[aria-label="Future academic events"]{' in css
    assert (
        'html body.weekly-view:not(.is-content-view):not(.cara-open):not(.cara-auth-open)'
        ':not(.python-library-view) > .activity-marquee-shell[aria-label="Future academic events"]{'
    ) in css


def test_secondary_views_offer_home_return_navigation():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")

    # Secondary views use an explicit home-return control; resources has its own view state.
    assert 'document.body.classList.toggle("weekly-view",name==="weekly")' in app
    assert 'function ensureHomeReturnButton(name)' in app
    assert 'button.className="view-home-return"' in app
    assert 'button.addEventListener("click",()=>showView("weekly"))' in app
    assert ".view-home-return" in css

def test_hamburger_menu_fits_content_and_has_mobile_back_navigation():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'id="menu-panel" role="navigation" aria-label="Calendar navigation"' in html
    assert 'class="menu-nav" data-view="monthly"' in html
    assert "Monthly Calendar" in html
    assert ".site-header .menu-panel{" in css
    assert ".menu-nav{min-height:44px" in css
    assert "touch-action:manipulation" in css
    assert 'document.querySelectorAll(".menu-nav[data-view]")' in app
    assert 'button.className="view-home-return"' in app
    assert "Back to Home" in app
    assert 'button.addEventListener("click",()=>showView("weekly"))' in app



def test_crara_preserves_latex_delimiters_through_markdown_and_bumps_assets():
    renderer = (ROOT / "frontend" / "js" / "class-rep-renderer.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    backend_config = (ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")

    assert "mathDelimiters.push({token: token, delimiter: delimiter})" in renderer
    assert "mathDelimiters.forEach(function (item)" in renderer
    assert "window.renderMathInElement(bubble" in renderer
    import re
    build = re.search(r'BUILD_ID = "([^"]+)"', backend_config).group(1)
    assert build == "2026.11.22-statistical-tests-glossary-v44"
    assert f'window.MNH_BUILD="{build}"' in html
    assert f'const BUILD = "{build}"' in worker
    assert f'?v={build}' in html


def test_python_library_resource_is_served_with_opt_in_runner():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    resource_dir = ROOT / "frontend" / "resources"

    assert 'src="/resources/python-command-library.html?runner=off&full=1&v=2026.11.22-statistical-tests-glossary-v44"' in html
    assert 'id="view-python-library"' in html
    assert 'id="python-library-back"' in html
    # All three reference views are launched from Resources only; they have no
    # standalone navigation-menu item or bottom-nav tab.
    assert 'data-view="python-library"' not in html
    assert 'href="#python-library"' not in html
    assert 'data-view="stat8100-practical"' not in html
    assert 'data-view="hypothesis-lab"' not in html
    assert 'id="open-python-library"' in html
    assert "Open Python Library full screen" in html
    # The Resources section is a launcher only; its old placeholder copy is gone.
    assert "Python &amp; Jupyter Command Library" not in html
    assert "Installation guidance, Python commands and Jupyter Notebook reference." not in html
    assert "The reference is available in this section." not in html
    assert "Backend execution starts off" not in html
    assert 'aria-label="Python Command Library for biomedical and health sciences"' in html
    assert 'title="Python Command Library for biomedical and health sciences"' in html
    assert 'app.mount("/resources", StaticFiles(directory=str(FRONTEND_DIR / "resources")), name="resources")' in main
    assert (resource_dir / "python-command-library.html").is_file()
    assert (resource_dir / "biomedical_api.js").is_file()
    assert (resource_dir / "sample_data.js").is_file()
    assert (resource_dir / "samples" / "anc_cohort.csv").is_file()

    build = "2026.11.22-statistical-tests-glossary-v44"
    simulation_path = resource_dir / "python-jupyter-windows-setup-simulation.html"
    assert simulation_path.is_file()
    simulation = simulation_path.read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    assert f'src="/resources/python-jupyter-windows-setup-simulation.html?full=1&v={build}"' in html
    assert 'id="view-python-setup-simulation"' in html
    assert 'id="python-setup-simulation-back"' in html
    assert '"python-setup-simulation"' in app
    assert 'MNH_OPEN_SETUP_SIM' in app
    assert 'contentWindow.fit?.()' in app
    assert 'body.python-library-view #view-python-setup-simulation:not([hidden])' in css
    assert '"/resources/python-jupyter-windows-setup-simulation.html"' in worker
    assert "Windows Python and JupyterLab setup simulation" in simulation
    assert "viewport-fit=cover" in simulation
    assert "full-screen-simulation" in simulation
    assert "function screenScale()" in simulation
    assert "ResizeObserver" in simulation
    assert "html.full-screen-simulation .wrap" in simulation
    assert "html.full-screen-simulation .ctl" in simulation
    assert "html.full-screen-simulation #zw" in simulation
    assert "width:100%;height:100%" in css
    assert "simUrl.searchParams.set(\"start\",\"find\")" in app
    assert "enteringSimulation" in app
    assert "{n:'Find',t:'Stage 1: Find the official Python site'" in simulation
    assert "sub('Find the official Python site'" in simulation
    assert "Always begin at stage 1, Find" in simulation
    assert "go(0);" in simulation
    assert "Watch simulation" in simulation or "Watch simulation" in (resource_dir / "python-command-library.html").read_text(encoding="utf-8")

    library = (resource_dir / "python-command-library.html").read_text(encoding="utf-8")
    assert "Watch simulation" in library
    assert ">Watch simulation</button>" in library
    assert ">(Watch simulation)</button>" not in library
    assert ".setup-simulation-button{font-weight:700;white-space:nowrap;background:#082f6b;" in library
    assert "data-open-setup-simulation" in library
    assert "function openSetupSimulation()" in library
    assert "MNH_OPEN_SETUP_SIM" in library
    bridge = (resource_dir / "biomedical_api.js").read_text(encoding="utf-8")
    assert '<script src="./biomedical_api.js" defer></script>' in library
    assert "Simulated data 1: anc_cohort.csv" in bridge
    assert 'pageParams.get("runner")' in bridge
    assert "function requireRunner()" in bridge
    assert 'button.dataset.bmExecType !== "notebook"' in bridge
    assert "public/embedded pages never inherit the local trusted backend URL" in bridge
    assert "runnerEnabled && !embeddedMode" in bridge
    assert "Enter a trusted backend API URL before enabling the runner." in bridge
    assert "bm-chapter-index" in bridge
    assert 'var LIBRARY_TITLE = "Python Command Library for biomedical and health sciences";' in bridge
    assert "function renameLibraryTitle()" in bridge
    assert "renameLibraryTitle();" in bridge
    assert 'request("/analysis/methods"' in bridge
    assert 'request("/analysis", { method: "POST", body: body })' in bridge
    assert 'request("/notebooks", {' in bridge
    assert 'request("/reports", {' in bridge
    assert "Download report" in bridge
    assert "function hidePanel()" in bridge
    assert "function showPanel()" in bridge
    assert "clearDatasetState(" in bridge

    # The cover is a static landing page; the generated index and the original
    # topic navigation are both injected/rendered after it, together.
    cover_pos = library.index('class="cover-page" id="designed-cover-page"')
    topics_pos = library.index("<nav>")
    assert cover_pos < topics_pos
    # The cover is static: no animated biomedical overlay objects remain.
    assert "bio-motion" not in library
    assert "bio-sprite" not in library
    assert "@keyframes" not in library
    assert "bio-motion" not in bridge
    assert "bio-sprite" not in bridge
    assert "addStyles();" in bridge
    assert bridge.count("hidePanel();") == 1
    assert 'if (reopenButtonEl) reopenButtonEl.style.display = "block";' in bridge
    assert ".bm-copy-in-code{" in bridge
    assert "preEl.appendChild(copyBtn)" in bridge
    assert 'copyBtn.textContent = "⧉";' in bridge
    assert 'preEl.style.paddingTop = "38px";' in bridge
    assert "originalNav.parentNode.insertBefore(index, originalNav)" in bridge
    assert "insertBefore(index, cover);" not in bridge
    assert "cover.nextSibling" in bridge

    app_js = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    assert '"python-library"' in app_js
    assert "python-library-view" in app_js
    assert "python-library-back" in app_js
    assert 'currentView!=="python-library"' in app_js
    assert 'name!=="python-library"' in app_js
    assert "body.python-library-view .bottom-nav" in css
    assert ".python-library-frame" in css
    assert ".python-library-back" in css


def test_python_library_topics_are_organized_into_tracks():
    import re

    resource_dir = ROOT / "frontend" / "resources"
    library = (resource_dir / "python-command-library.html").read_text(encoding="utf-8")
    bridge = (resource_dir / "biomedical_api.js").read_text(encoding="utf-8")

    nav = library.split("<nav>", 1)[1].split("</nav>", 1)[0]
    tracks = re.findall(
        r'<div class="topic-track" data-track="([^"]+)"><strong>\1</strong>', nav
    )
    assert tracks == [
        "Foundations",
        "Data handling",
        "Wrangling, visualisation &amp; aggregation",
        "Statistical methods &amp; modelling",
        "Applied biomedical labs",
        "Projects &amp; reproducibility",
        "Reference &amp; audit",
    ]

    links = re.findall(
        r'<a href="#([^"]+)" data-topic-label="([^"]+)">([^<]+)</a>', nav
    )
    assert len(links) == 44
    assert len({href for href, _, _ in links}) == 44
    assert all(label == text for _, label, text in links)
    section_ids = set(re.findall(r'\bid="([^"]+)"', library))
    assert all(href in section_ids for href, _, _ in links)
    assert library.count('data-topic-track="') == 44

    # Companions no longer borrow conflicting McKinney chapter numbers.
    assert "Chapter 4: Cleaning and quality assurance" not in library
    assert "Chapter 10B: Advanced methods II" not in library
    assert 'data-topic-label="Coverage &amp; audit"' in library
    assert 'nav a[href^="#"]' in library

    # The embedded chapter index follows the same seven-track organization.
    assert "var TOPIC_TRACKS = [" in bridge
    assert ".bm-chapter-track{margin:10px 0 2px}" in bridge
    assert "Organized topics (" in bridge
    assert 'var linkHost = nav.querySelector(".topic-track-links") || nav;' in bridge


def test_python_library_windows_setup_simulation_is_additive():
    resource_dir = ROOT / "frontend" / "resources"
    library = (resource_dir / "python-command-library.html").read_text(encoding="utf-8")
    bridge = (resource_dir / "biomedical_api.js").read_text(encoding="utf-8")

    assert library.count('<script src="./biomedical_api.js" defer></script>') == 1
    assert "var SIM_KEY = 'biomedical_windows_setup_sim_v1';" in bridge
    assert "root.id = 'bm-windows-simulation';" in bridge
    assert "function createWindowsSimulation()" in bridge
    assert "    createWindowsSimulation();" in bridge
    assert "window.BiomedicalSimulation" in bridge
    assert "API.windowsSimulation" in bridge
    assert "function simExec(raw, options)" in bridge
    assert "function simRunBatch(text)" in bridge
    assert "Simulated state only. This module never runs host commands or edits PATH." in bridge
    assert "This lab only interprets the Windows setup commands taught in this chapter and never runs host commands" in bridge
    for fault_id in (
        "python-not-recognised", "pip-not-recognised", "store-alias", "wrong-python",
        "multiple-installs", "jupyter-not-found", "package-install-failure",
        "dependency-conflict", "path-not-refreshed", "ps-activation-blocked",
        "invalid-directory-path", "permission-denied", "imports-fail",
        "notebook-wrong-kernel",
    ):
        assert "'" + fault_id + "':" in bridge
    for command in (
        "python --version", "py --version", "python -m pip --version",
        "where.exe python", "where.exe py", "py -0p", "python -m venv ",
        "freeze > requirements.txt", "'-r '",
        "jupyter notebook", "jupyter lab", "winver",
    ):
        assert command in bridge


def test_service_worker_cache_writes_are_guarded():
    worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")

    assert "async function cacheResponse(key, response)" in worker
    assert "await cache.put(key, response)" in worker
    assert 'cacheResponse(request.mode === "navigate" ? "/index.html" : url.pathname, response.clone())' in worker
    assert 'request.mode === "navigate" ? "/index.html"' in worker
    assert 'caches.match("/index.html")' in worker
    assert "caches.open(CACHE_NAME).then((cache) => cache.put(" not in worker


def test_schedule_session_outcomes_and_dialog_close_button():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    app_css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")

    schedule_dialog = html.split('id="module-dialog"', 1)[1].split('id="details-dialog"', 1)[0]
    assert '<option value="cancelled">Cancelled</option>' in schedule_dialog
    assert '<option value="rescheduled">Rescheduled</option>' in schedule_dialog
    assert "session-outcome-hint" in schedule_dialog
    assert 'id="module-colour"' not in html
    assert 'getElementById("module-colour")' not in app_js
    assert 'String(previous.weekStart||"").trim()||WK.isoMonday(weekOffset)' in app_js
    assert ".dialog-card .dialog-close{z-index:6!important;" in app_css
    # Empty module-details was reserving a blank row immediately above Session outcome.
    assert ".module-details:empty{display:none!important;}" in app_css
    # The global animated upcoming-events strip must not appear in either CRARA state.
    assert "body.cara-open .activity-marquee-shell" in app_css
    assert "body.cara-auth-open .activity-marquee-shell" in app_css


def test_install_gate_on_android_without_help_links():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")

    # Only the first-open Install/Close gate is visible; no help links or popups.
    assert "/install-help.html" not in html
    assert "Install help" not in html
    assert "How to install on your phone" not in html
    assert ".hd-install-help{" not in css
    assert 'id="mnh-first-open-gate"' in html
    assert 'id="mnh-install-accept"' in html
    assert 'id="mnh-install-decline"' in html
    assert ">Install<" in html
    assert ">Close<" in html

    # The gate opens on Android mobile even when no install API exists yet.
    assert 'const isLikelyAndroid=()=>/Android|SamsungBrowser/i.test(navigator.userAgent)' in html
    assert "if(isLikelyAndroid())openInstallChoice();" in html
    assert "if(isStandalone()||hasInstalled()||userClosed||!canInstall())return;" not in html
    assert "if(isStandalone()||hasInstalled()||userClosed)return;" in html
    assert "if(hasWebInstall())" in html
    assert "await navigator.install();" in html
    assert "await promptEvent.prompt();" in html


def test_statistical_tests_glossary_is_additive_and_reproducible():
    resource_dir = ROOT / "frontend" / "resources"
    glossary_path = resource_dir / "python-statistical-tests-glossary.html"
    generator = (ROOT / "scripts" / "build_statistical_glossary.py").read_text(encoding="utf-8")
    library = (resource_dir / "python-command-library.html").read_text(encoding="utf-8")
    worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    backend_config = (ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    build = "2026.11.22-statistical-tests-glossary-v44"
    assert f'BUILD_ID = "{build}"' in backend_config
    assert f'window.MNH_BUILD="{build}"' in index
    assert f'const BUILD = "{build}"' in worker
    assert '"/resources/python-statistical-tests-glossary.html"' in worker
    assert glossary_path.is_file()

    import html
    import re

    glossary = glossary_path.read_text(encoding="utf-8")
    plain = html.unescape(glossary)
    assert build in glossary
    assert glossary.count('<article class="entry"') == 46

    code_blocks = [
        html.unescape(block)
        for block in re.findall(r'<pre id="code-\d+"><code>(.*?)</code></pre>', glossary, re.S)
    ]
    output_blocks = [
        html.unescape(block).strip()
        for block in re.findall(r'<div class="output-wrap">.*?<pre>(.*?)</pre>', glossary, re.S)
    ]
    assert len(code_blocks) == len(output_blocks) == 44
    term_ids = re.findall(r'<h3 id="(term-\d+)"', glossary)
    assert len(term_ids) == len(set(term_ids)) == 46
    assert all("SIMULATED TEACHING DATA" in block for block in code_blocks)
    assert all("default_rng(" in block for block in code_blocks)
    assert all(block and not re.search(r"\b(?:nan|inf|infinity)\b", block, re.I)
               for block in output_blocks)
    for category in ("foundations", "groups", "categories", "association", "regression", "advanced"):
        assert f'id="cat-{category}"' in glossary
    for label in (
        "English definition",
        "Kufotokozera mu Chichewa",
        "Analogy",
        "Python example",
        "Code explanation",
        "Practical application",
        "Common misconception",
    ):
        assert label in glossary
    assert "Fanizo" in glossary
    assert "When to use" not in plain
    assert "Assumptions / design checks" not in plain
    assert "Limitations and mistakes to avoid" not in plain
    assert "Plain-language idea" not in plain
    assert "How to report it" not in plain
    assert ">None<" not in glossary
    assert "searchable glossary, not a textbook" in plain

    requested = [
        "Independent samples t-test", "Paired samples t-test", "Welch’s t-test",
        "Chi-square test", "Fisher’s exact test", "Analysis of Variance (ANOVA)",
        "Mann–Whitney U Test",
        "Wilcoxon Signed-Rank Test", "Pearson Correlation", "Spearman Rank Correlation",
        "Linear regression", "Logistic regression", "Odds ratio", "Risk ratio",
        "Hazard ratio", "Confounding", "Interaction", "Multicollinearity",
        "Survival analysis",
    ]
    for term in requested:
        assert f'>{term}</span>' in plain, term
    for grouped in (
        "Welch two-sample t-test", "Welch's t-test", "Paired t-test",
        "Mann-Whitney U test", "One-way ANOVA with Tukey follow-up",
        "2x2 table, risk ratio and odds ratio",
        "Chi-square test of independence and Cramer's V", "Fisher exact test",
        "Fisher's exact test", "ANOVA", "Spearman rank correlation",
        "Analysis of variance (ANOVA)", "Mann–Whitney U test",
        "Wilcoxon signed-rank test", "Pearson correlation", "Spearman correlation",
        "Simple linear regression", "Logistic regression and odds ratios",
        "Confounding and crude versus adjusted effect",
        "Interaction and effect modification", "Multicollinearity and VIF",
    ):
        assert f'>{grouped}</span>' not in plain, grouped
    assert "SIMULATED TEACHING DATA" in glossary
    assert "fixed-seed simulated teaching data" in plain
    assert "lifelines" not in generator
    assert "import requests" not in generator
    assert "Expected 46 entries" in generator
    assert "code=None" in generator

    assert "Next phase — Statistical tests and modelling" in library
    assert "46 individual terms" in library
    assert "Open bilingual statistics reference" in library
    assert "function openStatisticalGlossary()" in library
    assert "'/resources/python-statistical-tests-glossary.html'" in library


def test_supplied_statistical_glossary_wording_is_preserved():
    import html
    import re

    glossary = html.unescape(
        (ROOT / "frontend" / "resources" / "python-statistical-tests-glossary.html")
        .read_text(encoding="utf-8")
    )
    cards = {}
    for card in re.findall(r'<article class="entry".*?</article>', glossary, re.S):
        match = re.search(r'<h3 id="term-\d+"><span class="lang en">(.*?)</span>', card)
        if match:
            cards[match.group(1)] = card

    expected = {
        "Analysis of Variance (ANOVA)": [
            "A statistical method used to compare the means of three or more independent groups.",
            "ANOVA imathandiza kufufuza ngati pali kusiyana kwakukulu pakati pa ma average a magulu atatu kapena kuposerapo.",
            "Comparing the average examination scores of students from three different classes.",
            "scipy.stats.f_oneway(group1, group2, group3)",
            "A significant ANOVA result does not tell us exactly which groups differ. Post-hoc comparisons may be needed.",
        ],
        "Mann–Whitney U Test": [
            "A non-parametric test for comparing two independent groups using the ranks of their observations.",
            "Mayesowa amafananitsa magulu awiri osadalirana pogwiritsa ntchito malo amene ma observations awo ali nawo akasanjidwa kuyambira pa ochepa kufika pa ambiri.",
            "Comparing the rankings of two groups rather than comparing their raw averages.",
            "scipy.stats.mannwhitneyu(group1, group2)",
            "It is not automatically a test of differences in medians; its interpretation depends on the distributions.",
        ],
        "Wilcoxon Signed-Rank Test": [
            "A non-parametric test for comparing two related measurements.",
            "Mayesowa amafananitsa miyeso iwiri yokhudzana, monga kulemera kwa mwana asanalandire chithandizo ndi pambuyo pake, pogwiritsa ntchito kusiyana ndi ma rank ake.",
            "Examining how each participant's measurement changes rather than treating the two groups as unrelated.",
            "scipy.stats.wilcoxon(before, after)",
            "It is not suitable for two independent groups.",
        ],
        "Pearson Correlation": [
            "Measures the strength and direction of a linear relationship between two continuous variables.",
            "Pearson correlation imasonyeza mmene variables ziwiri zimayendera limodzi pa ubale wa mzere wowongoka (linear relationship), komanso mphamvu ndi direction ya ubalewo.",
            "Examining whether birth weight tends to increase as gestational age increases.",
            "scipy.stats.pearsonr(gestational_age, birth_weight)",
            "Correlation does not establish causation.",
        ],
        "Spearman Rank Correlation": [
            "Measures the strength and direction of a monotonic relationship using ranked observations.",
            "Spearman correlation imagwiritsa ntchito ma rank a observations kuti ifufuze ngati variable imodzi imakonda kukwera kapena kutsika pamene ina ikusintha.",
            "Comparing participants' positions in two rankings rather than their actual numerical measurements.",
            "scipy.stats.spearmanr(variable1, variable2)",
            "Spearman correlation does not require a linear relationship, but it still does not prove causation.",
        ],
    }
    for term, snippets in expected.items():
        assert term in cards, term
        for snippet in snippets:
            assert snippet in cards[term], (term, snippet)


def test_revised_example_outputs_stay_in_expected_ranges():
    import html
    import re

    glossary = html.unescape(
        (ROOT / "frontend" / "resources" / "python-statistical-tests-glossary.html")
        .read_text(encoding="utf-8")
    )
    cards = {}
    for card in re.findall(r'<article class="entry".*?</article>', glossary, re.S):
        match = re.search(r'<h3 id="term-\d+"><span class="lang en">(.*?)</span>', card)
        if match:
            cards[match.group(1)] = card

    def output_for(term):
        card = cards[term]
        match = re.search(r'<div class="output-wrap">.*?<pre>(.*?)</pre>', card, re.S)
        assert match, term
        return match.group(1).strip()

    def number(pattern, text, term):
        match = re.search(pattern, text)
        assert match, (term, pattern)
        return float(match.group(1))

    anova = output_for("Analysis of Variance (ANOVA)")
    f = number(r"F = ([0-9.]+)", anova, "ANOVA")
    p = number(r"p = ([0-9.eE+-]+)", anova, "ANOVA")
    assert 11.0 <= f <= 12.0
    assert 0 < p < 0.001

    mann = output_for("Mann–Whitney U Test")
    u = number(r"U = ([0-9.]+)", mann, "Mann–Whitney")
    p = number(r"p = ([0-9.eE+-]+)", mann, "Mann–Whitney")
    effect = number(r"rank-biserial effect = (-?[0-9.]+)", mann, "Mann–Whitney")
    assert 650 <= u <= 800
    assert 0.15 <= p <= 0.40
    assert -0.25 <= effect <= 0.0

    wilcoxon = output_for("Wilcoxon Signed-Rank Test")
    w = number(r"W = ([0-9.]+)", wilcoxon, "Wilcoxon")
    p = number(r"p = ([0-9.eE+-]+)", wilcoxon, "Wilcoxon")
    median = number(r"median change = (-?[0-9.]+)", wilcoxon, "Wilcoxon")
    assert 140 <= w <= 180
    assert 0 < p <= 0.02
    assert median < 0

    pearson = output_for("Pearson Correlation")
    r = number(r"Pearson r = ([0-9.]+)", pearson, "Pearson")
    ci = re.search(r"95% CI = ([0-9.]+) to ([0-9.]+)", pearson)
    assert ci
    low, high = float(ci.group(1)), float(ci.group(2))
    assert 0.70 <= r <= 0.82
    assert 0.60 <= low <= 0.70
    assert 0.80 <= high <= 0.88

    spearman = output_for("Spearman Rank Correlation")
    rho = number(r"Spearman rho = ([0-9.]+)", spearman, "Spearman")
    ci = re.search(r"approx 95% CI = ([0-9.]+) to ([0-9.]+)", spearman)
    assert ci
    low, high = float(ci.group(1)), float(ci.group(2))
    assert 0.95 <= rho <= 0.99
    assert 0.94 <= low <= 0.97
    assert 0.97 <= high <= 0.99


def test_generated_glossary_matches_generator_output(tmp_path):
    import importlib.util

    generator_path = ROOT / "scripts" / "build_statistical_glossary.py"
    spec = importlib.util.spec_from_file_location("statistical_glossary_generator", generator_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generated = tmp_path / "python-statistical-tests-glossary.html"
    module.OUTPUT = generated
    module.main()
    committed = (
        ROOT / "frontend" / "resources" / "python-statistical-tests-glossary.html"
    ).read_bytes()
    assert generated.read_bytes() == committed


def test_glossary_search_result_count_is_live():
    generator = (ROOT / "scripts" / "build_statistical_glossary.py").read_text(encoding="utf-8")
    rendered = (
        ROOT / "frontend" / "resources" / "python-statistical-tests-glossary.html"
    ).read_text(encoding="utf-8")
    assert 'id="result-count"' in generator
    assert 'aria-live="polite"' in generator
    assert "countEn.textContent='Showing '" in generator
    assert "countNy.textContent='Kuwonetsa mawu '" in generator
    assert 'id="result-count"' in rendered
    assert 'aria-live="polite"' in rendered


def test_cover_page_has_requested_subtitle_and_no_microscope():
    import base64
    import hashlib
    import re

    library = (ROOT / "frontend" / "resources" / "python-command-library.html").read_text(
        encoding="utf-8"
    )
    assert "FOR BIOMEDICAL &amp; HEALTH SCIENCES RESEARCH" in library
    assert "For Biomedical &amp; Health Sciences Research" not in library
    assert "static histogram, density curve and statistical symbols" in library
    assert "bio-sprite" not in library
    assert "bio-motion" not in library
    assert "@keyframes" not in library
    assert "methodological review v42" in library
    assert "no microscope illustration" in library
    assert "no course-name labels" in library

    # Ignore embedded image data when checking source copy: base64 text can
    # contain incidental letter sequences.
    source_copy = re.sub(r'data:image/[^"]+', "", library)
    source_copy = re.sub(r"/\*.*?\*/", "", source_copy, flags=re.S)
    source_copy = re.sub(r"<!--.*?-->", "", source_copy, flags=re.S).lower()
    assert "microscope" not in source_copy

    match = re.search(r"data:image/png;base64,([A-Za-z0-9+/=]+)", library)
    assert match
    digest = hashlib.sha256(base64.b64decode(match.group(1))).hexdigest().upper()
    assert digest == "6AD9E74A84A3127929E1BE0B1CE68B7C58F542954BDA3474591E7EC6631974D6"
