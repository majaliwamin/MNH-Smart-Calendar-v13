"""Configuration for the native MNH public chat feature.

All values are environment-backed so deployments can tune retention and limits
without code changes. Defaults preserve the established 7-day public retention
policy and the existing Africa/Blantyre application timezone.
"""
from __future__ import annotations

import os


def _int_env(name: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, "").strip() or default)
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


TIMEZONE = os.getenv("MNH_TIMEZONE", "Africa/Blantyre").strip() or "Africa/Blantyre"

RETENTION_DAYS = _int_env("MNH_PUBLIC_CHAT_RETENTION_DAYS", 7, 1, 365)
RETENTION_SECONDS = RETENTION_DAYS * 24 * 60 * 60

# Private replies are deliberately excluded from the public sweep by default.
# Set MNH_PUBLIC_CHAT_EXPIRE_PRIVATE=1 if the same retention policy should apply.
EXPIRE_PRIVATE_MESSAGES = _bool_env("MNH_PUBLIC_CHAT_EXPIRE_PRIVATE", False)

CLEANUP_LOG_RETENTION_DAYS = _int_env("MNH_PUBLIC_CHAT_CLEANUP_LOG_DAYS", 30, 1, 365)

# By default joining is self-service and immediately active, matching the
# established public chat. Deployments that require moderator approval can set
# MNH_PUBLIC_CHAT_REQUIRE_APPROVAL=1.
REQUIRE_ACCESS_APPROVAL = _bool_env("MNH_PUBLIC_CHAT_REQUIRE_APPROVAL", False)

MAX_MESSAGE_LENGTH = 4000
MAX_DISPLAY_NAME_LENGTH = 80
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # up to ~40 min compressed voice note
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
MAX_MENTIONS = 20

ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".pdf", ".txt", ".csv", ".doc", ".docx", ".xls", ".xlsx",
}
ALLOWED_ATTACHMENT_MIME_PREFIXES = ("image/", "text/", "application/pdf", "application/msword",
                                    "application/vnd.openxmlformats-officedocument",
                                    "application/vnd.ms-excel")

# Lenient anti-spam limits; normal conversation is never affected.
RATE_MESSAGE_LIMIT = _int_env("MNH_PUBLIC_CHAT_RATE_MESSAGES", 30, 1, 600)
RATE_UPLOAD_LIMIT = _int_env("MNH_PUBLIC_CHAT_RATE_UPLOADS", 10, 1, 300)
RATE_REPORT_LIMIT = _int_env("MNH_PUBLIC_CHAT_RATE_REPORTS", 10, 1, 300)
RATE_WINDOW_SECONDS = 60

ALLOWED_REACTIONS = {"👍", "❤️", "😂", "😮", "😢", "🙏", "🎉", "👏"}
REPORT_CATEGORIES = {
    "spam", "harassment", "abuse", "inappropriate", "misinformation", "other"
}
ALLOWED_REPORT_CATEGORIES = frozenset(REPORT_CATEGORIES)
