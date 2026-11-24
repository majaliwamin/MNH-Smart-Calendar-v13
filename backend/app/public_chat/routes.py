from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from app.class_rep import memory
from app.services import authentication

from .schemas import JoinRequest, MessageCreateRequest, MessageEditRequest
from .store import (
    PUBLIC_RETENTION_SECONDS,
    COL_PARTICIPANTS,
    can_access_media,
    cleanup_public_retention,
    create_message,
    delete_message,
    edit_message,
    ensure_participant,
    get_media_path,
    get_participant,
    list_messages,
    participant_by_code,
    require_participant,
    save_audio_upload,
    _list,
    _message_doc,
    _message_visible,
    _serialize_message,
)

router = APIRouter(prefix="/api/public-chat", tags=["Public Chat"])
def _read_raw_message(message_id: str) -> dict | None:
    return _message_doc(message_id)


def _message_visible_raw(msg: dict, viewer: dict) -> bool:
    return _message_visible(msg, viewer)


def _serialize_raw_for_viewer(msg: dict, viewer: dict) -> dict:
    return _serialize_message(msg, viewer)



_WS_LOCK = asyncio.Lock()
_WS_CLIENTS: dict[WebSocket, dict[str, Any]] = {}


async def _broadcast(event: dict) -> None:
    """Broadcast event. For message events, filter private messages per viewer."""
    async with _WS_LOCK:
        clients = list(_WS_CLIENTS.items())
    stale = []
    for ws, info in clients:
        try:
            payload = event
            if event.get("type", "").startswith("message.") and isinstance(event.get("message"), dict):
                msg = event["message"]
                # Re-fetch and serialize per viewer to enforce private visibility.
                viewer = info.get("participant") or {}
                raw = _read_raw_message(str(msg.get("id") or ""))
                if raw:
                    if not _message_visible_raw(raw, viewer):
                        continue
                    payload = {**event, "message": _serialize_raw_for_viewer(raw, viewer)}
                else:
                    # deleted/expired
                    if str(msg.get("kind")) == "private":
                        continue
            await ws.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception:
            stale.append(ws)
    if stale:
        async with _WS_LOCK:
            for ws in stale:
                _WS_CLIENTS.pop(ws, None)


PC_GUEST_COOKIE = "mnh_pc_guest"
PC_GUEST_RE = re.compile(r"^pc_guest_[A-Za-z0-9_-]{8,96}$")


def _ensure_guest_cookie(request: Request, response=None) -> str | None:
    gid = str(request.cookies.get(PC_GUEST_COOKIE) or "").strip()
    if PC_GUEST_RE.fullmatch(gid):
        return gid
    return None


def _resolve_user(request: Request, allow_create_guest: bool = False) -> dict[str, Any]:
    token = request.cookies.get("mnh_session")
    session = authentication.get_session(token)
    if session:
        role = str(session.get("role") or "")
        return {
            "id": f"mnh_{role}",
            "name": role.replace("_", " ").title(),
            "email": "",
            "role": role,
            "auth": "mnh_session",
        }
    cara_user = memory.resolve_session(request.cookies.get("cara_session"))
    if cara_user:
        return {**cara_user, "auth": "cara_session"}
    guest = str(request.cookies.get("cara_guest") or "").strip()
    if re.fullmatch(r"guest_[A-Za-z0-9_-]{8,96}", guest):
        return {"id": guest, "name": "Guest", "email": "", "guest": True, "auth": "cara_guest"}
    pc_guest = str(request.cookies.get(PC_GUEST_COOKIE) or "").strip()
    if PC_GUEST_RE.fullmatch(pc_guest):
        return {"id": pc_guest, "name": "Guest", "email": "", "guest": True, "auth": "mnh_pc_guest"}
    if allow_create_guest:
        import secrets
        gid = "pc_guest_" + secrets.token_urlsafe(18)
        return {"id": gid, "name": "Guest", "email": "", "guest": True, "auth": "mnh_pc_guest", "_new_cookie": gid}
    raise HTTPException(401, "Sign in to use public chat.")


def _public_participant_payload(p: dict | None) -> dict | None:
    if not p:
        return None
    return {
        "code": str(p.get("code") or ""),
        "display_name": str(p.get("display_name") or ""),
        "public_identity": str(p.get("public_identity") or ""),
    }


def _participants_payload() -> list[dict]:
    items = []
    for p in _list(COL_PARTICIPANTS, 1000):
        if str(p.get("status") or "active") != "active":
            continue
        code = str(p.get("code") or "")
        if not re.fullmatch(r"MNH-\d{4}", code):
            continue
        items.append({
            "code": code,
            "display_name": str(p.get("display_name") or ""),
            "public_identity": str(p.get("public_identity") or ""),
        })
    items.sort(key=lambda x: x["code"])
    return items


@router.get("/status")
def status(request: Request):
    user = _resolve_user(request, allow_create_guest=True)
    participant = get_participant(user)
    data = {
        "authenticated": True,
        "joined": bool(participant),
        "participant": _public_participant_payload(participant),
        "retention_days": 7,
        "retention_notice": "Public chat messages are cleared automatically after 7 days.",
        "participants": _participants_payload() if participant else [],
    }
    resp = JSONResponse(data)
    if user.get("_new_cookie"):
        resp.set_cookie(PC_GUEST_COOKIE, user["_new_cookie"], httponly=True, samesite="lax", secure=request.url.scheme=="https", max_age=60*60*24*30, path="/")
    return resp


