"""Password roles and in-memory signed-session registry."""
import hashlib
import os
import secrets
import time
from threading import RLock

from app.config import SESSION_SECONDS

SESSIONS = {}
SESSION_LOCK = RLock()


def role_for_password(password: str):
    """Resolve an editing role without exposing development passwords in production."""
    production = os.getenv("MNH_ENV", "development").strip().lower() == "production"
    configured = (
        ("administrator", os.getenv("MNH_ADMIN_PASSWORD", "" if production else "rep")),
        ("hod", os.getenv("MNH_HOD_PASSWORD", "")),
        ("coordinator", os.getenv("MNH_COORDINATOR_PASSWORD", "")),
        ("executive_dean", os.getenv("MNH_ED_PASSWORD", "")),
        ("lecturer", os.getenv("MNH_LECTURER_PASSWORD", "" if production else "staff")),
    )

    for role, expected in configured:
        if expected and secrets.compare_digest(password, expected):
            return role
    return None


def create_session(role: str):
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    with SESSION_LOCK:
        SESSIONS[digest] = {"role": role, "expires": time.time() + SESSION_SECONDS}
    return token


def get_session(token):
    if not token:
        return None

    digest = hashlib.sha256(token.encode()).hexdigest()
    with SESSION_LOCK:
        session = SESSIONS.get(digest)
        if not session or session["expires"] < time.time():
            SESSIONS.pop(digest, None)
            return None

        session["expires"] = time.time() + SESSION_SECONDS
        return dict(session)


def delete_session(token):
    if not token:
        return

    digest = hashlib.sha256(token.encode()).hexdigest()
    with SESSION_LOCK:
        SESSIONS.pop(digest, None)
