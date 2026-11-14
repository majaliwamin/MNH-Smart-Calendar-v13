"""Environment-backed application configuration."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("MNH_DATA_DIR", str(PROJECT_ROOT))).resolve()
DATABASE_DIR = DATA_DIR / "database"
BACKUP_DIR = DATA_DIR / "backups"
DATABASE_PATH = DATABASE_DIR / "calendar.db"
BACKUP_INTERVAL_SECONDS = max(60, int(os.getenv("MNH_BACKUP_INTERVAL_SECONDS", "86400")))
BACKUP_RETENTION = max(1, int(os.getenv("MNH_BACKUP_RETENTION", "30")))
SESSION_SECONDS = max(300, int(os.getenv("MNH_SESSION_SECONDS", str(12 * 60 * 60))))
CORS_ORIGINS = [x.strip() for x in os.getenv("MNH_CORS_ORIGINS", "").split(",") if x.strip()]
COOKIE_SECURE = os.getenv("MNH_COOKIE_SECURE", "auto").lower()

# ---- Server binding -------------------------------------------------------
# Local development: 127.0.0.1:8000 (set MNH_LAN=1 to expose on the LAN).
# Hosting platforms (Render etc.) provide PORT and need 0.0.0.0.
# MNH_HOST / MNH_PORT override everything; PORT is honoured when MNH_PORT is unset.
BUILD_ID = "2026.11.14-v14.9"
APP_VERSION = "2.1.0"

# ---- WhatsApp reminders ---------------------------------------------------
# Credentials are environment-only (MNH_WHATSAPP_TOKEN / MNH_WHATSAPP_PHONE_ID).
WHATSAPP_SENDER_NAME = os.getenv("MNH_WHATSAPP_SENDER_NAME", "Maternal & Neonatal Health Smart Time Table")
TIMEZONE = os.getenv("MNH_TIMEZONE", "Africa/Blantyre")
REMINDER_INTERVAL_SECONDS = max(10, int(os.getenv("MNH_REMINDER_INTERVAL_SECONDS", "30")))

# ---- Communications Centre (WhatsApp Click-to-Chat + Asterisk ARI) ----------
# Secrets are environment-only; nothing below is a credential.
AI_API_BASE = os.getenv("MNH_AI_BASE_URL", "https://api.openai.com/v1")
ARI_CALL_WINDOW_START = os.getenv("MNH_CALL_WINDOW_START", "08:00")
ARI_CALL_WINDOW_END = os.getenv("MNH_CALL_WINDOW_END", "18:00")


def server_host() -> str:
    explicit = os.getenv("MNH_HOST", "").strip()
    if explicit:
        return explicit
    if os.getenv("MNH_LAN", "").lower() in ("1", "true", "yes") or os.getenv("MNH_ENV", "").lower() == "production" or os.getenv("RENDER"):
        return "0.0.0.0"
    return "127.0.0.1"


def server_port() -> int:
    for name in ("MNH_PORT", "PORT"):
        raw = os.getenv(name, "").strip()
        if raw.isdigit() and 0 < int(raw) < 65536:
            return int(raw)
    return 8000


def ensure_directories():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
