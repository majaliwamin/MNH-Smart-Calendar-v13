from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import JSONResponse

from . import (auth, cleanup, media, moderation, notifications, permissions,
               reactions, service, settings, store, websocket as chat_ws)
from .schemas import (
    AccessDecisionRequest, JoinRequest, MessageCreateRequest, MessageEditRequest,
    ModerationRequest, PreferencesRequest, ReactionRequest, ReadRequest,
    ReportRequest, RestrictRequest, RoleRequest,
)

router = APIRouter(prefix="/api/public-chat", tags=["Public Chat"])


def _user(request: Request, allow_guest: bool = False) -> dict[str, Any]:
    return auth.resolve_user(request, allow_create_guest=allow_guest)


def _require_moderator(user: dict[str, Any]) -> None:
    if not permissions.can_moderate(user):
        raise HTTPException(403, "Moderator access is required.")


def _status_payload(user: dict[str, Any], joined: bool) -> dict[str, Any]:
    participant = store.get_participant(user, include_pending=True)
    return {
        "authenticated": True,
        "joined": joined,
        "participant": service.participant_payload(participant),
        "access_request": service.access_status(user),
        "retention_days": settings.RETENTION_DAYS,
        "retention_notice": "Public chat messages are cleared automatically after 7 days.",
        "participants": service.public_participants() if joined else [],
    }


def _json_with_guest(request: Request, user: dict[str, Any], payload: dict[str, Any]) -> JSONResponse:
    response = JSONResponse(payload)
    auth.set_guest_cookie(response, request, user)
    return response


@router.get("/status")
def status(request: Request):
    user = _user(request, allow_guest=True)
    participant = store.get_participant(user)
    return _json_with_guest(request, user, _status_payload(user, bool(participant)))


@router.post("/join")
async def join(payload: JoinRequest, request: Request):
    user = _user(request, allow_guest=True)
    result = service.join_chat(user, payload.display_name, payload.code, payload.request_new)
    response = _json_with_guest(request, user, result)
    if result.get("joined") and result.get("participant"):
        await chat_ws.broadcast({"type": "participant.joined", "participant": result["participant"]})
        chat_ws.dispatch_to_users(
            notifications.access_event("access", "Your public chat access is ready.", {str(user.get("id") or "")}),
            {str(user.get("id") or "")},
        )
    else:
        chat_ws.dispatch_to_users(
            notifications.access_event("access", "Your chat access request is awaiting approval.", {str(user.get("id") or "")}),
            {str(user.get("id") or "")},
        )
    return response


@router.get("/access-request")
def access_request_status(request: Request):
    return service.access_status(_user(request))


@router.delete("/access-request")
def access_request_cancel(request: Request):
    return service.cancel_access_request(_user(request))


@router.get("/admin/access-requests")
def admin_access_requests(request: Request):
    _require_moderator(_user(request))
    return {"requests": service.pending_access_requests()}


@router.post("/admin/access-requests/{user_id}/decision")
async def admin_access_decision(user_id: str, payload: AccessDecisionRequest, request: Request):
    user = _user(request)
    result = service.decide_access_request(user_id, payload.approved, user, payload.note)
    chat_ws.dispatch_to_users(
        notifications.access_event(
            "access",
            "Your public chat access request was approved." if payload.approved else "Your public chat access request was not approved.",
            {user_id},
        ),
        {user_id},
    )
    return result


@router.get("/participants")
def participants(request: Request):
    store.require_participant(_user(request))
    return {"participants": service.public_participants()}


@router.get("/messages")
def messages(request: Request, limit: int = 100, before: int | None = None):
    user = _user(request)
    participant = store.require_participant(user)
    return {"messages": store.list_messages(participant, limit=limit, before_ms=before,
                                            blocked_codes=service.blocked_codes(user))}


@router.get("/search")
def search_messages(request: Request, q: str = "", limit: int = 50):
    user = _user(request)
    participant = store.require_participant(user)
    query = str(q or "").strip()
    if not query or len(query) > 200:
        raise HTTPException(400, "Enter a search term of 200 characters or fewer.")
    return {"messages": store.list_messages(participant, limit=limit, query=query,
                                            blocked_codes=service.blocked_codes(user))}


@router.post("/messages")
async def post_message(payload: MessageCreateRequest, request: Request):
    user = _user(request)
    service.check_rate(user, "message")
    message = store.create_message(
        user,
        text=payload.text,
        reply_to_id=payload.reply_to_id,
        private_recipient_code=payload.private_recipient_code,
        mention_codes=payload.mention_codes,
    )
    await chat_ws.broadcast({"type": "message.created", "message": message})
    notifications.dispatch_for_message(message, chat_ws.dispatch_to_users)
    return {"message": message}


@router.put("/messages/{message_id}")
async def put_message(message_id: str, payload: MessageEditRequest, request: Request):
    user = _user(request)
    message = store.edit_message(user, message_id, payload.text)
    await chat_ws.broadcast({"type": "message.updated", "message": message})
    return {"message": message}


@router.delete("/messages/{message_id}")
async def remove_message(message_id: str, request: Request, mode: str = "me"):
    user = _user(request)
    result = store.delete_message(user, message_id, mode=mode)
    if result.get("action") == "deleted_for_all":
        await chat_ws.broadcast({"type": "message.deleted", "message": result["message"]})
    else:
        chat_ws.dispatch_to_users([{"type": "message.updated", "message": result["message"]}], {str(user.get("id") or "")})
    return result


