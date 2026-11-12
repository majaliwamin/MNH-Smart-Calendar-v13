
"""FastAPI application entry point for the MNH Calendar."""
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import (
    PROJECT_ROOT,
    CORS_ORIGINS,
    BUILD_ID,
    APP_VERSION,
    ensure_directories,
)
from app.database.connection import connect, is_postgres
from app.api.routes import router
from app.services.backup_service import (
    backup_worker,
    make_backup,
    list_backups,
)

FRONTEND_DIR = PROJECT_ROOT / "frontend"
STOP_BACKUPS = threading.Event()
BACKUP_THREAD = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global BACKUP_THREAD

    ensure_directories()

    db = connect()
    db.close()

    # Local SQLite deployments retain automatic file snapshots.
    # PostgreSQL uses the JSON backup and restore API instead.
    if not is_postgres():
        if not list_backups():
            try:
                make_backup()
            except Exception as exc:
                print(
                    f"Initial database backup warning: {exc}",
                    flush=True,
                )

        STOP_BACKUPS.clear()
        BACKUP_THREAD = threading.Thread(
            target=backup_worker,
            args=(STOP_BACKUPS,),
            daemon=True,
            name="mnh-daily-backup",
        )
        BACKUP_THREAD.start()

    yield

    if BACKUP_THREAD and BACKUP_THREAD.is_alive():
        STOP_BACKUPS.set()
        BACKUP_THREAD.join(timeout=2)


app = FastAPI(
    title="MNH Calendar API",
    version=APP_VERSION,
    lifespan=lifespan,
    description="Shared academic calendar API for web and Flutter clients.",
)

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = (
        "no-cache"
        if request.url.path == "/service-worker.js"
        else "no-store"
    )
    response.headers["X-Frame-Options"] = "SAMEORIGIN"

    return response


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)},
        headers=exc.headers,
    )


app.include_router(router)


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount(
    "/css",
    StaticFiles(directory=str(FRONTEND_DIR / "css")),
    name="css",
)

app.mount(
    "/js",
    StaticFiles(directory=str(FRONTEND_DIR / "js")),
    name="js",
)


def build_info() -> dict:
    """Identify the running application build."""
    info = {
        "ok": True,
        "build": BUILD_ID,
        "version": APP_VERSION,
    }

    if os.getenv("MNH_ENV", "").lower() != "production":
        info.update({
            "pid": os.getpid(),
            "projectRoot": str(PROJECT_ROOT),
        })

    return info


@app.get("/api/health/ready", include_in_schema=False)
@app.get("/health", include_in_schema=False)
@app.get("/api/build", include_in_schema=False)
async def readiness():
    """Health and build identity for hosting probes and frontend checks."""
    return build_info()


@app.get("/service-worker.js", include_in_schema=False)
async def service_worker():
    return FileResponse(
        FRONTEND_DIR / "service-worker.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )
