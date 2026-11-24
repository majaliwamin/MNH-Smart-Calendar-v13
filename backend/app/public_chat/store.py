from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import secrets
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from app.config import DATA_DIR, ensure_directories
from app.database.connection import database

COL_PARTICIPANTS = "public_chat_participants"
COL_MESSAGES = "public_chat_messages"
PUBLIC_RETENTION_SECONDS = 7 * 24 * 60 * 60
CODE_PREFIX = "MNH-"
CODE_RE = re.compile(r"^MNH-\d{4}$")
MEDIA_DIR = DATA_DIR / "public_chat_media"
MAX_AUDIO_BYTES = 10 * 1024 * 1024
ALLOWED_AUDIO = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "video/webm": ".webm",  # MediaRecorder often reports video/webm for audio-only
}


def _now() -> int:
    return int(time.time() * 1000)


def _now_s() -> int:
    return int(time.time())


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
    name = re.sub(r"\s+", " ", name)[:80]
    if not name:
        email = str(user.get("email") or "").strip()
        if email and "@" in email:
            name = email.split("@", 1)[0][:80]
    return name or "Participant"


def _public_identity(code: str, name: str) -> str:
    clean = re.sub(r"\s+", " ", str(name or "")).strip()[:80] or "Participant"
    return f"{code} — {clean}"


def _active_codes(exclude_user_id: str = "") -> set[str]:
    codes = set()
    for item in _list(COL_PARTICIPANTS, 5000):
        if exclude_user_id and str(item.get("user_id") or "") == exclude_user_id:
            continue
        if str(item.get("status") or "active") != "active":
            continue
        code = str(item.get("code") or "")
        if CODE_RE.fullmatch(code):
            codes.add(code)
    return codes


def generate_code(exclude_user_id: str = "") -> str:
    used = _active_codes(exclude_user_id)
    available = [f"{CODE_PREFIX}{i:04d}" for i in range(10000) if f"{CODE_PREFIX}{i:04d}" not in used]
    if not available:
        raise HTTPException(409, "No public chat identification codes are currently available.")
    # Non-sequential random selection from remaining space.
    return secrets.choice(available)


