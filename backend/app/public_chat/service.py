"""Business logic for the native public chat.

The module keeps authorization, membership, rate limits, read state, and
notification preferences out of the router and the UI.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import HTTPException

from . import models, permissions, settings, store

_RATE_LOCK = threading.Lock()
_RATE_HITS: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_RATE_LIMITS = {
    "message": settings.RATE_MESSAGE_LIMIT,
    "upload": settings.RATE_UPLOAD_LIMIT,
    "report": settings.RATE_REPORT_LIMIT,
    "access": 10,
    "reaction": 60,
}


def check_rate(user: dict[str, Any], bucket: str) -> None:
    """Lenient per-user rolling-window limit for abuse prevention."""
    uid = str(user.get("id") or "") or "anonymous"
    key = (uid, bucket)
    now = time.monotonic()
    limit = _RATE_LIMITS.get(bucket, settings.RATE_MESSAGE_LIMIT)
    with _RATE_LOCK:
        hits = _RATE_HITS[key]
        while hits and now - hits[0] > settings.RATE_WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(429, "Too many requests. Please slow down and try again.")
        hits.append(now)


def participant_payload(participant: dict | None) -> dict | None:
    if not participant:
        return None
    return {
        "code": str(participant.get("code") or ""),
        "display_name": str(participant.get("display_name") or ""),
        "public_identity": str(participant.get("public_identity") or ""),
        "role": str(participant.get("role") or models.ROLE_MEMBER),
        "status": str(participant.get("status") or models.MEMBER_STATUS_ACTIVE),
    }


def public_participants() -> list[dict]:
    items = []
    for p in store._list(models.COL_PARTICIPANTS, 1000):
        if str(p.get("status") or models.MEMBER_STATUS_ACTIVE) != models.MEMBER_STATUS_ACTIVE:
            continue
        code = str(p.get("code") or "")
        if not store.CODE_RE.fullmatch(code):
            continue
        items.append(participant_payload(p))
    items.sort(key=lambda x: x["code"])
    return items


def _access_request(user: dict[str, Any]) -> dict | None:
    return store._read(models.COL_ACCESS_REQUESTS, str(user.get("id") or ""))


def access_status(user: dict[str, Any]) -> dict:
    request = _access_request(user)
    participant = store.get_participant(user, include_pending=True)
    if participant and str(participant.get("status") or "") == models.MEMBER_STATUS_SUSPENDED:
        return {"status": models.MEMBER_STATUS_SUSPENDED}
    if not request:
        return {"status": "active" if participant else "none"}
    return {
        "status": str(request.get("status") or "pending"),
        "requested_at": int(request.get("requested_at") or 0),
        "decided_at": int(request.get("decided_at") or 0),
        "decision": str(request.get("decision") or ""),
        "note": str(request.get("note") or ""),
    }


def join_chat(user: dict[str, Any], display_name: str = "", requested_code: str = "", request_new: bool = False) -> dict[str, Any]:
    check_rate(user, "access")
    code = str(requested_code or "").strip().upper()
    if not code and not request_new:
        existing = store.get_participant(user, include_pending=True)
        if not existing:
            raise HTTPException(400, "Enter your MNH ID or request a new one to join chat.")
    participant = store.ensure_participant(user, display_name, requested_code=code if code else "")
    now = store._now_s()
    uid = str(user.get("id") or "")
    request = _access_request(user)
    status = str(participant.get("status") or models.MEMBER_STATUS_ACTIVE)
    if status == models.MEMBER_STATUS_ACTIVE:
        if not request or str(request.get("status") or "") != "approved":
            store._write(models.COL_ACCESS_REQUESTS, uid, {
                "user_id": uid,
                "code": str(participant.get("code") or ""),
                "status": "approved",
                "decision": "automatic" if not settings.REQUIRE_ACCESS_APPROVAL else "moderator",
                "requested_at": int(request.get("requested_at") or now) if request else now,
                "decided_at": now,
                "note": "Access request approved.",
                "updated_at": now,
            })
    else:
        if not request or str(request.get("status") or "") == "approved":
            store._write(models.COL_ACCESS_REQUESTS, uid, {
                "user_id": uid,
                "code": str(participant.get("code") or ""),
                "status": "pending",
                "decision": "",
                "requested_at": now,
                "decided_at": 0,
                "note": "Awaiting moderator approval.",
                "updated_at": now,
            })
    return {
        "joined": status == models.MEMBER_STATUS_ACTIVE,
        "participant": participant_payload(participant),
        "access_request": access_status(user),
        "participants": public_participants(),
    }


def cancel_access_request(user: dict[str, Any]) -> dict[str, Any]:
    uid = str(user.get("id") or "")
    request = _access_request(user)
    if not request or str(request.get("status") or "") != "pending":
        raise HTTPException(400, "There is no pending access request to cancel.")
    participant = store.get_participant(user, include_pending=True)
    if participant and str(participant.get("status") or "") == models.MEMBER_STATUS_SUSPENDED:
        # Cancelling must not erase a moderator suspension and allow an instant
        # rejoin with a fresh participant record.
        raise HTTPException(403, "Your membership is suspended. Contact a moderator.")
    store._delete(models.COL_ACCESS_REQUESTS, uid)
    if participant:
        store._delete(models.COL_PARTICIPANTS, uid)
    return {"ok": True, "status": "cancelled"}


def decide_access_request(uid: str, approved: bool, moderator: dict[str, Any], note: str = "") -> dict[str, Any]:
    if not permissions.can_moderate(moderator):
        raise HTTPException(403, "Moderator access is required.")
    uid = str(uid or "")
    request = store._read(models.COL_ACCESS_REQUESTS, uid)
    if not request:
        raise HTTPException(404, "Access request not found.")
    status = str(request.get("status") or "")
    if status != "pending":
        raise HTTPException(400, "Only pending access requests can be decided.")
    now = store._now_s()
    request["status"] = "approved" if approved else "rejected"
    request["decision"] = "approved" if approved else "rejected"
    request["decided_by"] = str(moderator.get("id") or "")
    request["decided_at"] = now
    request["note"] = str(note or "")[:500]
    request["updated_at"] = now
    store._write(models.COL_ACCESS_REQUESTS, uid, request)
    participant = store._read(models.COL_PARTICIPANTS, uid)
    if participant:
        participant["status"] = models.MEMBER_STATUS_ACTIVE if approved else "suspended"
        participant["updated_at"] = now
        store._write(models.COL_PARTICIPANTS, uid, participant)
    return {"ok": True, "status": request["status"], "user_id": uid}


def pending_access_requests() -> list[dict]:
    out = []
    for request in store._list(models.COL_ACCESS_REQUESTS, 500):
        if str(request.get("status") or "") == "pending":
            out.append({
                "user_id": str(request.get("_id") or ""),
                "code": str(request.get("code") or ""),
                "requested_at": int(request.get("requested_at") or 0),
                "note": str(request.get("note") or ""),
            })
    out.sort(key=lambda x: x["requested_at"])
    return out


DEFAULT_PREFERENCES = {
    "replies": True,
    "mentions": True,
    "private": True,
    "access": True,
    "moderation": True,
}


def notification_preferences(user: dict[str, Any]) -> dict[str, bool]:
    uid = str(user.get("id") or "")
    stored = store._read(models.COL_PREFERENCES, uid) or {}
    values = stored.get("values") if isinstance(stored.get("values"), dict) else {}
    return {key: bool(values.get(key, DEFAULT_PREFERENCES[key])) for key in DEFAULT_PREFERENCES}


def set_notification_preferences(user: dict[str, Any], values: dict[str, Any]) -> dict[str, bool]:
    current = notification_preferences(user)
    for key in DEFAULT_PREFERENCES:
        if key in values:
            current[key] = bool(values[key])
    store._write(models.COL_PREFERENCES, str(user.get("id") or ""), {
        "user_id": str(user.get("id") or ""),
        "values": current,
        "updated_at": store._now_s(),
    })
    return current


def blocked_codes(user: dict[str, Any]) -> set[str]:
    doc = store._read(models.COL_BLOCKS, str(user.get("id") or "")) or {}
    values = doc.get("blocked_codes") if isinstance(doc.get("blocked_codes"), list) else []
    return {str(code) for code in values if store.CODE_RE.fullmatch(str(code))}


def muted_codes(user: dict[str, Any]) -> set[str]:
    doc = store._read(models.COL_BLOCKS, str(user.get("id") or "")) or {}
    values = doc.get("muted_codes") if isinstance(doc.get("muted_codes"), list) else []
    return {str(code) for code in values if store.CODE_RE.fullmatch(str(code))}


def mark_read(user: dict[str, Any], up_to_ms: int | None = None) -> dict[str, Any]:
    participant = store.require_participant(user)
    now = store._now()
    stamp = max(0, int(up_to_ms or now))
    store._write(models.COL_READ_STATE, str(user.get("id") or ""), {
        "user_id": str(user.get("id") or ""),
        "code": str(participant.get("code") or ""),
        "last_read_at": stamp,
        "updated_at": now,
    })
    return {"ok": True, "last_read_at": stamp}


def unread_summary(user: dict[str, Any]) -> dict[str, int]:
    participant = store.require_participant(user)
    doc = store._read(models.COL_READ_STATE, str(user.get("id") or "")) or {}
    last_read = int(doc.get("last_read_at") or 0)
    messages = store.list_messages(participant, limit=300, blocked_codes=blocked_codes(user))
    unread = [m for m in messages if int(m.get("created_at") or 0) > last_read and not m.get("mine")]
    return {
        "unread": len(unread),
        "private": sum(1 for m in unread if m.get("kind") == "private"),
        "mentions": sum(1 for m in unread if participant.get("code") in (m.get("mentions") or [])),
    }
