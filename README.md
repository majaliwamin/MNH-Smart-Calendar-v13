# MNH Calendar — Web + Flutter + FastAPI

A shared academic calendar with a web interface, a separate Flutter mobile client, and a modular Python backend. The web and mobile clients use one API and one central SQLite database.

## Project layout

```text
MNH-Calendar/
├── backend/
│   ├── app/
│   │   ├── api/                 # REST endpoints
│   │   ├── database/            # SQLite connection and schema
│   │   ├── models/              # Domain model package
│   │   ├── schemas/             # API schema package
│   │   ├── services/            # Authentication, audit, backups
│   │   ├── utils/               # Shared helpers
│   │   ├── config.py
│   │   └── main.py              # FastAPI application
│   ├── tests/
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── run.py
├── frontend/                    # Existing web UI (HTML/CSS/JS)
├── mobile/                      # Flutter/Dart mobile client
│   ├── lib/
│   │   ├── core/
│   │   ├── models/
│   │   ├── screens/
│   │   ├── services/
│   │   ├── widgets/
│   │   ├── app.dart
│   │   └── main.dart
│   ├── pubspec.yaml
│   └── README.md
├── database/                    # Local SQLite database (created at runtime)
├── backups/                     # Automatic SQLite snapshots (created at runtime)
├── render.yaml           # Render Blueprint configuration
├── run.ps1               # Windows local startup helper
├── docs/
└── tests/
```

## 1. Run locally on Windows

Install Python 3.10 or newer. Open the project root in VS Code, then run in the integrated terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\run.py
```

Alternatively, run `Set-ExecutionPolicy -Scope Process Bypass` once in the current PowerShell window, then use `.\run.ps1`. The helper creates `.venv` and installs backend dependencies only when needed. It starts the same verified entry point.

Open `http://127.0.0.1:8000/` (or `http://localhost:8000/`). Do not enter `http://0.0.0.0:8000/` in a browser: `0.0.0.0` is only the server listening address. The server binds to `0.0.0.0` so it can accept connections from other devices on the same LAN. The terminal prints the local network address. This LAN address is only for the same network; it is not an internet address.

To stop the local server, press `Ctrl+C` in the terminal. Do not open `frontend/index.html` directly or use VS Code Live Server: the application requires the API server for shared records.

## CARA — Classroom and Academic Relations Assistant

CARA is the persistent academic assistant in the web application. Its AI provider priority is Cloudflare Workers AI, then Gemini, then Groq. Credentials are server-side environment variables only.

The CARA backend is in `backend/app/class_rep/`:

- `config.py` and `providers.py`: provider configuration and fallback.
- `assistant.py` and `context.py`: response orchestration and live timetable context.
- `memory.py`: individual accounts, persistent conversations, memories, tasks and reminders.
- `documents.py`: account-owned document indexing and retrieval.
- `routes.py` and `schemas.py`: authenticated API endpoints and request validation.

### CARA account setup

Open CARA from the web dashboard and create an account using your name, email address and a password of at least 12 characters. Sign in on later visits to restore your previous conversation and access your account-scoped memories, tasks, uploaded documents and reminders. Passwords are stored as salted PBKDF2 hashes; session cookies are HttpOnly.

CARA memory is stored in the existing application database. It uses recent conversation retrieval, keyword matching for saved memories and tasks, and semantic document retrieval when the configured embedding service is available. Private CARA collections are excluded from public timetable exports. On Render, a persistent database is required: the Free web-service filesystem is temporary, so account registration and memory are disabled until `DATABASE_URL` points to a durable database, or a paid service has an actual persistent disk mounted at the configured `MNH_DATA_DIR` (for example, `/var/data`). A free Render Postgres instance expires after 30 days and is not suitable as permanent production storage.

### CARA environment variables

Set these in Render → Environment. Do not commit credentials:

- `MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID`
- `MNH_CLASSREP_CLOUDFLARE_API_KEY`
- `MNH_CLASSREP_CLOUDFLARE_MODEL`
- `MNH_CLASSREP_GEMINI_API_KEY` (optional free fallback; `GEMINI_API_KEY` is also accepted). Only the key is required — the endpoint defaults to Gemini's standard chat-completions-compatible route and the model defaults to the free-tier `gemini-3.5-flash-lite`. `MNH_CLASSREP_GEMINI_MODEL` and `MNH_CLASSREP_GEMINI_BASE_URL` are optional overrides. Hugging Face variables are no longer read because free-only HF tokens return HTTP 402 for Inference Providers.
- `MNH_CLASSREP_GROQ_API_KEY` (optional fallback; only the key is required — the endpoint defaults to Groq's standard chat-completions route and the model defaults to Groq's current fast 27B production model with reasoning disabled). `MNH_CLASSREP_GROQ_MODEL` and `MNH_CLASSREP_GROQ_BASE_URL` are optional overrides. Add a model override only if Groq changes its supported-model list.

Providers are tried in order: Cloudflare → Gemini → Groq. When Cloudflare is
rate-limited or out of credits, CRARA automatically uses the next configured
provider; when Cloudflare recovers it becomes primary again without a redeploy.
Check `/api/class-rep/status` for `fallbacks` to confirm Gemini and Groq are active.
- `MNH_CLASSREP_CLOUDFLARE_EMBEDDING_MODEL`
- `MNH_CLASSREP_CLOUDFLARE_STT_MODEL` (optional speech-to-text model)
- `MNH_CLASSREP_CLOUDFLARE_TTS_MODEL` (optional text-to-speech model)

The Communications Centre has a separate optional provider configuration: `MNH_COMM_AI_API_KEY`, `MNH_COMM_AI_BASE_URL`, `MNH_COMM_AI_MODEL`, and `MNH_COMM_AI_TRIGGER_ENABLED`. Its endpoint and model must be explicitly configured; the application assumes no default vendor or model.

### CARA reminders

CARA can create persistent in-app reminders in the `Africa/Blantyre` timezone. They become due in the account reminder list and are visible when the user returns to CARA. No SMS, email or push notification channel is currently configured, so CARA does not claim to send external notifications.

## 2. Access from different Wi-Fi networks / mobile data

For access outside the local network, deploy the service publicly. The included `render.yaml` configures a Render web service with:

- A public HTTPS service URL.
- FastAPI/Uvicorn startup and a health-check endpoint.
- A persistent 1 GB disk mounted at `/var/data` for the SQLite database and backup snapshots.
- A single shared API origin for the web client and Flutter client.

### Deploy using Render Blueprint

1. Push this project to a GitHub repository.
2. Sign in to Render and choose **New → Blueprint**.
3. Connect the repository and select `render.yaml` as the Blueprint file.
4. When prompted, set strong unique values for `MNH_ADMIN_PASSWORD` and `MNH_LECTURER_PASSWORD`. Set HOD/coordinator passwords if those roles are being used. Production mode disables the local development defaults (`rep` and `staff`).
5. Deploy and wait for the service to become Live.
6. Open the public `https://...onrender.com` URL. The web UI and API are served from that same address.

**Persistent storage note:** the Render configuration uses a paid Starter web service because SQLite requires persistent disk storage. A free ephemeral service is not suitable for the authoritative calendar database or backups: data may be lost on restart/redeploy. Keep the persistent disk attached and do not deploy multiple independent service instances against this SQLite database.

The local `database/` and `backups/` directories are used during development. In Render, both are placed under `/var/data` through `MNH_DATA_DIR`, so they survive ordinary service restarts and redeployments.

### Offline browser use

The web app registers a service worker that caches the same-origin application shell (HTML, CSS and JavaScript). Calendar data and shared collections are cached in browser storage after a successful online read. Timetable, module, resource, settings and workspace writes made while the API is unreachable are queued locally and retried when connectivity returns. The queue is preserved if the server rejects a write; sign in again if the editing session has expired. Do not clear this site's browser storage while queued writes are pending. Service workers require HTTPS or localhost; an ordinary HTTP LAN address does not qualify. External Google Fonts, html2canvas and jsPDF CDN files are not included in the offline shell, so PDF export may require an internet connection. The Flutter client remains online-only in this release.

## 3. Flutter / Dart mobile app

The `mobile/` directory contains the separate Flutter source. See `mobile/README.md` for SDK setup and commands. The Dart source is included; the Flutter SDK generates native runner folders when you prepare the app for Android/iOS/web. After deployment, use the Render URL as the API base:

```powershell
cd mobile
flutter pub get
flutter analyze
# If the Android runner folder is not present yet, generate platform scaffolding:
flutter create --platforms=android,web --project-name mnh_calendar .
flutter pub get
flutter run --dart-define=API_BASE_URL=https://YOUR-RENDER-SERVICE.onrender.com
```

The mobile client reads the same database as the web app. Do not run a separate backend/database for the mobile app.

## 4. Navigation and working sections

The web client opens on the **Weekly Schedule**. The permanent on-screen tabs are **Dashboard**, **Weekly Schedule** and **Upcoming Academic Activities**; Analytics is a separate protected tab. The hamburger menu contains Monthly Calendar, Modules, Facilitators, Examinations, Recurring Activities, WhatsApp & Communications, Activity History, Export & Sharing, and Settings. Settings is pinned at the bottom of the mobile drawer and separated from the main navigation on the web.

### Python Command Library for biomedical and health sciences

