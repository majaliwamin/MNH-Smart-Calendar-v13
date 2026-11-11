# Backend architecture

FastAPI application package:

- `app/main.py`: application assembly, lifespan, middleware, static web serving.
- `app/api/routes.py`: HTTP API endpoints shared by web and Flutter.
- `app/database/connection.py`: SQLite schema, seed data, transactions.
- `app/services/authentication.py`: Rep/Staff and optional HOD/coordinator sessions.
- `app/services/audit_service.py`: activity attribution for new sessions and activities.
- `app/services/backup_service.py`: consistent daily SQLite snapshots and retention.
- `app/config.py`: environment-based paths and settings.
- `run.py`: local development entry point.

The API is intentionally kept in one deployable service with the web frontend so browsers can use same-origin requests and secure cookies. Flutter uses the same API URL.

## Local startup (Windows)

From the project root, install dependencies once and start the server:

```powershell
python -m pip install -r backend\requirements.txt
python backend\run.py
```

The `run.ps1` helper in the project root creates and reuses a local `.venv` automatically. The application is served at `http://127.0.0.1:8000/`, API documentation at `/docs`, and the health endpoint at `/health`.

The timetable supports Monday–Friday sessions only. Custom sessions use `dayIndex`, `startTime` and `endTime`; the API validates weekdays, time ordering and overlaps.
