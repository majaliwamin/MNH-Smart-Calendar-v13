# MNH Smart Calendar — Remediation Audit

**Package:** MNH-Smart-Calendar-Revised
**Audit date:** 10 November 2026

## Remediation completed

1. Removed Saturday from the web and Flutter timetable day lists and date labels; the monthly views now show weekdays only. The backend no longer seeds a Saturday timetable cell and now migrates all stored `cells` records assigned to day index 5 or later and Saturday recurring activities out of the schedule collections. Examination records and other unrelated collections are not deleted by this migration.
2. Added API validation that rejects new or restored Saturday/out-of-range timetable records and Saturday recurring activities.
3. Replaced the web timetable's fixed-slot-only editing path with a session interval model. New sessions have a weekday, start time and end time; rows are generated from the sorted set of start times. Activity cells show the activity label and lecturer, not the time range. Session detail and upcoming views show the actual interval.
4. Added client-side and server-side overlap checks. The server also checks the seeded Tuesday Journal Club interval.
5. Preserved legacy `row_day` cell records and their known slot/time-label interpretation. Editing a legacy entry to another weekday creates a new stable session ID and removes the former ID only after the new save is queued/sent.
6. Added mobile session creation and editing with native time pickers, Monday–Friday selection, module selection, automatic lecturer resolution and overlap validation.
7. Changed module lecturer assignment to use records from the Facilitators collection. New module records retain the facilitator record ID and canonical name; older name-only module records remain supported.
8. Added consistent visible × controls to web dialogs, including the incoming reminder dialog.
9. Restricted analytics API access to HOD, Coordinator and Executive Dean roles and aligned the web/mobile clients with that policy.
10. Added a Windows `run.ps1` helper and clarified the local backend startup instructions.

## Verification performed

| Check | Result |
|---|---|
| Python automated tests (`pytest -q`) | 28 passed |
| Python bytecode compilation (`compileall`) | Passed |
| Frontend JavaScript syntax (`node --check`) | Passed |
| API client JavaScript syntax | Passed |
| Service worker JavaScript syntax | Passed |
| Offline API queue simulation | Passed |
| FastAPI local startup (`python backend/run.py`) | Passed |
| `GET /` | HTTP 200 |
| `GET /docs` | HTTP 200 |
| `GET /health` | HTTP 200, `ok: true` |
| `GET /js/app.js` | HTTP 200 |
| Flutter analyzer/native build | Not run: Flutter/Dart SDK is not installed in this environment |
| Full interactive browser acceptance test | Not certified: headless Chromium did not complete in this environment |

## Local startup

From the extracted project root in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\run.ps1
```

Or install requirements and start directly:

```powershell
python -m pip install -r backend\requirements.txt
python backend\run.py
```

Open `http://127.0.0.1:8000/`. API docs are at `http://127.0.0.1:8000/docs`. Do not open `frontend/index.html` directly.

## Important verification limits

- Flutter source has been updated and structurally checked, but a real `flutter analyze`, Android build and iOS build require a Flutter SDK and platform toolchains.
- Browser JavaScript syntax and server-served assets were checked. The automated headless browser attempt did not complete, so user acceptance testing in Chrome/Edge remains necessary.
- Analytics calculations remain the existing friend-authored implementation; only the API authorization gate and client role checks were aligned. Attendance/missed-session metrics remain unavailable until attendance records exist.
- The academic teaching week remains explicitly fixed to 9–13 November 2026. The date is not fabricated or shifted dynamically.
