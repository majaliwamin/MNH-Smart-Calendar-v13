"""Persistence and serialization helpers for the native public chat.

The app uses a shared SQLite ``docs`` collection store (with a Postgres
adapter), so chat data needs no new migration framework or external database.
All message visibility decisions live here and are reused by REST and WS paths.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from app.config import DATA_DIR, ensure_directories
from app.database.connection import database

from . import permissions, settings
from .models import (
    COL_CODE_RESERVATIONS,
    COL_MESSAGES,
    COL_PARTICIPANTS,
    COL_REACTIONS,
    COL_READ_STATE,
    MEMBER_STATUS_ACTIVE,
    MEMBER_STATUS_PENDING,
    MEMBER_STATUS_SUSPENDED,
    PUBLIC_RETENTION_SECONDS,
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_MODERATOR,
)

COL_MEDIA_BLOBS = "public_chat_media_blobs"

CODE_PREFIX = "MNH-"
CODE_RE = re.compile(r"^MNH-\d{4}$")
MEDIA_DIR = DATA_DIR / "public_chat_media"
MAX_AUDIO_BYTES = settings.MAX_AUDIO_BYTES
MAX_AUDIO_UPLOAD_BYTES = 60 * 1024 * 1024  # raw upload; compressed output must fit MAX_AUDIO_BYTES
MAX_VOICE_DURATION_MS = 40 * 60 * 1000
MAX_ATTACHMENT_BYTES = settings.MAX_ATTACHMENT_BYTES
ALLOWED_AUDIO = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "video/webm": ".webm",  # MediaRecorder often reports video/webm for audio-only
}
# Preferred compressed delivery format for voice notes. WebM/Opus keeps quality high at low bitrate.
VOICE_TARGET_MIME = "audio/webm"
VOICE_TARGET_EXT = ".webm"
VOICE_COMPRESS_BITRATE = "24k"
ALLOWED_ATTACHMENTS = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".pdf": "application/pdf",
    ".txt": "text/plain", ".csv": "text/csv",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _now() -> int:
    return int(__import__("time").time() * 1000)


def _now_s() -> int:
    return int(__import__("time").time())


def _json_load(value: str, fallback):
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _read(col: str, item_id: str) -> dict | None:
    with database() as db:
        row = db.execute("SELECT data FROM docs WHERE col=? AND id=?", (col, item_id)).fetchone()
    if not row:
        return None
    data = _json_load(row["data"], None)
    return data if isinstance(data, dict) else None


def _write(col: str, item_id: str, value: dict) -> None:
    with database() as db:
        db.execute(
            "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (col, item_id, json.dumps(value, ensure_ascii=False), _now()),
        )


def _delete(col: str, item_id: str) -> bool:
    with database() as db:
        cur = db.execute("DELETE FROM docs WHERE col=? AND id=?", (col, item_id))
        return cur.rowcount > 0


def _list(col: str, limit: int = 500) -> list[dict]:
    with database() as db:
        rows = db.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? ORDER BY updated_at DESC LIMIT ?",
            (col, max(1, min(int(limit), 2000))),
        ).fetchall()
    out = []
    for row in rows:
        item = _json_load(row["data"], None)
        if isinstance(item, dict):
            item["_id"] = str(row["id"])
            item["_updated_at"] = int(row["updated_at"] or 0)
            out.append(item)
    return out


def _participant_id(user: dict[str, Any]) -> str:
    uid = str(user.get("id") or "").strip()
    if not uid:
        raise HTTPException(401, "Authentication required.")
    return uid


def _display_name(user: dict[str, Any], requested: str = "") -> str:
    name = str(requested or user.get("name") or "").strip()
    name = re.sub(r"\s+", " ", name)[:settings.MAX_DISPLAY_NAME_LENGTH]
    if not name:
        email = str(user.get("email") or "").strip()
        if email and "@" in email:
            name = email.split("@", 1)[0][:settings.MAX_DISPLAY_NAME_LENGTH]
    return name or "Participant"


def _public_identity(code: str, name: str) -> str:
    clean = re.sub(r"\s+", " ", str(name or "")).strip()[:settings.MAX_DISPLAY_NAME_LENGTH] or "Participant"
    return f"{code} — {clean}"


def _member_role(user: dict[str, Any]) -> str:
    role = str(user.get("role") or "").strip().lower()
    if role == "administrator":
        return ROLE_ADMIN
    if permissions.is_moderator(user):
        return ROLE_MODERATOR
    return ROLE_MEMBER


def _active_codes(exclude_user_id: str = "") -> set[str]:
    codes = set()
    for item in _list(COL_PARTICIPANTS, 5000):
        if exclude_user_id and str(item.get("user_id") or "") == exclude_user_id:
            continue
        if str(item.get("status") or MEMBER_STATUS_ACTIVE) not in {MEMBER_STATUS_ACTIVE, MEMBER_STATUS_PENDING}:
            continue
        code = str(item.get("code") or "")
        if CODE_RE.fullmatch(code):
            codes.add(code)
    return codes


def _reserved_codes(exclude_user_id: str = "") -> set[str]:
    """Codes already claimed by a reservation, optionally ignoring one owner."""
    with database() as db:
        rows = db.execute("SELECT id,data FROM docs WHERE col=?", (COL_CODE_RESERVATIONS,)).fetchall()
    used = set()
    for row in rows:
        code = str(row["id"])
        if not CODE_RE.fullmatch(code):
            continue
        reservation = _json_load(row["data"], {}) or {}
        if exclude_user_id and str(reservation.get("user_id") or "") == exclude_user_id:
            continue
        used.add(code)
    return used


def _reserved_code_for_user(user_id: str) -> str:
    """Reuse a reservation if a write was interrupted after claiming a code."""
    if not user_id:
        return ""
    with database() as db:
        rows = db.execute("SELECT id,data FROM docs WHERE col=?", (COL_CODE_RESERVATIONS,)).fetchall()
    for row in rows:
        code = str(row["id"])
        if not CODE_RE.fullmatch(code):
            continue
        reservation = _json_load(row["data"], {}) or {}
        if str(reservation.get("user_id") or "") == user_id:
            return code
    return ""


def _reserve_code(code: str, user_id: str) -> bool:
    """Claim a code with a primary-key insert shared by SQLite and PostgreSQL."""
    with database() as db:
        cur = db.execute(
            "INSERT OR IGNORE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (COL_CODE_RESERVATIONS, code, json.dumps(
                {"code": code, "user_id": user_id, "reserved_at": _now_s()},
                ensure_ascii=False,
            ), _now()),
        )
        return cur.rowcount > 0


def generate_code(exclude_user_id: str = "") -> str:
    """Return a random, non-sequential MNH-XXXX code that is still free."""
    used = _active_codes(exclude_user_id) | _reserved_codes(exclude_user_id)
    available = [f"{CODE_PREFIX}{i:04d}" for i in range(10000) if f"{CODE_PREFIX}{i:04d}" not in used]
    if not available:
        raise HTTPException(409, "No public chat identification codes are currently available.")
    return secrets.choice(available)


def _write_participant_if_code_free(user_id: str, code: str, doc: dict) -> bool:
    """Write the participant only if no other member already holds ``code``."""
    with database() as db:
        rows = db.execute("SELECT id,data FROM docs WHERE col=?", (COL_PARTICIPANTS,)).fetchall()
        for row in rows:
            if str(row["id"]) == user_id:
                continue
            other = _json_load(row["data"], {}) or {}
            if str(other.get("code") or "") == code and str(other.get("status") or MEMBER_STATUS_ACTIVE) != "suspended":
                return False
        db.execute(
            "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (COL_PARTICIPANTS, user_id, json.dumps(doc, ensure_ascii=False), _now()),
        )
        return True


def _claimable_code(user: dict[str, Any], requested_code: str) -> str:
    code = str(requested_code or "").strip().upper()
    if not code:
        return ""
    if not CODE_RE.fullmatch(code):
        raise HTTPException(400, "Enter a valid chat ID in the format MNH-1234.")
    uid = _participant_id(user)
    email = str(user.get("email") or "").strip().lower()
    # Same user already reserved/owns it.
    if _reserved_code_for_user(uid) == code:
        return code
    existing_owner = participant_by_code(code, include_inactive=True)
    if existing_owner:
        owner_uid = str(existing_owner.get("user_id") or "")
        owner_email = str(existing_owner.get("email") or "").strip().lower()
        if owner_uid == uid:
            return code
        # Allow reclaim only when authenticated account email matches the record owner.
        if email and owner_email and email == owner_email and owner_uid != uid:
            # Rebind code by moving reservation to current user; keep existing participant record as-is.
            # We only allow if the other user record is not active on a different identity? 
            # To avoid hijack, require same verified account email.
            _reserve_code(code, uid)
            return code
        raise HTTPException(409, "This ID is already assigned. Request a new ID if you do not have one.")
    # Code is unassigned; allow claiming only if not reserved by another user.
    reserved = _reserved_codes(exclude_user_id=uid)
    if code in reserved:
        raise HTTPException(409, "This ID is currently reserved. Request a new ID if you do not have one.")
    return code


def ensure_participant(user: dict[str, Any], display_name: str = "", status: str | None = None, requested_code: str = "") -> dict:
    uid = _participant_id(user)
    now = _now_s()
    desired_status = status or (MEMBER_STATUS_PENDING if settings.REQUIRE_ACCESS_APPROVAL else MEMBER_STATUS_ACTIVE)
    if desired_status not in {MEMBER_STATUS_ACTIVE, MEMBER_STATUS_PENDING}:
        desired_status = MEMBER_STATUS_PENDING
    existing = _read(COL_PARTICIPANTS, uid)
    name = _display_name(user, display_name or (existing or {}).get("display_name", ""))

    if existing and CODE_RE.fullmatch(str(existing.get("code") or "")):
        _reserve_code(existing["code"], uid)
        current = str(existing.get("status") or MEMBER_STATUS_ACTIVE)
        if current == MEMBER_STATUS_SUSPENDED:
            existing["status"] = MEMBER_STATUS_SUSPENDED
        else:
            existing["status"] = MEMBER_STATUS_ACTIVE if current == MEMBER_STATUS_ACTIVE else desired_status
        existing["display_name"] = name
        existing["public_identity"] = _public_identity(existing["code"], name)
        existing["role"] = existing.get("role") or _member_role(user)
        existing["updated_at"] = now
        if str(user.get("email") or "").strip():
            existing["email"] = str(user.get("email") or "").strip().lower()[:254]
        _write(COL_PARTICIPANTS, uid, existing)
        return existing

    claim = _claimable_code(user, requested_code)
    preferred = claim or _reserved_code_for_user(uid)
    for _ in range(40):
        code = preferred or generate_code(exclude_user_id=uid)
        if not _reserve_code(code, uid) and code != preferred:
            if claim:
                raise HTTPException(409, "This ID could not be claimed. Request a new ID if you do not have one.")
            continue
        # If claiming a code owned by another participant with same email, bind to that code for this user
        # by creating a participant record; old record remains but code reservation points here. Avoid duplicate active codes.
        owner = participant_by_code(code, include_inactive=True)
        if owner and str(owner.get("user_id") or "") != uid:
            owner_email = str(owner.get("email") or "").strip().lower()
            user_email = str(user.get("email") or "").strip().lower()
            if not (user_email and owner_email and user_email == owner_email):
                if claim:
                    raise HTTPException(409, "This ID is already assigned. Request a new ID if you do not have one.")
                preferred = ""
                continue
            # Rebind: deactivate old participant mapping for same email, keep history by code in messages.
            old_uid = str(owner.get("user_id") or "")
            if old_uid:
                old_doc = _read(COL_PARTICIPANTS, old_uid)
                if old_doc:
                    old_doc["status"] = "migrated"
                    old_doc["migrated_to"] = uid
                    old_doc["updated_at"] = now
                    _write(COL_PARTICIPANTS, old_uid, old_doc)
        doc = {
            "user_id": uid,
            "code": code,
            "display_name": name,
            "public_identity": _public_identity(code, name),
            "email": str(user.get("email") or "").strip().lower()[:254],
            "role": _member_role(user),
            "status": desired_status,
            "joined_at": now,
            "created_at": now,
            "updated_at": now,
        }
        if _write_participant_if_code_free(uid, code, doc):
            return doc
        preferred = ""
        if claim:
            raise HTTPException(409, "This ID could not be claimed. Request a new ID if you do not have one.")
    raise HTTPException(409, "Unable to assign a unique public chat identification code.")


def get_participant(user: dict[str, Any], include_pending: bool = False) -> dict | None:
    uid = str(user.get("id") or "").strip()
    if not uid:
        return None
    doc = _read(COL_PARTICIPANTS, uid)
    if not doc or not CODE_RE.fullmatch(str(doc.get("code") or "")):
        return None
    status = str(doc.get("status") or MEMBER_STATUS_ACTIVE)
    if status == MEMBER_STATUS_ACTIVE:
        return doc
    return doc if include_pending else None


def require_participant(user: dict[str, Any]) -> dict:
    p = get_participant(user)
    if not p:
        raise HTTPException(403, "Request a public chat identification code before joining the public chat.")
    return p


def _viewer_for_action(user: dict[str, Any]) -> dict:
    p = get_participant(user)
    if p:
        return p
    if permissions.can_moderate(user):
        return {"user_id": str(user.get("id") or ""), "code": "", "role": _member_role(user)}
    raise HTTPException(403, "Request a public chat identification code before using the public chat.")


def participant_by_code(code: str, include_inactive: bool = False) -> dict | None:
    code = str(code or "").strip().upper()
    if not CODE_RE.fullmatch(code):
        return None
    for item in _list(COL_PARTICIPANTS, 5000):
        if str(item.get("code") or "").upper() != code:
            continue
        status = str(item.get("status") or MEMBER_STATUS_ACTIVE)
        if include_inactive or status == MEMBER_STATUS_ACTIVE:
            return item
    return None


def _message_visible(msg: dict, viewer: dict, blocked_codes: set[str] | None = None) -> bool:
    sender_code = str(msg.get("sender_code") or "")
    if blocked_codes and sender_code in blocked_codes:
        return False
    viewer_uid = str(viewer.get("user_id") or "")
    deleted_for = {str(x) for x in (msg.get("deleted_for") or []) if str(x)}
    if viewer_uid and viewer_uid in deleted_for:
        return False
    kind = str(msg.get("kind") or "public")
    if kind == "private":
        return bool(viewer_uid) and viewer_uid in {
            str(msg.get("sender_user_id") or ""),
            str(msg.get("private_recipient_user_id") or ""),
        }
    # Moderators can remove public content, but never gain access to private threads.
    return True


def _reaction_summaries(viewer_uid: str) -> dict[str, dict[str, Any]]:
    by_message: dict[str, dict[str, Any]] = {}
    for doc in _list(COL_REACTIONS, 2000):
        message_id = str(doc.get("message_id") or "")
        emoji = str(doc.get("emoji") or "")
        uid = str(doc.get("user_id") or "")
        if not message_id or not emoji:
            continue
        entry = by_message.setdefault(message_id, {})
        emoji_entry = entry.setdefault(emoji, {"count": 0, "mine": False})
        emoji_entry["count"] = int(emoji_entry["count"]) + 1
        if uid and uid == viewer_uid:
            emoji_entry["mine"] = True
    return by_message


def _read_counts() -> list[tuple[str, int]]:
    readers = []
    for doc in _list(COL_READ_STATE, 500):
        uid = str(doc.get("user_id") or "")
        if uid:
            readers.append((uid, int(doc.get("last_read_at") or 0)))
    return readers


def _serialize_message(msg: dict, viewer: dict, reaction_map: dict | None = None,
                       readers: list[tuple[str, int]] | None = None) -> dict:
    kind = str(msg.get("kind") or "public")
    sender_uid = str(msg.get("sender_user_id") or "")
    viewer_uid = str(viewer.get("user_id") or "")
    deleted = bool(msg.get("deleted"))
    reply = msg.get("reply_to") if isinstance(msg.get("reply_to"), dict) else None
    if reply and str(reply.get("kind") or "") == "private":
        # A quote of a private thread is never public, even on a legacy message
        # that was created before this redaction rule existed.
        members = {str(uid) for uid in (reply.get("participants") or []) if str(uid)}
        if not viewer_uid or viewer_uid not in members:
            reply = {**reply, "text": "", "has_audio": False, "redacted": True}
    created_at = int(msg.get("created_at") or 0)
    readers = readers if readers is not None else _read_counts()
    read_count = sum(1 for uid, stamp in readers if uid and uid != sender_uid and stamp >= created_at and created_at)
    reaction_map = reaction_map if reaction_map is not None else _reaction_summaries(viewer_uid)
    attachments = []
    raw_attachments = msg.get("attachments") if isinstance(msg.get("attachments"), list) else []
    view_once = bool(msg.get("view_once")) and bool(raw_attachments)
    viewed_by = [str(x) for x in (msg.get("viewed_by") or []) if str(x)]
    viewer_viewed = bool(viewer_uid) and viewer_uid in viewed_by
    if not deleted:
        for item in raw_attachments:
            if not isinstance(item, dict):
                continue
            fid = str(item.get("file_id") or "")
            if not fid:
                continue
            opened = (not view_once) or (sender_uid == viewer_uid) or (not viewer_viewed)
            attachments.append({
                "file_id": fid,
                "file_name": str(item.get("file_name") or fid),
                "mime_type": str(item.get("mime_type") or "application/octet-stream"),
                "size_bytes": int(item.get("size_bytes") or 0),
                "kind": str(item.get("kind") or "document"),
                "url": f"/api/public-chat/media/{fid}" if opened else "",
                "view_once": view_once,
                "opened": opened,
            })
    out = {
        "id": str(msg.get("id") or ""),
        "kind": kind,
        "created_at": created_at,
        "updated_at": int(msg.get("updated_at") or 0),
        "edited": bool(msg.get("edited")),
        "deleted": deleted,
        "sender_code": str(msg.get("sender_code") or ""),
        "sender_name": str(msg.get("sender_name") or ""),
        "sender_identity": str(msg.get("sender_identity") or ""),
        "mine": sender_uid == viewer_uid,
        "reply_to": reply,
        "mentions": [str(x) for x in (msg.get("mentions") or []) if CODE_RE.fullmatch(str(x))],
        "private_recipient_code": str(msg.get("private_recipient_code") or "") if kind == "private" else "",
        "private_recipient_name": str(msg.get("private_recipient_name") or "") if kind == "private" else "",
        "reactions": reaction_map.get(str(msg.get("id") or ""), {}),
        "read_count": read_count,
        "attachments": attachments,
        "view_once": view_once,
        "viewed": viewer_viewed,
    }
    if deleted:
        out["text"] = ""
        out["audio"] = None
        out["deleted_placeholder"] = "This message was deleted"
    else:
        out["text"] = str(msg.get("text") or "")
        audio = msg.get("audio") if isinstance(msg.get("audio"), dict) else None
        if audio and str(audio.get("file_id") or ""):
            fid = str(audio.get("file_id") or "")
            out["audio"] = {
                "file_id": fid,
                "duration_ms": int(audio.get("duration_ms") or 0),
                "mime_type": str(audio.get("mime_type") or "audio/webm"),
                "size_bytes": int(audio.get("size_bytes") or 0),
                "file_name": str(audio.get("file_name") or f"voice-note-{fid}.webm"),
                "url": f"/api/public-chat/media/{fid}",
            }
        else:
            out["audio"] = None
        out["deleted_placeholder"] = ""
    return out


def list_messages(viewer: dict, limit: int = 100, before_ms: int | None = None,
                  query: str = "", blocked_codes: set[str] | None = None) -> list[dict]:
    cutoff = _now_s() - PUBLIC_RETENTION_SECONDS
    needle = str(query or "").strip().lower()
    items = []
    for msg in _list(COL_MESSAGES, 1000):
        kind = str(msg.get("kind") or "public")
        created_s = int(msg.get("created_at_s") or 0)
        expired = created_s < cutoff and (kind == "public" or settings.EXPIRE_PRIVATE_MESSAGES)
        if expired:
            continue
        if before_ms and int(msg.get("created_at") or 0) >= int(before_ms):
            continue
        if needle and needle not in str(msg.get("text") or "").lower():
            continue
        if _message_visible(msg, viewer, blocked_codes):
            items.append(msg)
    items.sort(key=lambda m: int(m.get("created_at") or 0))
    if limit > 0:
        items = items[-max(1, min(int(limit), 300)):]
    reactions = _reaction_summaries(str(viewer.get("user_id") or ""))
    readers = _read_counts()
    return [_serialize_message(m, viewer, reactions, readers) for m in items]


def _message_doc(message_id: str) -> dict | None:
    doc = _read(COL_MESSAGES, message_id)
    if not doc:
        return None
    doc["id"] = str(doc.get("id") or message_id)
    return doc


def _reply_snapshot(msg: dict) -> dict:
    return {
        "id": str(msg.get("id") or ""),
        "sender_code": str(msg.get("sender_code") or ""),
        "sender_name": str(msg.get("sender_name") or ""),
        "sender_identity": str(msg.get("sender_identity") or ""),
        "kind": str(msg.get("kind") or "public"),
        "text": "" if msg.get("deleted") else str(msg.get("text") or "")[:240],
        "deleted": bool(msg.get("deleted")),
        "has_audio": bool((msg.get("audio") or {}).get("file_id")),
        "participants": [
            str(msg.get("sender_user_id") or ""),
            str(msg.get("private_recipient_user_id") or ""),
        ] if str(msg.get("kind") or "") == "private" else [],
    }


def _normalize_mentions(codes: list[str] | None) -> list[str]:
    out: list[str] = []
    for code in codes or []:
        c = str(code or "").strip().upper()
        if CODE_RE.fullmatch(c) and c not in out:
            out.append(c)
        if len(out) >= settings.MAX_MENTIONS:
            break
    return out


def create_message(user: dict, text: str, reply_to_id: str | None = None,
                   private_recipient_code: str | None = None,
                   mention_codes: list[str] | None = None,
                   audio: dict | None = None,
                   attachments: list[dict] | None = None,
                   view_once: bool = False) -> dict:
    sender = require_participant(user)
    body = str(text or "").strip()
    if not body and not audio and not attachments:
        raise HTTPException(400, "Enter a message, attach a file, or record a voice note.")
    if len(body) > settings.MAX_MESSAGE_LENGTH:
        raise HTTPException(400, "Message is too long.")

    kind = "public"
    recipient = None
    recipient_code = str(private_recipient_code or "").strip().upper()
    if recipient_code:
        recipient = participant_by_code(recipient_code)
        if not recipient:
            raise HTTPException(404, "The selected private recipient is not available.")
        if str(recipient.get("user_id") or "") == str(sender.get("user_id") or ""):
            raise HTTPException(400, "You cannot send a private reply to yourself.")
        kind = "private"

    reply_snapshot = None
    reply_to = str(reply_to_id or "").strip()
    if reply_to:
        parent = _message_doc(reply_to)
        if not parent or not _message_visible(parent, sender):
            raise HTTPException(404, "The message you are replying to is unavailable.")
        if kind == "private":
            parent_kind = str(parent.get("kind") or "public")
            if parent_kind == "private":
                members = {str(parent.get("sender_user_id") or ""), str(parent.get("private_recipient_user_id") or "")}
                if str(sender.get("user_id") or "") not in members or str(recipient.get("user_id") or "") not in members:
                    raise HTTPException(403, "You cannot reply privately across a different private conversation.")
        reply_snapshot = _reply_snapshot(parent)

    # Replying to a private thread must stay private. Otherwise the quoted text
    # would become visible to the whole room even though the sender can see it.
    if reply_snapshot and str(reply_snapshot.get("kind") or "") == "private" and kind != "private":
        parent_sender = str(parent.get("sender_user_id") or "")
        sender_uid = str(sender.get("user_id") or "")
        other_code = (str(parent.get("private_recipient_code") or "")
                      if parent_sender == sender_uid else str(parent.get("sender_code") or ""))
        promoted = participant_by_code(other_code)
        if not promoted:
            raise HTTPException(404, "The private conversation is no longer available.")
        recipient = promoted
        recipient_code = other_code
        kind = "private"

    mentions = _normalize_mentions(mention_codes)
    for code in mentions:
        if not participant_by_code(code):
            raise HTTPException(404, f"Mentioned participant {code} is not available.")

    now = _now()
    now_s = _now_s()
    msg_id = uuid.uuid4().hex
    doc = {
        "id": msg_id,
        "kind": kind,
        "text": body,
        "audio": audio or None,
        "attachments": attachments or [],
        "view_once": bool(view_once) and bool(attachments) and not bool(audio),
        "viewed_by": [],
        "deleted_for": [],
        "sender_user_id": str(sender.get("user_id") or ""),
        "sender_code": str(sender.get("code") or ""),
        "sender_name": str(sender.get("display_name") or ""),
        "sender_identity": str(sender.get("public_identity") or ""),
        "private_recipient_user_id": str(recipient.get("user_id") or "") if recipient else "",
        "private_recipient_code": str(recipient.get("code") or "") if recipient else "",
        "private_recipient_name": str(recipient.get("display_name") or "") if recipient else "",
        "reply_to": reply_snapshot,
        "mentions": mentions,
        "edited": False,
        "deleted": False,
        "created_at": now,
        "created_at_s": now_s,
        "updated_at": now,
        "updated_at_s": now_s,
    }
    _write(COL_MESSAGES, msg_id, doc)
    return _serialize_message(doc, sender)


def edit_message(user: dict, message_id: str, text: str) -> dict:
    viewer = _viewer_for_action(user)
    doc = _message_doc(message_id)
    if not doc or not _message_visible(doc, viewer):
        raise HTTPException(404, "Message not found.")
    if not permissions.can_edit_message(user, doc):
        raise HTTPException(403, "You can only edit your own messages.")
    if doc.get("deleted"):
        raise HTTPException(400, "Deleted messages cannot be edited.")
    body = str(text or "").strip()
    if not body:
        raise HTTPException(400, "Message text cannot be empty.")
    if len(body) > settings.MAX_MESSAGE_LENGTH:
        raise HTTPException(400, "Message is too long.")
    doc["text"] = body
    doc["edited"] = True
    doc["updated_at"] = _now()
    doc["updated_at_s"] = _now_s()
    _write(COL_MESSAGES, str(doc.get("id") or message_id), doc)
    return _serialize_message(doc, viewer)


def delete_message(user: dict, message_id: str, mode: str = "me") -> dict:
    viewer = _viewer_for_action(user)
    doc = _message_doc(message_id)
    if not doc or not _message_visible(doc, viewer):
        raise HTTPException(404, "Message not found.")
    mode = str(mode or "me").strip().lower()
    if mode not in {"me", "all"}:
        raise HTTPException(400, "Delete mode must be 'me' or 'all'.")
    if mode == "all":
        if not permissions.can_delete_message(user, doc):
            raise HTTPException(403, "You can only delete your own messages for everyone.")
        if doc.get("deleted"):
            return {"action": "deleted_for_all", "message": _serialize_message(doc, viewer)}
        doc["deleted"] = True
        doc["text"] = ""
        doc["audio"] = None
        doc["attachments"] = []
        doc["view_once"] = False
        doc["viewed_by"] = []
        doc["updated_at"] = _now()
        doc["updated_at_s"] = _now_s()
        _write(COL_MESSAGES, str(doc.get("id") or message_id), doc)
        return {"action": "deleted_for_all", "message": _serialize_message(doc, viewer)}

    uid = str(viewer.get("user_id") or "")
    if not uid:
        raise HTTPException(403, "You cannot delete this message.")
    deleted_for = [str(x) for x in (doc.get("deleted_for") or []) if str(x)]
    if uid not in deleted_for:
        deleted_for.append(uid)
        doc["deleted_for"] = deleted_for
        doc["updated_at"] = _now()
        doc["updated_at_s"] = _now_s()
        _write(COL_MESSAGES, str(doc.get("id") or message_id), doc)
    return {"action": "deleted_for_me", "message_id": str(doc.get("id") or message_id)}


def _extension_for_upload(upload: UploadFile, allowed: dict[str, str]) -> tuple[str, str]:
    content_type = str(upload.content_type or "").lower().split(";", 1)[0].strip()
    guessed = Path(upload.filename or "").suffix.lower()
    if content_type in allowed:
        return allowed[content_type], content_type
    if guessed in allowed:
        ext = guessed
        return ext, content_type or allowed[ext]
    raise HTTPException(400, "Unsupported file format.")


def _ffmpeg_bin() -> str | None:
    for name in ("ffmpeg", "ffmpeg.exe"):
        found = shutil.which(name)
        if found:
            return found
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if local.exists():
        for cand in local.rglob("ffmpeg.exe"):
            if cand.is_file():
                return str(cand)
    return None


def _ffprobe_bin() -> str | None:
    for name in ("ffprobe", "ffprobe.exe"):
        found = shutil.which(name)
        if found:
            return found
    ffmpeg = _ffmpeg_bin()
    if ffmpeg:
        cand = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if cand.is_file():
            return str(cand)
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if local.exists():
        for cand in local.rglob("ffprobe.exe"):
            if cand.is_file():
                return str(cand)
    return None


def _probe_duration_ms(data: bytes, ext: str) -> int:
    """Best-effort actual media duration. Returns 0 if unavailable."""
    ffprobe = _ffprobe_bin()
    if not ffprobe or not data:
        return 0
    src_suffix = ext if ext.startswith(".") else f".{ext.lstrip('.') or 'webm'}"
    with tempfile.TemporaryDirectory(prefix="mnh-probe-") as td:
        src = Path(td) / f"in{src_suffix}"
        try:
            src.write_bytes(data)
            cmd = [
                ffprobe, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(src),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
            if proc.returncode != 0:
                return 0
            raw = (proc.stdout or "").strip().splitlines()[0].strip()
            dur = float(raw)
            if not (dur > 0):
                return 0
            return max(0, min(int(round(dur * 1000)), MAX_VOICE_DURATION_MS))
        except Exception:
            return 0


def _compress_voice(data: bytes, ext: str, content_type: str) -> tuple[bytes, str, str, int]:
    """Compress voice note to small Opus/WebM when ffmpeg is available.

    Returns (data, ext, content_type, duration_ms). Falls back to original bytes on any failure.
    duration_ms is probed from the resulting file when possible.
    """
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg or not data:
        return data, ext, content_type, _probe_duration_ms(data, ext)
    src_suffix = ext if ext.startswith(".") else f".{ext.lstrip('.') or 'webm'}"
    with tempfile.TemporaryDirectory(prefix="mnh-voice-") as td:
        src = Path(td) / f"in{src_suffix}"
        dst = Path(td) / f"out{VOICE_TARGET_EXT}"
        try:
            src.write_bytes(data)
            cmd = [
                ffmpeg, "-y", "-v", "error",
                "-i", str(src),
                "-vn", "-sn", "-dn",
                "-ac", "1",
                "-ar", "24000",
                "-c:a", "libopus",
                "-b:a", VOICE_COMPRESS_BITRATE,
                "-application", "voip",
                str(dst),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
            if proc.returncode != 0 or not dst.exists():
                return data, ext, content_type, _probe_duration_ms(data, ext)
            out = dst.read_bytes()
            if not out:
                return data, ext, content_type, _probe_duration_ms(data, ext)
            probed = _probe_duration_ms(out, VOICE_TARGET_EXT)
            if len(out) < len(data) or content_type != VOICE_TARGET_MIME or ext != VOICE_TARGET_EXT:
                return out, VOICE_TARGET_EXT, VOICE_TARGET_MIME, probed
            return data, ext, content_type, probed or _probe_duration_ms(data, ext)
        except Exception:
            return data, ext, content_type, _probe_duration_ms(data, ext)


def _media_blob_write(file_id: str, data: bytes, mime_type: str, file_name: str) -> None:
    """Best-effort small metadata blob. Avoid storing large base64 audio in docs DB."""
    try:
        if len(data) > 2 * 1024 * 1024:
            return
        doc = {
            "id": file_id,
            "mime_type": mime_type,
            "file_name": file_name,
            "size_bytes": len(data),
            "b64": base64.b64encode(data).decode("ascii"),
            "created_at": _now(),
            "created_at_s": _now_s(),
        }
        _write(COL_MEDIA_BLOBS, file_id, doc)
    except Exception:
        return


def _media_blob_read(file_id: str) -> dict | None:
    doc = _read(COL_MEDIA_BLOBS, file_id)
    if not doc or not isinstance(doc.get("b64"), str):
        return None
    try:
        raw = base64.b64decode(doc["b64"].encode("ascii"), validate=False)
    except Exception:
        return None
    return {
        "file_id": file_id,
        "mime_type": str(doc.get("mime_type") or "application/octet-stream"),
        "file_name": str(doc.get("file_name") or file_id),
        "size_bytes": int(doc.get("size_bytes") or len(raw)),
        "data": raw,
    }


def _media_blob_delete(file_id: str) -> None:
    try:
        _delete(COL_MEDIA_BLOBS, file_id)
    except Exception:
        pass


def save_audio_upload(user: dict, upload: UploadFile, duration_ms: int = 0) -> dict:
    require_participant(user)
    ensure_directories()
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ext, content_type = _extension_for_upload(upload, ALLOWED_AUDIO)
    data = upload.file.read(MAX_AUDIO_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "The voice note is empty.")
    if len(data) > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(413, "Voice note upload is too large.")

    duration_ms = max(0, min(int(duration_ms or 0), MAX_VOICE_DURATION_MS))
    data, ext, content_type, probed_ms = _compress_voice(data, ext, content_type or "audio/webm")
    if probed_ms > 0:
        duration_ms = probed_ms
    if len(data) > settings.MAX_AUDIO_BYTES:
        raise HTTPException(413, "Voice note is too large after compression. Please record a shorter note.")

    file_id = uuid.uuid4().hex
    file_name = f"{file_id}{ext}"
    path = MEDIA_DIR / file_name
    path.write_bytes(data)
    # Best-effort small metadata backup only; large audio stays on persistent disk.
    _media_blob_write(file_id, data, content_type or "audio/webm", file_name)

    return {
        "file_id": file_id,
        "file_name": file_name,
        "mime_type": content_type or "audio/webm",
        "size_bytes": len(data),
        "duration_ms": duration_ms,
        "storage": "file",
    }


async def save_audio_upload_async(user: dict, upload: UploadFile, duration_ms: int = 0) -> dict:
    import asyncio
    return await asyncio.to_thread(save_audio_upload, user, upload, duration_ms)


def save_attachment_upload(user: dict, upload: UploadFile) -> dict:
    require_participant(user)
    ensure_directories()
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ext, content_type = _extension_for_upload(upload, ALLOWED_ATTACHMENTS)
    data = upload.file.read(settings.MAX_ATTACHMENT_BYTES + 1)
    if not data:
        raise HTTPException(400, "The attachment is empty.")
    if len(data) > settings.MAX_ATTACHMENT_BYTES:
        raise HTTPException(413, "Attachments must be 15 MB or smaller.")
    file_id = uuid.uuid4().hex
    path = MEDIA_DIR / f"{file_id}{ext}"
    path.write_bytes(data)
    return {
        "file_id": file_id,
        "file_name": str(upload.filename or path.name)[:120],
        "mime_type": content_type or ALLOWED_ATTACHMENTS.get(ext, "application/octet-stream"),
        "size_bytes": len(data),
        "kind": "image" if content_type.startswith("image/") or ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"} else "document",
    }


def get_media_path(file_id: str) -> Path | None:
    fid = re.sub(r"[^a-f0-9]", "", str(file_id or "").lower())
    if not fid:
        return None
    ensure_directories()
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    for path in MEDIA_DIR.glob(fid + ".*"):
        if path.is_file():
            return path
    # Cloud-backed fallback: restore blob to local cache for FileResponse/streaming.
    blob = _media_blob_read(fid)
    if not blob:
        return None
    mime = str(blob.get("mime_type") or "application/octet-stream")
    ext = mimetypes.guess_extension(mime) or ".bin"
    if mime == "audio/webm":
        ext = ".webm"
    elif mime == "audio/ogg":
        ext = ".ogg"
    elif mime in {"audio/mp4", "audio/m4a", "audio/x-m4a"}:
        ext = ".m4a"
    path = MEDIA_DIR / f"{fid}{ext}"
    try:
        path.write_bytes(blob["data"])
        return path
    except Exception:
        return None


def get_media_blob(file_id: str) -> dict | None:
    """Return cloud-stored media bytes as a fallback when local file cache is missing."""
    fid = re.sub(r"[^a-f0-9]", "", str(file_id or "").lower())
    if not fid:
        return None
    return _media_blob_read(fid)


def can_access_media(user: dict, file_id: str, consume_view_once: bool = False) -> bool:
    viewer = get_participant(user)
    if not viewer:
        return False
    fid = re.sub(r"[^a-f0-9]", "", str(file_id or "").lower())
    viewer_uid = str(viewer.get("user_id") or "")
    for msg in _list(COL_MESSAGES, 5000):
        audio = msg.get("audio") if isinstance(msg.get("audio"), dict) else None
        media = [audio] if audio and str(audio.get("file_id") or "") else []
        attachments = msg.get("attachments") if isinstance(msg.get("attachments"), list) else []
        media.extend(a for a in attachments if isinstance(a, dict))
        if not any(str((item or {}).get("file_id") or "") == fid for item in media):
            continue
        if not _message_visible(msg, viewer):
            return False
        if msg.get("deleted"):
            return False
        if bool(msg.get("view_once")) and str(msg.get("sender_user_id") or "") != viewer_uid:
            viewed_by = [str(x) for x in (msg.get("viewed_by") or []) if str(x)]
            if viewer_uid in viewed_by:
                return False
            if consume_view_once and viewer_uid:
                viewed_by.append(viewer_uid)
                msg["viewed_by"] = viewed_by
                msg["updated_at"] = _now()
                msg["updated_at_s"] = _now_s()
                _write(COL_MESSAGES, str(msg.get("id") or msg.get("_id") or ""), msg)
        return True
    return False


def cleanup_public_retention(now_s: int | None = None, expire_private: bool | None = None) -> dict:
    now_s = int(now_s or _now_s())
    cutoff = now_s - PUBLIC_RETENTION_SECONDS
    expire_private = settings.EXPIRE_PRIVATE_MESSAGES if expire_private is None else bool(expire_private)
    deleted_messages = 0
    deleted_files = 0
    referenced = set()
    all_msgs = _list(COL_MESSAGES, 5000)
    surviving_ids = set()
    for msg in all_msgs:
        kind = str(msg.get("kind") or "public")
        created = int(msg.get("created_at_s") or 0)
        expired = created < cutoff and (kind == "public" or (kind == "private" and expire_private))
        if expired:
            continue
        surviving_ids.add(str(msg.get("_id") or msg.get("id") or ""))
        if msg.get("deleted"):
            continue
        audio = msg.get("audio") if isinstance(msg.get("audio"), dict) else None
        media = [audio] if audio and str(audio.get("file_id") or "") else []
        attachments = msg.get("attachments") if isinstance(msg.get("attachments"), list) else []
        media.extend(a for a in attachments if isinstance(a, dict))
        for item in media:
            fid = re.sub(r"[^a-f0-9]", "", str((item or {}).get("file_id") or "").lower())
            if fid:
                referenced.add(fid)

    for msg in all_msgs:
        kind = str(msg.get("kind") or "public")
        created = int(msg.get("created_at_s") or 0)
        if created < cutoff and (kind == "public" or (kind == "private" and expire_private)):
            if _delete(COL_MESSAGES, str(msg.get("_id") or msg.get("id") or "")):
                deleted_messages += 1

    deleted_reactions = 0
    for reaction in _list(COL_REACTIONS, 2000):
        message_id = str(reaction.get("message_id") or "")
        if message_id and not _message_doc(message_id):
            if _delete(COL_REACTIONS, str(reaction.get("_id") or "")):
                deleted_reactions += 1

    ensure_directories()
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    for path in MEDIA_DIR.glob("*"):
        if not path.is_file():
            continue
        fid = path.stem.lower()
        if fid and fid not in referenced:
            try:
                path.unlink()
                deleted_files += 1
            except OSError:
                pass
    return {
        "deleted_messages": deleted_messages,
        "deleted_files": deleted_files,
        "deleted_reactions": deleted_reactions,
        "surviving_messages": len(surviving_ids),
        "cutoff": cutoff,
        "expired_private": expire_private,
    }
