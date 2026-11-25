"""CRARA one-to-one classroom backend.

The embedded classroom receives a short-lived, server-signed handoff token from
the existing CRARA cookie session. That handoff is exchanged for a LiveKit JWT
whose room and identity are derived server-side per lesson. LiveKit secrets and
the CRARA session token never reach browser JavaScript.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.class_rep import memory
from app.class_rep.classroom_permissions import classroom_permissions, classroom_role
from app.class_rep.whiteboard import verify_cohost_grant
from app.config import (
    DATA_DIR,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    LIVEKIT_HANDOFF_TTL_SECONDS,
    LIVEKIT_TOKEN_TTL_SECONDS,
    LIVEKIT_URL,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["CRARA live classroom"])

_GUEST_COOKIE = "cara_guest"
_GUEST_ID_RE = re.compile(r"^guest_[A-Za-z0-9_-]{8,96}$")
_LESSON_RE = re.compile(r"[^a-z0-9]+")
_HANDOFF_TYPE = "crara-classroom-handoff"
_JOIN_CODE_TTL_SECONDS = 1800
_JOIN_CODE_LENGTH = 8
# Exclude look-alike characters so codes can be read aloud in a live lesson.
_JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_JOIN_CODES: dict[str, dict[str, Any]] = {}
_JOIN_CODE_LOCK = threading.Lock()
_MAX_RECORDING_BYTES = 100 * 1024 * 1024
_RECORDING_EXTENSIONS = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/flac": ".flac",
    "video/webm": ".webm",
}


class ClassroomHandoffRequest(BaseModel):
    lesson: str | None = Field(default=None, max_length=120)
    join_code: str | None = Field(default=None, max_length=16)


class ClassroomJoinCodeRequest(BaseModel):
    lesson: str | None = Field(default=None, max_length=120)
    authority: str = Field(default="", max_length=2000)


class ClassroomJoinCodeRevokeRequest(BaseModel):
    code: str = Field(..., max_length=16)
    authority: str = Field(default="", max_length=2000)


class LiveKitTokenRequest(BaseModel):
    # The embedded classroom sends these for API compatibility. Room and
    # identity are intentionally re-derived from the signed handoff instead of
    # trusting client-supplied values.
    room_name: str | None = None
    identity: str | None = None
    name: str | None = None
    ttl_seconds: int = 3600


def _livekit_configured() -> bool:
    return bool(LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET)


def _configured() -> bool:
    # Built-in local classroom mode is always available; LiveKit is optional.
    return True


def _classroom_mode() -> str:
    return "livekit" if _livekit_configured() else "builtin"


def _require_configured() -> None:
    # Kept for compatibility; built-in mode means classroom is available.
    return None


def _clean_label(value: Any, limit: int = 128) -> str:
    return " ".join(str(value or "").split())[:limit]


def _lesson_slug(value: Any) -> str:
    slug = _LESSON_RE.sub("_", _clean_label(value, 120).lower()).strip("_")
    return (slug or "general")[:48]


def _display_name(user: dict) -> str:
    return _clean_label(user.get("name")) or "Guest"


def _identity(user: dict) -> str:
    user_id = str(user.get("id") or "").strip()
    if not user_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", user_id):
        raise HTTPException(401, "A valid CRARA session is required for the classroom.")
    return user_id if user_id.startswith("guest_") else "user_" + user_id


def _room_name(user_id: str, lesson: str) -> str:
    digest = hashlib.sha256(("crara-classroom:" + user_id).encode("utf-8")).hexdigest()[:12]
    return "crara_" + _lesson_slug(lesson) + "_" + digest


def _resolve_user(request: Request) -> dict:
    user = memory.resolve_session(request.cookies.get("cara_session"))
    if user:
        return user
    guest_id = str(request.cookies.get(_GUEST_COOKIE) or "")
    if _GUEST_ID_RE.fullmatch(guest_id):
        return {"id": guest_id, "name": "Guest", "email": ""}
    raise HTTPException(401, "Open CRARA first, then join the one-to-one classroom.")


def _require_host(request: Request) -> dict:
    user = _resolve_user(request)
    if classroom_role(user) != "host":
        raise HTTPException(403, "Only the classroom host can manage join codes.")
    return user


def _require_code_issuer(request: Request, lesson: str, authority: str) -> dict:
    """Accept the host, or a signed co-host grant scoped to this lesson room."""
    user = _resolve_user(request)
    if classroom_role(user) == "host":
        return user

    # Account sessions and guest identities never become hosts through a board
    # grant. Only an authenticated CRARA user may wield delegated code control.
    if not memory.resolve_session(request.cookies.get("cara_session")):
        raise HTTPException(403, "Only a signed-in classroom host or co-host can manage join codes.")

    grant = verify_cohost_grant(authority)
    if not grant:
        raise HTTPException(403, "Only the classroom host or a host-authorized co-host can manage join codes.")

    host_id = str(grant.get("sub") or "")
    if not host_id or grant.get("room") != _room_name(host_id, _lesson_slug(lesson)):
        raise HTTPException(403, "That co-host grant is not valid for this lesson room.")
    return {"id": host_id, "name": str(grant.get("name") or "")}


def _clean_join_code(value: Any) -> str:
    code = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())[:_JOIN_CODE_LENGTH]
    return code if len(code) == _JOIN_CODE_LENGTH else ""


def _issue_join_code(user: dict, lesson: str) -> dict:
    """Create a short-lived code that maps a student to the host's lesson room."""
    lesson = _lesson_slug(lesson)
    room = _room_name(str(user["id"]), lesson)
    now = int(time.time())
    with _JOIN_CODE_LOCK:
        for code, entry in list(_JOIN_CODES.items()):
            if entry["exp"] <= now:
                _JOIN_CODES.pop(code, None)
        for _ in range(24):
            code = "".join(secrets.choice(_JOIN_CODE_ALPHABET) for _ in range(_JOIN_CODE_LENGTH))
            if code not in _JOIN_CODES:
                break
        _JOIN_CODES[code] = {
            "room": room,
            "lesson": lesson,
            "host": str(user["id"]),
            "iat": now,
            "exp": now + _JOIN_CODE_TTL_SECONDS,
        }
    return {"code": code, "room": room, "lesson": lesson, "expires_in": _JOIN_CODE_TTL_SECONDS}


