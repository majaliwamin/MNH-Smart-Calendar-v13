"""FastAPI application entry point for the MNH Calendar."""
import threading
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.config import PROJECT_ROOT, CORS_ORIGINS, BUILD_ID, APP_VERSION, ensure_directories
from app.database.connection import connect, database
from app.api.routes import router
from app.api.comm_routes import router as comm_router
from app.class_rep.routes import router as class_rep_router
from app.class_rep.whiteboard import router as class_rep_whiteboard_router
from app.ai_intelligence.routes import router as ai_router
from app.livekit.routes import router as livekit_router
from app.public_chat.routes import router as public_chat_router
from app.ai_intelligence import evaluation as ai_evaluation
from app.services.backup_service import backup_worker, make_backup, list_backups
from app.services.reminders import reminder_worker
from app.services import comm_service
from app.config import REMINDER_INTERVAL_SECONDS

FRONTEND_DIR = PROJECT_ROOT / "frontend"
STOP_BACKUPS = threading.Event()
BACKUP_THREAD = None
STOP_REMINDERS = threading.Event()
REMINDER_THREAD = None
STOP_COMM = threading.Event()
COMM_THREAD = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global BACKUP_THREAD, REMINDER_THREAD, COMM_THREAD
    ensure_directories()
    db = connect(); db.close()
    # Recurring activities are user-managed records. Do not recreate deleted rows at startup.
    # Guarantee an initial snapshot on first startup; later snapshots are daily.
    if not list_backups():
        try:
            make_backup()
        except Exception as exc:
            print(f"Initial database backup warning: {exc}", flush=True)
    STOP_BACKUPS.clear()
    BACKUP_THREAD = threading.Thread(target=backup_worker, args=(STOP_BACKUPS,),
                                     daemon=True, name="mnh-daily-backup")
    BACKUP_THREAD.start()
    # WhatsApp reminders: checks every few seconds and messages everyone a set number of
    # minutes before each session. Silent no-op until credentials and numbers are set.
    STOP_REMINDERS.clear()
    REMINDER_THREAD = threading.Thread(target=reminder_worker, args=(STOP_REMINDERS, REMINDER_INTERVAL_SECONDS),
                                       daemon=True, name="mnh-whatsapp-reminders")
    REMINDER_THREAD.start()
    # Communications Centre worker: runs due scheduled jobs (creates DRAFTS only —
    # nothing is sent automatically) and syncs live ARI call states. No-op when
    # nothing is scheduled and Asterisk is not configured.
    def _comm_worker(stop_event: threading.Event):
        while not stop_event.wait(30):
            try:
                comm_service.run_due_jobs()
                from app.class_rep.memory import tick_reminders
                tick_reminders()
                try:
                    from app.public_chat.routes import run_retention_cleanup
                    run_retention_cleanup()
                except Exception as chat_error:
                    print(f"Public chat retention warning: {chat_error}", flush=True)
                from app.services import ari_service, ai_trigger
                if ai_trigger.enabled():
                    outcome = ai_trigger.auto_check()
                    if outcome.get("changes") or outcome.get("errors"):
                        print(f"AI trigger: {outcome}", flush=True)
                if ari_service.configured():
                    ari_service.sync_live_calls()
                # Once per calendar day, test the live timetable pipeline and
                # persist a trend. Failures here never affect timetable service.
                try:
                    ai_evaluation.maybe_run_daily()
                except Exception as ai_error:
                    print(f"AI daily evaluation warning: {ai_error}", flush=True)
            except Exception as error:
                print(f"Communications worker warning: {error}", flush=True)

    STOP_COMM.clear()
    COMM_THREAD = threading.Thread(target=_comm_worker, args=(STOP_COMM,),
                                   daemon=True, name="mnh-communications")
    COMM_THREAD.start()
    yield
    STOP_BACKUPS.set()
    STOP_REMINDERS.set()
    if BACKUP_THREAD and BACKUP_THREAD.is_alive():
        BACKUP_THREAD.join(timeout=2)
    if REMINDER_THREAD and REMINDER_THREAD.is_alive():
        REMINDER_THREAD.join(timeout=3)
    STOP_COMM.set()
    if COMM_THREAD and COMM_THREAD.is_alive():
        COMM_THREAD.join(timeout=3)