**Library** (bottom tab), **Menu → Python Library**, or the button in **Resources** opens the full 480-card biomedical command library as a dedicated full-screen page with a **← Back** control. A chapter index is shown at the top of the reference on desktop and mobile. The reference content, copy buttons, search and bundled simulated datasets are always available. The backend runner starts disabled (`?runner=off`) so the public calendar does not expose code execution; no backend URL is prefilled on public pages. To use it on a trusted machine, start the separate biomedical FastAPI service, enter its API base URL (for example `http://127.0.0.1:8000/api/v1`) in the runner panel and press **Enable runner**. Local execution uses `local_trusted`; it is not a security sandbox. Do not point it at a public unauthenticated service or use patient data. The three simulated CSV buttons and any uploaded file are loaded into the active kernel as `df`, `DATASET_ID` and `DATASET_NAME`.

The teaching timetable is Monday to Friday, 9–13 November 2026. The monthly calendar is a five-column weekday view (weekend dates are omitted). Saturday timetable and recurring-activity records are removed during database startup migration and new Saturday entries are rejected by the API. Sessions support user-selected start and end times, are sorted by start time, and cannot overlap on the same day. Timetable cells show the session/activity and its assigned lecturer; the exact interval appears in session details and schedule listings. Existing legacy slot records remain readable. Module lecturer assignments are selected from the Facilitators directory and are carried into scheduled sessions automatically. Analytics are restricted to HOD, Coordinator and Executive Dean roles.

The directory and activity sections use shared API collections backed by the same SQLite database. Authorised editors can add and remove facilitator, examination, recurring-activity and communication records; modules can be added; timetable sessions can be added from the web timetable editor and the Flutter weekly timetable. Export tools provide CSV/PDF/JSON options. The Flutter client copies JSON and CSV exports to the device clipboard.

Analytics are restricted by the API to HOD, Coordinator and Executive Dean roles; Rep and Staff do not receive analytics access. Session delivery mode (online / face-to-face / unspecified) is counted from timetable session records. Missed-session reporting is explicitly marked unavailable until attendance data is recorded; the app does not fabricate attendance statistics.

## 5. Access and activity attribution

- Viewing the calendar does not require sign-in.
- Editing is unlocked with the existing Rep or Staff password; optional HOD, Coordinator and Executive Dean passwords can be configured through environment variables.
- The activity feed attributes newly added timetable sessions, examinations, recurring activities and shared communications to **Rep**, **Staff**, **HOD**, **Coordinator** or **Executive Dean**.
- Routine edits, deletions, settings changes, app maintenance and upgrades are not displayed as user activity.
- Existing historical records are not retroactively attributed.

For Render, enter the existing values in the service environment variables. Do not commit passwords to GitHub.

## 6. Tests and code checks

From the project root, install the development test dependencies and run the backend tests:

```powershell
python -m pip install -r backend\requirements-dev.txt
python -m pytest -q
node --check frontend\js\app.js
node --check frontend\js\api-client.js
node --check frontend\service-worker.js
node tests\test_api_client_offline.js
```

The tests cover authentication, API access controls, shared data operations, backup restoration validation, service-worker delivery and offline write-queue behaviour.

## 7. Backups and operations checks

The server creates an initial SQLite snapshot when the backup folder is empty, then checks for a daily backup. It retains up to 30 snapshots. On Render, the snapshots are stored on the persistent disk.

After the first deployment, verify both:

1. The Render persistent disk contains a recent `mnh-calendar-YYYYMMDD-HHMMSS.sqlite3` file in `/var/data/backups/`.
2. `https://YOUR-RENDER-SERVICE.onrender.com/api/health` reports `backup_count` greater than zero and a non-null `last_backup`.

The JSON endpoint `/api/backup` is an application-data export for compatibility; the `.sqlite3` files are the actual database snapshots.

## 8. Configuration

| Variable | Purpose | Default |
|---|---|---|
| `PORT` | HTTP port supplied by host | `8000` |
| `MNH_DATA_DIR` | Parent directory for database and backups | Project root |
| `MNH_ENV` | Runtime security mode | `development` locally; `production` on Render |
| `MNH_ADMIN_PASSWORD` | Rep editing password | `rep` in local development only; required for production |
| `MNH_LECTURER_PASSWORD` | Staff editing password | `staff` in local development only; required for production |
| `MNH_HOD_PASSWORD` | Optional HOD password | Disabled |
| `MNH_COORDINATOR_PASSWORD` | Optional coordinator password | Disabled |
| `MNH_ED_PASSWORD` | Optional Executive Dean password | Disabled |
| `MNH_CORS_ORIGINS` | Comma-separated trusted web origins when hosting frontend separately | Same-origin only |
| `MNH_BACKUP_RETENTION` | Number of snapshots retained | `30` |

Do not expose the local development server directly to the public internet. Use Render HTTPS or another properly secured hosting provider for remote access.