def ensure_participant(user: dict[str, Any], display_name: str = "") -> dict:
    uid = _participant_id(user)
    now = _now_s()
    existing = _read(COL_PARTICIPANTS, uid)
    name = _display_name(user, display_name or (existing or {}).get("display_name", ""))
    if existing and CODE_RE.fullmatch(str(existing.get("code") or "")):
        existing["display_name"] = name
        existing["public_identity"] = _public_identity(existing["code"], name)
        existing["updated_at"] = now
        existing["status"] = "active"
        if str(user.get("email") or "").strip():
            existing["email"] = str(user.get("email") or "").strip().lower()[:254]
        _write(COL_PARTICIPANTS, uid, existing)
        return existing
    # Collision-safe assignment: write candidate if slot still free.
    for _ in range(30):
        code = generate_code(exclude_user_id=uid)
        doc = {
            "user_id": uid,
            "code": code,
            "display_name": name,
            "public_identity": _public_identity(code, name),
            "email": str(user.get("email") or "").strip().lower()[:254],
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        # Verify no other active participant took the code between generation and write.
        if any(p.get("code") == code and p.get("user_id") != uid and p.get("status") == "active" for p in _list(COL_PARTICIPANTS, 5000)):
            continue
        _write(COL_PARTICIPANTS, uid, doc)
        return doc
    raise HTTPException(409, "Unable to assign a unique public chat identification code.")


def get_participant(user: dict[str, Any]) -> dict | None:
    uid = str(user.get("id") or "").strip()
    if not uid:
        return None
    doc = _read(COL_PARTICIPANTS, uid)
    if not doc or str(doc.get("status") or "active") != "active":
        return None
    if not CODE_RE.fullmatch(str(doc.get("code") or "")):
        return None
    return doc


def require_participant(user: dict[str, Any]) -> dict:
    p = get_participant(user)
    if not p:
        raise HTTPException(403, "Request a public chat identification code before joining the public chat.")
    return p


def participant_by_code(code: str) -> dict | None:
    code = str(code or "").strip().upper()
    if not CODE_RE.fullmatch(code):
        return None
    for item in _list(COL_PARTICIPANTS, 5000):
        if str(item.get("code") or "").upper() == code and str(item.get("status") or "active") == "active":
            return item
    return None


def _message_visible(msg: dict, viewer: dict) -> bool:
    if str(msg.get("kind") or "public") == "deleted":
        # Deleted placeholders visible in public timeline if they were public.
        pass
    viewer_uid = str(viewer.get("user_id") or "")
    viewer_code = str(viewer.get("code") or "")
    kind = str(msg.get("kind") or "public")
    if kind == "private":
        sender_uid = str(msg.get("sender_user_id") or "")
        recipient_uid = str(msg.get("private_recipient_user_id") or "")
        return viewer_uid and viewer_uid in {sender_uid, recipient_uid}
    return True


def _serialize_message(msg: dict, viewer: dict) -> dict:
    kind = str(msg.get("kind") or "public")
    sender_uid = str(msg.get("sender_user_id") or "")
    viewer_uid = str(viewer.get("user_id") or "")
    deleted = bool(msg.get("deleted"))
    reply = msg.get("reply_to") if isinstance(msg.get("reply_to"), dict) else None
    # Hide private reply metadata from unauthorized viewers by construction; callers should filter first.
    out = {
        "id": str(msg.get("id") or ""),
        "kind": kind,
        "created_at": int(msg.get("created_at") or 0),
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
    }
    if deleted:
        out["text"] = ""
        out["audio"] = None
        out["deleted_placeholder"] = "This message was deleted"
    else:
        out["text"] = str(msg.get("text") or "")
        audio = msg.get("audio") if isinstance(msg.get("audio"), dict) else None
        if audio and str(audio.get("file_id") or ""):
            out["audio"] = {
                "file_id": str(audio.get("file_id") or ""),
                "duration_ms": int(audio.get("duration_ms") or 0),
                "mime_type": str(audio.get("mime_type") or "audio/webm"),
                "url": f"/api/public-chat/media/{str(audio.get('file_id') or '')}",
            }
        else:
            out["audio"] = None
        out["deleted_placeholder"] = ""
    return out


def list_messages(viewer: dict, limit: int = 100, before_ms: int | None = None) -> list[dict]:
    cutoff = _now_s() - PUBLIC_RETENTION_SECONDS
    items = []
    for msg in _list(COL_MESSAGES, 1000):
        if int(msg.get("created_at_s") or 0) < cutoff and str(msg.get("kind") or "public") == "public":
            continue
        if before_ms and int(msg.get("created_at") or 0) >= int(before_ms):
            continue
        if _message_visible(msg, viewer):
            items.append(msg)
    items.sort(key=lambda m: int(m.get("created_at") or 0))
    if limit > 0:
        items = items[-max(1, min(int(limit), 300)):]
    return [_serialize_message(m, viewer) for m in items]


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
    }


def _normalize_mentions(codes: list[str] | None) -> list[str]:
    out = []
    for code in codes or []:
        c = str(code or "").strip().upper()
        if CODE_RE.fullmatch(c) and c not in out:
            out.append(c)
        if len(out) >= 20:
            break
    return out