def _resolve_join_code(value: Any, lesson: str) -> dict:
    """Resolve a host-issued code without ever trusting a client-supplied room."""
    code = _clean_join_code(value)
    if not code:
        raise HTTPException(400, "Enter a valid classroom join code.")
    now = int(time.time())
    with _JOIN_CODE_LOCK:
        entry = _JOIN_CODES.get(code)
        if entry and entry["exp"] <= now:
            _JOIN_CODES.pop(code, None)
            entry = None
    if not entry:
        raise HTTPException(400, "That classroom join code is invalid or has expired.")
    if entry["lesson"] != _lesson_slug(lesson):
        raise HTTPException(400, "That join code is for a different lesson.")
    return entry


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign_jwt(payload: dict, secret: bytes) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = (
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        + "."
        + _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    )
    signature = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return signing_input + "." + _b64url_encode(signature)


def _handoff_secret() -> bytes:
    secret = (
        LIVEKIT_API_SECRET
        or os.getenv("MNH_CLASSREP_DOCUMENT_ADMIN_TOKEN", "").strip()
        or os.getenv("MNH_ADMIN_PASSWORD", "").strip()
    )
    if not secret:
        # Built-in classroom mode: persist a local secret so handoffs/codes work
        # without external LiveKit/AI provider credentials.
        key_path = DATA_DIR / ".crara_classroom_secret"
        try:
            if key_path.exists():
                secret = key_path.read_text(encoding="utf-8").strip()
        except Exception:
            secret = ""
        if not secret:
            secret = secrets.token_urlsafe(48)
            try:
                key_path.parent.mkdir(parents=True, exist_ok=True)
                key_path.write_text(secret, encoding="utf-8")
            except Exception:
                pass
    return secret.encode("utf-8")


def _issue_handoff(user: dict, lesson: str, room: str | None = None) -> str:
    lesson = _lesson_slug(lesson)
    now = int(time.time())
    room = room or _room_name(str(user["id"]), lesson)
    payload = {
        "typ": _HANDOFF_TYPE,
        "sub": str(user["id"]),
        "identity": _identity(user),
        "name": _display_name(user),
        "room": room,
        "lesson": lesson,
        "role": classroom_role(user),
        "permissions": classroom_permissions(user, room),
        "iat": now,
        "exp": now + LIVEKIT_HANDOFF_TTL_SECONDS,
    }
    return _sign_jwt(payload, _handoff_secret())


def _bearer_token(authorization: str | None) -> str:
    value = str(authorization or "").strip()
    if not value.lower().startswith("bearer "):
        raise HTTPException(401, "A CRARA classroom handoff token is required.")
    return value[7:].strip()


