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
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.class_rep import memory
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


class LiveKitTokenRequest(BaseModel):
    # The embedded classroom sends these for API compatibility. Room and
    # identity are intentionally re-derived from the signed handoff instead of
    # trusting client-supplied values.
    room_name: str | None = None
    identity: str | None = None
    name: str | None = None
    ttl_seconds: int = 3600


def _configured() -> bool:
    return bool(LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET)


def _require_configured() -> None:
    if not _configured():
        raise HTTPException(
            503,
            "The CRARA one-to-one classroom is not configured. Ask an administrator to set the LiveKit URL and API credentials.",
        )


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
        raise HTTPException(
            503,
            "The CRARA one-to-one classroom is not configured. Ask an administrator to set the LiveKit credentials.",
        )
    return secret.encode("utf-8")


def _issue_handoff(user: dict, lesson: str) -> str:
    lesson = _lesson_slug(lesson)
    now = int(time.time())
    payload = {
        "typ": _HANDOFF_TYPE,
        "sub": str(user["id"]),
        "identity": _identity(user),
        "name": _display_name(user),
        "room": _room_name(str(user["id"]), lesson),
        "lesson": lesson,
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
    return {
        "configured": _configured(),
        "url_set": bool(LIVEKIT_URL),
        "key_set": bool(LIVEKIT_API_KEY),
        "secret_set": bool(LIVEKIT_API_SECRET),
        "handoff_ttl_seconds": LIVEKIT_HANDOFF_TTL_SECONDS,
    }


@router.post("/api/class-rep/livekit/handoff")
def classroom_handoff(payload: ClassroomHandoffRequest, request: Request) -> dict:
    """Issue a short-lived handoff from the CRARA cookie session."""
    _require_configured()
    user = _resolve_user(request)
    lesson = _lesson_slug(payload.lesson)
    return {
        "token": _issue_handoff(user, lesson),
        "url": LIVEKIT_URL,
        "room": _room_name(str(user["id"]), lesson),
        "room_name": _room_name(str(user["id"]), lesson),
        "identity": _identity(user),
        "name": _display_name(user),
        "lesson": lesson,
        "expires_in": LIVEKIT_HANDOFF_TTL_SECONDS,
        "configured": True,
    }


@router.post("/api/v1/livekit/token")
@router.post("/api/class-rep/livekit/token")
def livekit_token(
    body: LiveKitTokenRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    """Exchange a CRARA handoff for a short-lived LiveKit access token."""
    _require_configured()
    claims = _verify_handoff(authorization)
    ttl = min(max(int(body.ttl_seconds), 60), LIVEKIT_TOKEN_TTL_SECONDS)
    room = str(claims["room"])
    identity = str(claims["identity"])
    name = str(claims["name"])
    token = _livekit_token(room, identity, name, ttl)
    logger.info("CRARA LiveKit token issued room=%s ttl=%s", room, ttl)
    return {
        "token": token,
        "url": LIVEKIT_URL,
        "room_name": room,
        "identity": identity,
        "name": name,
        "expires_in": ttl,
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