def create_message(user: dict, text: str, reply_to_id: str | None = None, private_recipient_code: str | None = None, mention_codes: list[str] | None = None, audio: dict | None = None) -> dict:
    sender = require_participant(user)
    body = str(text or "").strip()
    if not body and not audio:
        raise HTTPException(400, "Enter a message or record a voice note.")
    if len(body) > 4000:
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
        # Private reply target must stay within same private conversation.
        if kind == "private":
            parent_kind = str(parent.get("kind") or "public")
            if parent_kind == "private":
                members = {str(parent.get("sender_user_id") or ""), str(parent.get("private_recipient_user_id") or "")}
                if str(sender.get("user_id") or "") not in members or str(recipient.get("user_id") or "") not in members:
                    raise HTTPException(403, "You cannot reply privately across a different private conversation.")
        reply_snapshot = _reply_snapshot(parent)

    now = _now()
    now_s = _now_s()
    msg_id = uuid.uuid4().hex
    mentions = _normalize_mentions(mention_codes)
    doc = {
        "id": msg_id,
        "kind": kind,
        "text": body,
        "audio": audio or None,
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
    sender = require_participant(user)
    doc = _message_doc(message_id)
    if not doc or not _message_visible(doc, sender):
        raise HTTPException(404, "Message not found.")
    if str(doc.get("sender_user_id") or "") != str(sender.get("user_id") or ""):
        raise HTTPException(403, "You can only edit your own messages.")
    if doc.get("deleted"):
        raise HTTPException(400, "Deleted messages cannot be edited.")
    body = str(text or "").strip()
    if not body:
        raise HTTPException(400, "Message text cannot be empty.")
    doc["text"] = body[:4000]
    doc["edited"] = True
    doc["updated_at"] = _now()
    doc["updated_at_s"] = _now_s()
    _write(COL_MESSAGES, str(doc.get("id") or message_id), doc)
    return _serialize_message(doc, sender)


def delete_message(user: dict, message_id: str) -> dict:
    sender = require_participant(user)
    doc = _message_doc(message_id)
    if not doc or not _message_visible(doc, sender):
        raise HTTPException(404, "Message not found.")
    is_author = str(doc.get("sender_user_id") or "") == str(sender.get("user_id") or "")
    is_admin = str(user.get("role") or "").strip().lower() in {"administrator", "hod", "coordinator", "executive_dean"}
    if not is_author and not is_admin:
        raise HTTPException(403, "You can only delete your own messages.")
    if doc.get("deleted"):
        return _serialize_message(doc, sender)
    doc["deleted"] = True
    doc["text"] = ""
    # Keep audio file reference cleanup for retention sweep to avoid race with open streams.
    doc["audio"] = None
    doc["edited"] = bool(doc.get("edited"))
    doc["updated_at"] = _now()
    doc["updated_at_s"] = _now_s()
    _write(COL_MESSAGES, str(doc.get("id") or message_id), doc)
    return _serialize_message(doc, sender)


def save_audio_upload(user: dict, upload: UploadFile) -> dict:
    require_participant(user)
    ensure_directories()
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    content_type = str(upload.content_type or mimetypes.guess_type(upload.filename or "")[0] or "").lower()
    ext = ALLOWED_AUDIO.get(content_type)
    if not ext:
        # Accept common browser blobs by filename fallback.
        guessed = Path(upload.filename or "").suffix.lower()
        if guessed in {".webm", ".ogg", ".m4a", ".mp3", ".wav"}:
            ext = guessed
            content_type = content_type or (mimetypes.guess_type("x" + ext)[0] or "audio/webm")
    if not ext:
        raise HTTPException(400, "Unsupported audio format.")
    data = upload.file.read(MAX_AUDIO_BYTES + 1)
    if not data:
        raise HTTPException(400, "The voice note is empty.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Voice notes must be 10 MB or smaller.")
    file_id = uuid.uuid4().hex
    path = MEDIA_DIR / f"{file_id}{ext}"
    path.write_bytes(data)
    return {
        "file_id": file_id,
        "file_name": path.name,
        "mime_type": content_type or "audio/webm",
        "size_bytes": len(data),
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
    return None


def can_access_media(user: dict, file_id: str) -> bool:
    viewer = get_participant(user)
    if not viewer:
        return False
    fid = re.sub(r"[^a-f0-9]", "", str(file_id or "").lower())
    for msg in _list(COL_MESSAGES, 2000):
        audio = msg.get("audio") if isinstance(msg.get("audio"), dict) else None
        if str((audio or {}).get("file_id") or "") != fid:
            continue
        if not _message_visible(msg, viewer):
            return False
        if msg.get("deleted"):
            return False
        # Public messages are accessible to registered participants; private only to members.
        return True
    return False


def cleanup_public_retention(now_s: int | None = None) -> dict:
    now_s = int(now_s or _now_s())
    cutoff = now_s - PUBLIC_RETENTION_SECONDS
    deleted_messages = 0
    deleted_files = 0
    referenced = set()
    # Determine referenced files from retained, non-deleted messages.
    all_msgs = _list(COL_MESSAGES, 5000)
    for msg in all_msgs:
        kind = str(msg.get("kind") or "public")
        created = int(msg.get("created_at_s") or 0)
        expired_public = kind == "public" and created < cutoff
        if expired_public:
            continue
        if msg.get("deleted"):
            continue
        audio = msg.get("audio") if isinstance(msg.get("audio"), dict) else None
        fid = re.sub(r"[^a-f0-9]", "", str((audio or {}).get("file_id") or "").lower())
        if fid:
            referenced.add(fid)
    # Delete expired public messages.
    for msg in all_msgs:
        kind = str(msg.get("kind") or "public")
        created = int(msg.get("created_at_s") or 0)
        if kind == "public" and created < cutoff:
            if _delete(COL_MESSAGES, str(msg.get("_id") or msg.get("id") or "")):
                deleted_messages += 1
    # Delete orphaned media files.
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
    return {"deleted_messages": deleted_messages, "deleted_files": deleted_files, "cutoff": cutoff}
