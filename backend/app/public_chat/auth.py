"""Identity resolution shared by public chat REST and WebSocket endpoints.

A participant code identifies a chat member; it is never accepted as a
credential from the request body or query string. Identity comes only from the
existing application sessions or a signed, HttpOnly public-chat guest cookie.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from typing import Any

from fastapi import HTTPException

from app.class_rep import memory
from app.services import authentication

PC_GUEST_COOKIE = "mnh_pc_guest"
_GUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,96}$")
_CARA_GUEST_RE = re.compile(r"^guest_[A-Za-z0-9_-]{8,96}$")


def _guest_secret() -> bytes:
    """Derive a stable signing key without introducing a new required secret."""
    material = (
        os.getenv("MNH_PUBLIC_CHAT_SECRET", "").strip()
        or os.getenv("MNH_ADMIN_PASSWORD", "").strip()
        or os.getenv("MNH_ENV", "development").strip()
        or "mnh-public-chat"
    )
    return hashlib.sha256(("mnh-public-chat:" + material).encode("utf-8")).digest()


def make_guest_cookie() -> tuple[str, str]:
    """Return ``(user_id, cookie_value)`` for a new signed guest identity."""
    raw_id = secrets.token_urlsafe(18)
    signature = hmac.new(_guest_secret(), raw_id.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    return "pc_guest_" + raw_id, f"pc_guest_{raw_id}.{signature}"


def resolve_guest_cookie(value: str) -> str | None:
    """Validate a signed public-chat guest cookie and return its user id."""
    token = str(value or "").strip()
    if not token.startswith("pc_guest_"):
        return None
    body, sep, signature = token[len("pc_guest_"):].partition(".")
    if not sep or not _GUEST_ID_RE.fullmatch(body) or not re.fullmatch(r"[a-f0-9]{32}", signature):
        return None
    expected = hmac.new(_guest_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(signature, expected):
        return None
    return "pc_guest_" + body


def resolve_user(request, allow_create_guest: bool = False) -> dict[str, Any]:
    """Resolve a chat user from existing sessions/cookies.

    Works with Starlette ``Request`` and ``WebSocket`` because both expose
    ``.cookies``. No client-supplied participant code is trusted here.
    """
    cookies = getattr(request, "cookies", {}) or {}

    session = authentication.get_session(cookies.get("mnh_session"))
    if session:
        role = str(session.get("role") or "")
        return {
            "id": f"mnh_{role}",
            "name": role.replace("_", " ").title(),
            "email": "",
            "role": role,
            "auth": "mnh_session",
        }

    cara_user = memory.resolve_session(cookies.get("cara_session"))
    if cara_user:
        return {**cara_user, "auth": "cara_session"}

    guest_id = resolve_guest_cookie(cookies.get(PC_GUEST_COOKIE))
    if guest_id:
        return {"id": guest_id, "name": "Guest", "email": "", "guest": True, "auth": "mnh_pc_guest"}

    # Bridge legacy CRARA guest cookies to a stable public-chat identity so the
    # same browser guest can use one MNH-XXXX code across MNH chat and CRARA.
    cara_guest = str(cookies.get("cara_guest") or "").strip()
    if _CARA_GUEST_RE.fullmatch(cara_guest):
        raw = cara_guest[len("guest_"):]
        sig = hmac.new(_guest_secret(), raw.encode("ascii"), hashlib.sha256).hexdigest()[:32]
        user = {
            "id": "pc_guest_" + raw,
            "name": "Guest",
            "email": "",
            "guest": True,
            "auth": "cara_guest_bridge",
        }
        if allow_create_guest:
            user["_new_cookie"] = f"pc_guest_{raw}.{sig}"
        return user

    if allow_create_guest:
        user_id, cookie_value = make_guest_cookie()
        return {
            "id": user_id,
            "name": "Guest",
            "email": "",
            "guest": True,
            "auth": "mnh_pc_guest",
            "_new_cookie": cookie_value,
        }

    raise HTTPException(401, "Sign in to use public chat.")


def set_guest_cookie(response, request, user: dict[str, Any]) -> None:
    """Attach the signed guest cookie to a response when one was created."""
    cookie_value = str(user.get("_new_cookie") or "")
    if not cookie_value:
        return
    response.set_cookie(
        PC_GUEST_COOKIE,
        cookie_value,
        httponly=True,
        samesite="lax",
        secure=getattr(request.url, "scheme", "http") == "https",
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
