#!/usr/bin/env python3
"""Export public, read-only JSON snapshots of the MNH Calendar for the static site.

The site is hosted on GitHub Pages with no backend. This script imports the
existing FastAPI app and calls its GET endpoints through FastAPI's TestClient,
so no server is started and no database file is copied.

Only endpoints that are both (a) needed to render the read-only views and
(b) free of private personal data are exported. Endpoints that expose chat
messages, participants, contacts/phone numbers, login identities, password
hashes, exam submissions, audit logs, or full database backups are deliberately
excluded — see EXCLUDED_ENDPOINTS below.

Usage (PowerShell):
    & "C:\\Users\\AMINILOGY\\AppData\\Local\\Temp\\opencode\\backend312\\Scripts\\python.exe" tools/export_static_data.py

Lifespan is replaced with a no-op so the export cannot start backup/reminder
workers, create a database backup, or otherwise write to the live database.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
DATA_DIR = PROJECT_ROOT / "site" / "data"

# Never route requests through a local cloud mirror during an export.
os.environ["MNH_CLOUD_MIRROR_URL"] = ""

sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.routes import ALLOWED_COLLECTIONS  # noqa: E402
from app.main import app  # noqa: E402


@asynccontextmanager
async def _no_lifespan(_app):
    """GET snapshots must not start background workers or create backups."""
    yield


app.router.lifespan_context = _no_lifespan

# endpoint -> relative filename under site/data/
ENDPOINTS: dict[str, str] = {
    "/api/ping": "ping.json",
    "/api/session": "session.json",
    "/api/health": "health.json",
    "/api/export/modules": "export-modules.json",
    "/api/analytics": "analytics.json",
    "/api/history": "history.json",
}
for _collection in sorted(ALLOWED_COLLECTIONS):
    ENDPOINTS[f"/api/col/{_collection}"] = f"col-{_collection}.json"

# GET endpoints the frontend calls that are NOT exported, and why:
EXCLUDED_ENDPOINTS = {
    "/api/backup": "full database dump (can include private collections)",
    "/api/export": "full document dump",
    "/api/export/timetable.xlsx": "binary, generated client-side instead",
    "/api/export/timetable.pdf": "binary, generated client-side instead",
    "/api/reminders": "phone numbers and delivery credentials",
    "/api/comm/*": "contacts, phone numbers, drafts, call records",
    "/api/public-chat/*": "private messages and participant identities",
    "/api/class-rep/*": "conversations, memories and login identity",
    "/api/ai/*": "diagnostics and model performance data",
    "/api/exams/*": "candidate submissions, audit trail and logged-in identity",
    "/api/resources/files/*": "uploaded private files",
    "/health, /api/build, /service-worker.js": "deployment probes, not page data",
}


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)
    written: list[tuple[str, int]] = []
    failures: list[str] = []

    for path, filename in ENDPOINTS.items():
        try:
            response = client.get(path)
        except Exception as error:  # noqa: BLE001 - report and continue
            failures.append(f"{path}: {type(error).__name__}: {error}")
            continue
        if response.status_code != 200:
            failures.append(f"{path}: HTTP {response.status_code} {response.text[:160]}")
            continue
        try:
            payload = response.json()
        except Exception as error:  # noqa: BLE001
            failures.append(f"{path}: non-JSON response ({error})")
            continue
        target = DATA_DIR / filename
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append((filename, target.stat().st_size))

    print(f"Exported {len(written)} snapshots to {DATA_DIR}")
    for filename, size in written:
        print(f"  {filename:<28} {size:>9,} bytes")
    if failures:
        print("\nFailed endpoints:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
