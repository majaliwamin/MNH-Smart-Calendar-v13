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

def test_weekly_calendar_is_monday_to_friday_and_supports_custom_sessions():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'class="view-tabs"' in html
    tabs = html[html.index('id="view-tabs"'):html.index('</nav>', html.index('id="view-tabs"'))]
    assert 'data-view="weekly"' in tabs
    assert 'class="week-nav"' in html
    assert 'id="view-my-schedule"' in html
    assert 'id="session-day"' in html and 'id="session-start"' in html and 'id="session-end"' in html
    assert 'const days=["Monday","Tuesday","Wednesday","Thursday","Friday"]' in app
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
    assert "9–13 November 2026" in readme
    assert '"1_5"' not in backend


def test_month_view_renders_weekdays_only_from_the_shared_malawi_week_model():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    monthly = app[app.index("function renderMonthly()"):app.index("function localActivityDate(", app.index("function renderMonthly()"))]
    assert '["Mon","Tue","Wed","Thu","Fri"]' in monthly
    assert 'weekday===0||weekday===6' in monthly
    assert 'WK.startParts(weekOffset)' in monthly
    assert 'The academic timetable displays Monday–Friday only' in monthly


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
    # The current UI creates its install notice dynamically after install eligibility is known.
    assert 'notice.id="install-app-notice"' in html
    assert 'notice.setAttribute("aria-label","tap here to install")' in html
    assert "beforeinstallprompt" in html
    assert "event.preventDefault()" in html
    assert "installFromNotice()" in html
    assert ".prompt()" in html and "userChoice" in html
    assert "appinstalled" in html
    assert "display-mode: standalone" in html
    assert "promptOpen" in html
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
    assert build == "2026.11.19-simplified-schedule-dialog-v1"
    assert f'window.MNH_BUILD="{build}"' in html
    assert f'const BUILD = "{build}"' in worker
    assert f'?v={build}' in html
