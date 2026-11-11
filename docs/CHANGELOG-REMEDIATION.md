# Remediation change log — 10 November 2026

## Files changed

- `backend/app/database/connection.py` — Monday–Friday seed data, weekday-only monthly views, and startup migration for Saturday/out-of-range timetable cells and Saturday recurring activities.
- `backend/app/api/routes.py` — management-only analytics authorization; weekday/time validation; server-side session overlap checks; restore validation.
- `backend/tests/test_api.py` — analytics authorization, safe restore behavior, custom interval validation, overlap rejection, Saturday rejection and migration tests.
- `frontend/index.html` — custom weekday/start/end controls and weekly Add Session action.
- `frontend/js/app.js` — normalized legacy/custom session model, variable timetable rows, interval details, overlap validation, facilitator resolution, Monday–Friday filtering, CSV date-safe export and close controls.
- `frontend/css/app.css` — custom session cell presentation and consistent dialog close control styling.
- `mobile/lib/screens/home_screen.dart` — custom start/end pickers, weekday-only session creation/editing, weekday-only recurring activity selection, overlap checks, lecturer resolution and corrected analytics role checks.
- `mobile/lib/widgets/section_card.dart` — retains modern `withValues(alpha: ...)` usage; no deprecated `withOpacity` remains.
- `tests/test_structure.py` — updated structural checks to verify actual navigation and the new Monday–Friday/custom-session behavior rather than stale formatting-specific source strings.
- `README.md`, `backend/README.md`, `docs/AUDIT-REPORT.md` — corrected startup and scheduling documentation.
- `run.ps1` — new Windows startup helper that creates/reuses `.venv` and installs requirements only when missing.

## Preservation

The existing analytics implementation and dashboard calculations were retained. The API access check was narrowed to the documented management roles. Existing legacy timetable IDs remain readable; timetable records assigned to Saturday or a later day index and recurring activities explicitly assigned to Saturday are removed during startup migration. No Git commit or push was made.


## Follow-up: timetable display, themes and programme analytics

- Timetable activity cards now use the module code, module title resolved from the Modules directory, and facilitator resolved from the Facilitators directory; time ranges remain in session details rather than replacing the lecturer line.
- Removed per-session colour overrides from the scheduling form so the selected application theme controls timetable cells consistently. Theme styles now cover the timetable, workspace, analytics, monthly view and hamburger panel while the masthead remains navy/gold.
- Added explicit session outcome recording (scheduled, completed, missed). The outcome is included in cloud/offline synchronisation and drives missed-session metrics; unknown outcomes are not automatically counted as missed.
- Added optional semester session/hour targets when creating a module. Analytics now report weekly sessions and hours per module, semester-to-date sessions and hours, target progress, missed counts/rates, and online versus face-to-face counts.
- Updated the service-worker cache to v8 so browsers replace the previously cached interface that could still display the Saturday column.
- Expanded analytics API response while retaining legacy `counts` and `delivery_modes` fields for compatibility.
- Added a focused analytics aggregation test covering module targets, teaching hours, missed sessions and delivery mode.


## Editable Excel timetable export

- Added `GET /api/export/timetable.xlsx`, which generates an `.xlsx` workbook from the shared timetable and module/facilitator records.
- Added an Export & Sharing page action for downloading the Excel workbook.
- Workbook sheets: `Weekly Timetable` (Monday–Friday grid with internal hyperlinks), `Session Details` (editable/filterable session register), and `Read Me`.
- Module titles and lecturer names are resolved from the module and facilitator records.
- Added `openpyxl` to backend dependencies and bumped the service-worker cache to v9.
- Excel edits are local to the downloaded workbook; they do not automatically write back to the shared calendar.


## 10 November 2026 — Footer placement and high-resolution image exports

- Anchored the Penrose ScholarMw footer at the lower-left of the viewport. On mobile it sits above the fixed bottom navigation, leaving the Home/dashboard navigation control unobstructed.
- Added weekly timetable image downloads in PNG, JPEG and WebP formats from Export & Sharing. Images are rendered at 4× scale; unsupported WebP encoding falls back to PNG with the correct file extension.
- Bumped the service-worker shell cache to v9 so the updated interface is fetched.


## Optional entry colours (10 November 2026)

- Added an Entry colour selector to web and Flutter session forms.
- Added a default “No colour — use current theme” choice. Selecting it removes any saved custom colour so the timetable uses the active theme styling.
- Added optional named palette colours for users who want colour-coded entries.
- Existing entries retain their previously saved colours when edited unless the user selects No colour.
- Incremented the service-worker cache to v10.

## v13 (10 Nov 2026) — startup, cache, theme, lunch, Excel
- One start method: `.\run.ps1` (also the VS Code task, limited to one instance). It runs `scripts\diagnose-server.ps1` first, then `backend\run.py`, which refuses to start if the port is taken and names the owner. Default 127.0.0.1:8000; `MNH_PORT`, `MNH_HOST`, `MNH_LAN=1`; hosting uses `PORT`.
- `/api/build` and `/health` report the build id; the page purges caches and reloads once if it differs from the server's.
- Service worker is network-first; assets are versioned `?v=<build>`. Bump BUILD in `config.py`, `service-worker.js`, `index.html` together (a test checks they match).
- Theme tokens drive the whole workspace; Light is white.
- Lunch Break row 12:00–13:30 (web + Excel). Excel export rebuilt in `services/excel_export.py`.
- Non-weekday records are flagged, no longer deleted.
- Facilitator initials ignore titles; photos accept common formats.
- Not verified: Flutter (no SDK), real-browser rendering, Windows startup.