@router.post("/messages/{message_id}/reactions")
async def toggle_reaction(message_id: str, payload: ReactionRequest, request: Request):
    user = _user(request)
    result = reactions.toggle_reaction(user, message_id, payload.emoji)
    await chat_ws.broadcast({"type": "message.reaction", **result})
    return result


@router.post("/reports")
def report_message(payload: ReportRequest, request: Request):
    return moderation.report_message(_user(request), payload.message_id, payload.category, payload.reason)


@router.get("/admin/reports")
def admin_reports(request: Request, status: str = ""):
    return {"reports": moderation.list_reports(_user(request), status)}


@router.post("/admin/reports/{report_id}/resolve")
async def admin_resolve_report(report_id: str, payload: ModerationRequest, request: Request):
    user = _user(request)
    result = moderation.resolve_report(user, report_id, payload.action, payload.note)
    await chat_ws.broadcast({"type": "moderation.action", **result})
    return result


@router.get("/admin/moderation")
def admin_moderation_history(request: Request):
    return {"actions": moderation.moderation_history(_user(request))}


@router.post("/admin/participants/{code}/status")
async def admin_participant_status(code: str, payload: RestrictRequest, request: Request):
    user = _user(request)
    result = moderation.restrict_participant(user, code, payload.status)
    await chat_ws.broadcast({"type": "moderation.membership", **result})
    return result


@router.post("/admin/participants/{code}/role")
async def admin_participant_role(code: str, payload: RoleRequest, request: Request):
    user = _user(request)
    result = moderation.set_member_role(user, code, payload.role)
    await chat_ws.broadcast({"type": "moderation.membership", **result})
    return result


@router.get("/blocks")
def moderation_lists(request: Request):
    return moderation.moderation_lists(_user(request))


@router.post("/blocks/{code}")
def block_participant(code: str, request: Request):
    return moderation.block_participant(_user(request), code)


@router.delete("/blocks/{code}")
def unblock_participant(code: str, request: Request):
    return moderation.unblock_participant(_user(request), code)


@router.post("/mutes/{code}")
def mute_participant(code: str, request: Request):
    return moderation.mute_participant(_user(request), code)


@router.delete("/mutes/{code}")
def unmute_participant(code: str, request: Request):
    return moderation.unmute_participant(_user(request), code)


@router.post("/voice-notes")
async def upload_voice_note(request: Request, file: UploadFile = File(...)):
    user = _user(request)
    service.check_rate(user, "upload")
    form = await request.form()
    reply_to_id = str(form.get("reply_to_id") or "").strip() or None
    private_recipient_code = str(form.get("private_recipient_code") or "").strip() or None
    mention_codes = [c.strip() for c in str(form.get("mention_codes") or "").split(",") if c.strip()]
    try:
        duration_ms = int(str(form.get("duration_ms") or "0").strip() or 0)
    except Exception:
        duration_ms = 0
    audio = await store.save_audio_upload_async(user, file, duration_ms=duration_ms)
    message = store.create_message(user, text="", reply_to_id=reply_to_id,
                                   private_recipient_code=private_recipient_code,
                                   mention_codes=mention_codes, audio=audio)
    await chat_ws.broadcast({"type": "message.created", "message": message})
    notifications.dispatch_for_message(message, chat_ws.dispatch_to_users)
    return {"message": message}


@router.post("/attachments")
async def upload_attachment(request: Request, file: UploadFile = File(...)):
    user = _user(request)
    service.check_rate(user, "upload")
    form = await request.form()
    reply_to_id = str(form.get("reply_to_id") or "").strip() or None
    private_recipient_code = str(form.get("private_recipient_code") or "").strip() or None
    mention_codes = [c.strip() for c in str(form.get("mention_codes") or "").split(",") if c.strip()]
    text = str(form.get("text") or "").strip()
    view_once = str(form.get("view_once") or "").strip().lower() in {"1", "true", "yes", "on"}
    attachment = store.save_attachment_upload(user, file)
    message = store.create_message(user, text=text, reply_to_id=reply_to_id,
                                   private_recipient_code=private_recipient_code,
                                   mention_codes=mention_codes, attachments=[attachment],
                                   view_once=view_once)
    await chat_ws.broadcast({"type": "message.created", "message": message})
    notifications.dispatch_for_message(message, chat_ws.dispatch_to_users)
    return {"message": message}


@router.get("/media/{file_id}")
def get_media(file_id: str, request: Request):
    return media.media_response(_user(request), file_id)


@router.get("/unread")
def unread(request: Request):
    return service.unread_summary(_user(request))


@router.post("/read")
def mark_read(payload: ReadRequest, request: Request):
    return service.mark_read(_user(request), payload.at)


@router.get("/preferences")
def get_preferences(request: Request):
    return {"values": service.notification_preferences(_user(request))}


@router.put("/preferences")
def put_preferences(payload: PreferencesRequest, request: Request):
    return {"values": service.set_notification_preferences(_user(request), payload.values)}


@router.get("/cleanup/status")
def cleanup_status(request: Request):
    _require_moderator(_user(request))
    return cleanup.cleanup_status()


@router.post("/cleanup/run")
def cleanup_run(request: Request):
    _require_moderator(_user(request))
    return cleanup.run_cleanup()


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await chat_ws.websocket_endpoint(websocket)


def run_retention_cleanup() -> dict:
    return cleanup.run_cleanup()