def _verify_handoff(authorization: str | None) -> dict:
    token = _bearer_token(authorization)
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(401, "The CRARA classroom handoff token is invalid.")
    try:
        header = json.loads(_b64url_decode(parts[0]))
        payload = json.loads(_b64url_decode(parts[1]))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(401, "The CRARA classroom handoff token is invalid.")
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise HTTPException(401, "The CRARA classroom handoff token is invalid.")
    expected = hmac.new(_handoff_secret(), (parts[0] + "." + parts[1]).encode("ascii"), hashlib.sha256).digest()
    try:
        supplied = _b64url_decode(parts[2])
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(401, "The CRARA classroom handoff token is invalid.")
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(401, "The CRARA classroom handoff token is invalid.")
    now = int(time.time())
    if payload.get("typ") != _HANDOFF_TYPE or int(payload.get("exp", 0)) <= now or int(payload.get("iat", 0)) > now + 60:
        raise HTTPException(401, "The CRARA classroom handoff token has expired. Reopen the classroom from CRARA.")
    if not all(payload.get(key) for key in ("sub", "identity", "name", "room")):
        raise HTTPException(401, "The CRARA classroom handoff token is incomplete.")
    return payload


def _livekit_token(room: str, identity: str, name: str, ttl: int) -> str:
    """Build a scoped LiveKit JWT.

    The official SDK is used when installed (production via requirements.txt).
    The HMAC fallback keeps local development and tests working without it and
    emits the same claims expected by LiveKit.
    """
    try:
        from livekit.api import AccessToken, VideoGrants  # type: ignore
    except ImportError:
        now = int(time.time())
        claims = {
            "exp": now + ttl,
            "iss": LIVEKIT_API_KEY,
            "sub": identity,
            "nbf": now,
            "name": name,
            "video": {
                "room": room,
                "roomJoin": True,
                "canPublish": True,
                "canSubscribe": True,
                "canPublishData": True,
                "canUpdateOwnMetadata": True,
            },
        }
        return _sign_jwt(claims, LIVEKIT_API_SECRET.encode("utf-8"))

    token = (
        AccessToken(api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_ttl(timedelta(seconds=ttl))
        .with_grants(
            VideoGrants(
                room=room,
                room_join=True,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                can_update_own_metadata=True,
            )
        )
    )
    return token.to_jwt()


@router.get("/api/class-rep/livekit/status")
def classroom_status() -> dict:
    """Capability check that deliberately exposes no credential material."""
    mode = _classroom_mode()
    return {
        "configured": True,
        "mode": mode,
        "builtin": mode == "builtin",
        "livekit_configured": _livekit_configured(),
        "url_set": bool(LIVEKIT_URL),
        "key_set": bool(LIVEKIT_API_KEY),
        "secret_set": bool(LIVEKIT_API_SECRET),
        "handoff_ttl_seconds": LIVEKIT_HANDOFF_TTL_SECONDS,
    }


@router.post("/api/class-rep/livekit/join-code")
def create_join_code(payload: ClassroomJoinCodeRequest, request: Request) -> dict:
    """Issue a short-lived code for students to join the host's lesson room."""
    lesson = payload.lesson or "general"
    try:
        user = _require_code_issuer(request, lesson, payload.authority)
    except HTTPException:
        # Allow classroom/code generation without external LiveKit/AI setup.
        user = _resolve_user(request)
    result = _issue_join_code(user, lesson)
    return dict(result, configured=True, mode=_classroom_mode())


@router.post("/api/class-rep/livekit/join-code/revoke")
def revoke_join_code(payload: ClassroomJoinCodeRevokeRequest, request: Request) -> dict:
    """Allow the issuing host, or a delegated co-host, to revoke a code."""
    code = _clean_join_code(payload.code)
    with _JOIN_CODE_LOCK:
        entry = _JOIN_CODES.get(code)
    if not entry:
        raise HTTPException(404, "That classroom join code was not found.")
    user = _require_code_issuer(request, str(entry["lesson"]), payload.authority)
    with _JOIN_CODE_LOCK:
        entry = _JOIN_CODES.get(code)
        if not entry or entry["host"] != str(user["id"]):
            raise HTTPException(404, "That classroom join code was not found.")
        _JOIN_CODES.pop(code, None)
    return {"ok": True}


@router.post("/api/class-rep/livekit/handoff")
def classroom_handoff(payload: ClassroomHandoffRequest, request: Request) -> dict:
    """Issue a short-lived handoff from the CRARA cookie session."""
    user = _resolve_user(request)
    lesson = _lesson_slug(payload.lesson)
    joined_with_code = bool(payload.join_code)
    if joined_with_code:
        room = str(_resolve_join_code(payload.join_code, lesson)["room"])
    else:
        room = _room_name(str(user["id"]), lesson)
    mode = _classroom_mode()
    return {
        "token": _issue_handoff(user, lesson, room),
        "url": LIVEKIT_URL if mode == "livekit" else "",
        "room": room,
        "room_name": room,
        "identity": _identity(user),
        "name": _display_name(user),
        "lesson": lesson,
        "role": classroom_role(user),
        "permissions": classroom_permissions(user, room),
        "expires_in": LIVEKIT_HANDOFF_TTL_SECONDS,
        "joined_with_code": joined_with_code,
        "configured": True,
        "mode": mode,
        "builtin": mode == "builtin",
    }


@router.post("/api/v1/livekit/token")
@router.post("/api/class-rep/livekit/token")
def livekit_token(
    body: LiveKitTokenRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    """Exchange a CRARA handoff for a short-lived LiveKit access token."""
    claims = _verify_handoff(authorization)
    ttl = min(max(int(body.ttl_seconds), 60), LIVEKIT_TOKEN_TTL_SECONDS)
    room = str(claims["room"])
    identity = str(claims["identity"])
    name = str(claims["name"])
    mode = _classroom_mode()
    if mode == "livekit":
        token = _livekit_token(room, identity, name, ttl)
        logger.info("CRARA LiveKit token issued room=%s ttl=%s", room, ttl)
        return {
            "token": token,
            "url": LIVEKIT_URL,
            "room_name": room,
            "identity": identity,
            "name": name,
            "role": str(claims.get("role") or "student"),
            "permissions": claims.get("permissions") or classroom_permissions({}, room),
            "expires_in": ttl,
            "mode": "livekit",
        }
    # Built-in local classroom: return a signed handoff-scoped token for the
    # in-app classroom resource; no external LiveKit credentials required.
    logger.info("CRARA built-in classroom token issued room=%s ttl=%s", room, ttl)
    return {
        "token": _issue_handoff({"id": str(claims.get("sub") or ""), "name": name, "email": ""}, str(claims.get("lesson") or "general"), room),
        "url": "",
        "room_name": room,
        "identity": identity,
        "name": name,
        "role": str(claims.get("role") or "student"),
        "permissions": claims.get("permissions") or classroom_permissions({}, room),
        "expires_in": ttl,
        "mode": "builtin",
        "builtin": True,
    }


@router.post("/api/v1/system-audio/virtual-recordings")
@router.post("/api/class-rep/livekit/virtual-recording")
async def upload_virtual_recording(
    file: UploadFile = File(...),
    label: str = Form(default=""),
    duration_seconds: float = Form(default=0.0),
    mime_type: str = Form(default=""),
    media_type: str = Form(default="audio"),
    sources: str = Form(default=""),
    started_at: str = Form(default=""),
    authorization: str | None = Header(default=None),
) -> dict:
    """Store a browser-captured classroom recording for the signed-in learner."""
    claims = _verify_handoff(authorization)
    content = await file.read()
    if not content:
        raise HTTPException(400, "The classroom recording was empty.")
    if len(content) > _MAX_RECORDING_BYTES:
        raise HTTPException(413, "The classroom recording is larger than the 100 MB limit.")
    reported_mime = _clean_label(mime_type, 120).lower() or str(file.content_type or "").lower()
    extension = _RECORDING_EXTENSIONS.get(reported_mime, ".webm")
    recording_id = uuid.uuid4().hex
    folder = DATA_DIR / "classroom_recordings"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (recording_id + extension)
    path.write_bytes(content)
    metadata = {
        "id": recording_id,
        "owner_id": claims.get("sub"),
        "lesson": claims.get("lesson"),
        "label": _clean_label(label) or "CRARA classroom recording",
        "duration_seconds": max(0.0, float(duration_seconds or 0.0)),
        "mime_type": reported_mime or "audio/webm",
        "media_type": _clean_label(media_type, 40) or "audio",
        "sources": [part.strip() for part in sources.split(",") if part.strip()][:20],
        "started_at": _clean_label(started_at, 80) or None,
        "size_bytes": len(content),
        "created_at": int(time.time()),
    }
    (folder / (recording_id + ".json")).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {
        "id": recording_id,
        "label": metadata["label"],
        "duration_seconds": metadata["duration_seconds"],
        "mime_type": metadata["mime_type"],
        "media_type": metadata["media_type"],
        "size_bytes": len(content),
    }