app = FastAPI(title="MNH Calendar API", version=APP_VERSION, lifespan=lifespan,
              description="Shared academic calendar API for web and Flutter clients.")
if CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
                       allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                       allow_headers=["Content-Type", "Authorization", "X-CARA-Analytics-Password", "X-MNH-AI-Admin-Token"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = (
        "no-cache" if request.url.path == "/service-worker.js" else "no-store"
    )
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # Explicitly allow chat voice notes and legacy export cleanup in this app's
    # own documents. The microphone still requires the browser's normal
    # click-initiated permission prompt; this only prevents a policy from
    # blocking that prompt or logging an unload violation.
    response.headers["Permissions-Policy"] = "microphone=(self), unload=*"
    # Every response identifies the exact build that produced it. A stale PWA
    # can compare this with its own build marker and recover automatically.
    response.headers["X-MNH-Build"] = BUILD_ID
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    # FastAPI's default 422 body is a list of objects. Older chat clients stringify
    # that list as "[object Object]", so return one readable sentence instead.
    parts = []
    for item in exc.errors():
        location = [str(part) for part in item.get("loc", []) if part not in ("body", "query", "path")]
        field = ".".join(location) or "request"
        parts.append(field + ": " + str(item.get("msg") or "Invalid value"))
    detail = "Invalid request. " + "; ".join(parts[:4])
    if len(parts) > 4:
        detail += " (and " + str(len(parts) - 4) + " more)"
    detail = detail[:500]
    return JSONResponse(status_code=422, content={"detail": detail, "error": detail})


app.include_router(router)
app.include_router(comm_router)
app.include_router(class_rep_router)
app.include_router(class_rep_whiteboard_router)
app.include_router(livekit_router)
app.include_router(ai_router)
app.include_router(public_chat_router)


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    # Serve the same vector icon for the conventional browser request and explicit SVG link.
    return FileResponse(FRONTEND_DIR / "favicon.svg", media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/manifest.json", include_in_schema=False)
async def manifest():
    # Web app manifest: required for PWA installability (and beforeinstallprompt).
    return FileResponse(FRONTEND_DIR / "manifest.json", media_type="application/manifest+json",
                        headers={"Cache-Control": "no-cache"})


@app.get("/install-help.html", include_in_schema=False)
async def install_help():
    return FileResponse(FRONTEND_DIR / "install-help.html",
                        headers={"Cache-Control": "public, max-age=3600"})


app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
# Math, Markdown, sanitisation, chart, export and font packages are vendored locally
# so CRARA renders correctly on mobile networks and never asks third-party hosts for storage.
app.mount("/vendor", StaticFiles(directory=str(FRONTEND_DIR / "vendor")), name="vendor")
app.mount("/fonts", StaticFiles(directory=str(FRONTEND_DIR / "fonts")), name="fonts")
app.mount("/icons", StaticFiles(directory=str(FRONTEND_DIR / "icons")), name="icons")
app.mount("/resources", StaticFiles(directory=str(FRONTEND_DIR / "resources")), name="resources")


def build_info() -> dict:
    """Identifies exactly which copy of the project is answering (used to detect stale servers/caches)."""
    info = {"ok": True, "build": BUILD_ID, "version": APP_VERSION}
    if os.getenv("MNH_ENV", "").lower() != "production":
        info.update({"pid": os.getpid(), "projectRoot": str(PROJECT_ROOT)})
    return info


@app.get("/api/health/ready", include_in_schema=False)
@app.get("/health", include_in_schema=False)
@app.get("/api/build", include_in_schema=False)
async def readiness():
    """Health + build identity for local checks, hosting probes and the frontend stale-copy check."""
    return build_info()


@app.get("/service-worker.js", include_in_schema=False)
async def service_worker():
    return FileResponse(
        FRONTEND_DIR / "service-worker.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )
