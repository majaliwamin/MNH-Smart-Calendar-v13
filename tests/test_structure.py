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
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    mobile = (ROOT / "mobile" / "lib" / "screens" / "home_screen.dart").read_text(encoding="utf-8")
    for label in ("Dashboard", "Weekly Schedule", "Monthly Calendar", "Upcoming Academic Activities",
                  "Modules", "Facilitators", "Examinations", "Recurring Activities",
                  "WhatsApp &amp; Communications", "Analytics", "Activity History",
                  "Export &amp; Sharing", "Settings"):
        assert label in html or label in mobile
    assert 'id="settings" class="menu-nav settings-nav"' in html
    assert "'Dashboard'" in mobile and "'Weekly Schedule'" in mobile
    assert 'data-view="analytics"' in html
    assert "ListTile(" in mobile and "selected: selected == 12" in mobile


def test_weekly_calendar_is_monday_to_friday_and_supports_custom_sessions():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    mobile = (ROOT / "mobile" / "lib" / "screens" / "home_screen.dart").read_text(encoding="utf-8")
    assert 'class="view-tabs"' in html
    tabs = html[html.index('id="view-tabs"'):html.index('</nav>', html.index('id="view-tabs"'))]
    assert 'data-view="weekly"' in tabs and 'data-view="upcoming"' in tabs
    assert 'id="weekly-add-session"' in html
    assert 'id="session-day"' in html and 'id="session-start"' in html and 'id="session-end"' in html
    assert 'const days=["Monday","Tuesday","Wednesday","Thursday","Friday"]' in app
    assert 'dayIndex,startTime,endTime' in app
    assert "'dayIndex': day, 'startTime': start.text, 'endTime': end.text" in mobile
    assert "dayIndex >= 5" in mobile
    assert 'showView(location.hash.slice(1)||"weekly")' in app
    assert "int selected = 1;" in mobile


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


def test_backend_has_shared_collections_and_manager_analytics():
    routes = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
    assert '"facilitators", "examinations", "recurring", "communications"' in routes
    assert '"hod", "coordinator", "executive_dean"' in routes


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


def test_month_views_are_weekday_only():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    mobile = (ROOT / "mobile" / "lib" / "screens" / "home_screen.dart").read_text(encoding="utf-8")
    monthly = app[app.index('function renderMonthly()'):app.index('function renderUpcoming()', app.index('function renderMonthly()'))]
    mobile_monthly = mobile[mobile.index('List<Widget> _monthly()'):mobile.index('List<Widget> _upcoming()', mobile.index('List<Widget> _monthly()'))]
    assert '["Mon","Tue","Wed","Thu","Fri"]' in monthly
    assert 'date.getDay()===0||date.getDay()===6' in monthly
    assert 'Choose weekday' in app and 'Friday' in app
    assert 'crossAxisCount: 5' in mobile_monthly
    assert 'DateTime(2026, 11, day).weekday <= 5' in mobile_monthly
    assert "collection == 'recurring' && field == 'day'" in mobile


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
    assert '.footer.banner{position:fixed;left:10px' in css
    assert 'bottom:calc(58px + env(safe-area-inset-bottom,0px))' in css
    assert 'Download high-resolution timetable photo — PNG' in app
    assert 'Download high-resolution timetable photo — JPEG' in app
    assert 'Download high-resolution timetable photo — WebP' in app
    assert 'scale:4' in app and 'window.downloadTimetableImage=downloadTimetableImage' in app


def test_timetable_places_lecturer_directly_after_module_code_and_theme_reaches_footer():
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    code_at = app.index('name.className="activity-name"')
    lecturer_at = app.index('lecturer.className="activity-lecturer"', code_at)
    title_at = app.index('title.className="activity-module-title"', lecturer_at)
    assert code_at < lecturer_at < title_at
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
    assert 'Attendance and completion are not yet tracked' in app
    assert '#view-analytics.vw' in css
    assert '.ana-report[hidden]{display:none}' in css
    assert '<div id="analytics-body"></div>' in html
