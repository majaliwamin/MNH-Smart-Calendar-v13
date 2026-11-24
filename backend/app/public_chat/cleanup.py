"""Idempotent weekly-retention cleanup with audit logging.

Deletion is restricted to public-chat message documents and chat-owned media
files. Members, access records, moderation history, and all unrelated calendar
data are deliberately preserved.
"""
from __future__ import annotations

import time
import uuid

from . import models, settings, store


def run_cleanup(now_s: int | None = None, expire_private: bool | None = None) -> dict:
    now_s = int(now_s or time.time())
    result = store.cleanup_public_retention(now_s=now_s, expire_private=expire_private)
    result["timezone"] = settings.TIMEZONE
    result["retention_days"] = settings.RETENTION_DAYS

    changed = any(result.get(key) for key in ("deleted_messages", "deleted_files", "deleted_reactions"))
    recent = store._list(models.COL_CLEANUP_LOG, 5)
    last = recent[0] if recent else {}
    one_hour_ago = now_s - 3600
    should_log = changed or int(last.get("finished_at") or 0) < one_hour_ago

    if should_log:
        log_id = uuid.uuid4().hex
        store._write(models.COL_CLEANUP_LOG, log_id, {
            "id": log_id,
            "started_at": now_s,
            "finished_at": int(time.time()),
            "timezone": settings.TIMEZONE,
            "result": result,
            "status": "ok",
        })

    cutoff = now_s - settings.CLEANUP_LOG_RETENTION_DAYS * 24 * 60 * 60
    for doc in store._list(models.COL_CLEANUP_LOG, 200):
        if int(doc.get("finished_at") or 0) < cutoff:
            store._delete(models.COL_CLEANUP_LOG, str(doc.get("_id") or doc.get("id") or ""))
    return result


def cleanup_status() -> dict:
    entries = []
    for doc in store._list(models.COL_CLEANUP_LOG, 20):
        entries.append({
            "id": str(doc.get("id") or ""),
            "finished_at": int(doc.get("finished_at") or 0),
            "status": str(doc.get("status") or "ok"),
            "result": doc.get("result") if isinstance(doc.get("result"), dict) else {},
        })
    entries.sort(key=lambda x: x["finished_at"], reverse=True)
    return {
        "retention_days": settings.RETENTION_DAYS,
        "timezone": settings.TIMEZONE,
        "expire_private": settings.EXPIRE_PRIVATE_MESSAGES,
        "recent_runs": entries,
    }