@router.post("/join")
async def join(payload: JoinRequest, request: Request):
    from fastapi.responses import JSONResponse
    user = _resolve_user(request, allow_create_guest=True)
    participant = ensure_participant(user, payload.display_name)
    data = {
        "joined": True,
        "participant": _public_participant_payload(participant),
        "retention_days": 7,
        "retention_notice": "Public chat messages are cleared automatically after 7 days.",
        "participants": _participants_payload(),
    }
    resp = JSONResponse(data)
    if user.get("_new_cookie"):
        resp.set_cookie(PC_GUEST_COOKIE, user["_new_cookie"], httponly=True, samesite="lax", secure=request.url.scheme=="https", max_age=60*60*24*30, path="/")
    await _broadcast({"type": "participant.joined", "participant": data["participant"]})
    return resp


@router.get("/participants")
def participants(request: Request):
    user = _resolve_user(request)
    require_participant(user)
    return {"participants": _participants_payload()}


@router.get("/messages")
def messages(request: Request, limit: int = 100, before: int | None = None):
    user = _resolve_user(request)
    participant = require_participant(user)
    return {"messages": list_messages(participant, limit=limit, before_ms=before)}


@router.post("/messages")
async def post_message(payload: MessageCreateRequest, request: Request):
    user = _resolve_user(request)
    msg = create_message(
        user,
        text=payload.text,
        reply_to_id=payload.reply_to_id,
        private_recipient_code=payload.private_recipient_code,
        mention_codes=payload.mention_codes,
    )
    await _broadcast({"type": "message.created", "message": msg})
    return {"message": msg}


@router.put("/messages/{message_id}")
async def put_message(message_id: str, payload: MessageEditRequest, request: Request):
    user = _resolve_user(request)
    msg = edit_message(user, message_id, payload.text)
    await _broadcast({"type": "message.updated", "message": msg})
    return {"message": msg}


@router.delete("/messages/{message_id}")
async def remove_message(message_id: str, request: Request):
    user = _resolve_user(request)
    msg = delete_message(user, message_id)
    await _broadcast({"type": "message.deleted", "message": msg})
    return {"message": msg}


@router.post("/voice-notes")
async def upload_voice_note(request: Request, file: UploadFile = File(...)):
    user = _resolve_user(request)
    # parse optional form fields
    form = await request.form()
    reply_to_id = str(form.get("reply_to_id") or "").strip() or None
    private_recipient_code = str(form.get("private_recipient_code") or "").strip() or None
    mention_codes = [c.strip() for c in str(form.get("mention_codes") or "").split(",") if c.strip()]
    audio = save_audio_upload(user, file)
    msg = create_message(user, text="", reply_to_id=reply_to_id, private_recipient_code=private_recipient_code, mention_codes=mention_codes, audio=audio)
    await _broadcast({"type": "message.created", "message": msg})
    return {"message": msg}


@router.get("/media/{file_id}")
def get_media(file_id: str, request: Request):
    user = _resolve_user(request)
    if not can_access_media(user, file_id):
        raise HTTPException(404, "Media not found.")
    path = get_media_path(file_id)
    if not path:
        raise HTTPException(404, "Media not found.")
    return FileResponse(path, media_type=None, filename=path.name, headers={"Cache-Control": "private, no-store"})


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    # WebSocket auth via cookies; accept first then validate.
    await websocket.accept()
    try:
        # Build a fake Request-like cookie read through websocket.cookies.
        token = websocket.cookies.get("mnh_session")
        session = authentication.get_session(token)
        if session:
            role = str(session.get("role") or "")
            user = {"id": f"mnh_{role}", "name": role.replace("_", " ").title(), "email": "", "role": role}
        else:
            cara_user = memory.resolve_session(websocket.cookies.get("cara_session"))
            if cara_user:
                user = cara_user
            else:
                guest = str(websocket.cookies.get("cara_guest") or websocket.cookies.get(PC_GUEST_COOKIE) or "").strip()
                if re.fullmatch(r"(?:guest|pc_guest)_[A-Za-z0-9_-]{8,96}", guest):
                    user = {"id": guest, "name": "Guest", "email": "", "guest": True}
                else:
                    await websocket.send_text(json.dumps({"type": "error", "error": "Authentication required."}))
                    await websocket.close(code=4401)
                    return
        participant = get_participant(user)
        async with _WS_LOCK:
            _WS_CLIENTS[websocket] = {"user_id": str(user.get("id") or ""), "participant": participant or {}}
        await websocket.send_text(json.dumps({
            "type": "hello",
            "joined": bool(participant),
            "participant": _public_participant_payload(participant),
            "retention_days": 7,
        }, ensure_ascii=False))
        while True:
            # Keepalive / ignore client pings; clients receive broadcasts.
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        async with _WS_LOCK:
            _WS_CLIENTS.pop(websocket, None)


def run_retention_cleanup() -> dict:
    return cleanup_public_retention()