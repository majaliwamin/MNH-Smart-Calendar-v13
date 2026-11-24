"""Reporting, member restrictions, and moderation audit records."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException

from . import models, permissions, service, settings, store


def _require_moderator(user: dict[str, Any]) -> None:
    if not permissions.can_moderate(user):
        raise HTTPException(403, "Moderator access is required.")


def report_message(user: dict[str, Any], message_id: str, category: str, reason: str = "") -> dict[str, Any]:
    service.check_rate(user, "report")
    participant = store.require_participant(user)
    message = store._message_doc(message_id)
    if not message or not store._message_visible(message, participant, service.blocked_codes(user)):
        raise HTTPException(404, "Message not found.")
    category = str(category or "").strip().lower()
    if category not in settings.ALLOWED_REPORT_CATEGORIES:
        raise HTTPException(400, "Choose a valid report category.")
    report_id = uuid.uuid4().hex
    now = store._now()
    doc = {
        "id": report_id,
        "message_id": message_id,
        "message_kind": str(message.get("kind") or "public"),
        "reporter_user_id": str(user.get("id") or ""),
        "reporter_code": str(participant.get("code") or ""),
        "offender_code": str(message.get("sender_code") or ""),
        "offender_user_id": str(message.get("sender_user_id") or ""),
        "category": category,
        "reason": str(reason or "")[:1000],
        "status": "open",
        "created_at": now,
        "updated_at": now,
    }
    store._write(models.COL_REPORTS, report_id, doc)
    return {"ok": True, "report_id": report_id, "status": "open"}


def list_reports(user: dict[str, Any], status: str = "") -> list[dict[str, Any]]:
    _require_moderator(user)
    wanted = str(status or "").strip().lower()
    items = []
    for doc in store._list(models.COL_REPORTS, 500):
        if wanted and str(doc.get("status") or "") != wanted:
            continue
        items.append({
            "id": str(doc.get("id") or ""),
            "message_id": str(doc.get("message_id") or ""),
            "category": str(doc.get("category") or ""),
            "reason": str(doc.get("reason") or ""),
            "status": str(doc.get("status") or ""),
            "reporter_code": str(doc.get("reporter_code") or ""),
            "created_at": int(doc.get("created_at") or 0),
        })
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items


def _audit(user: dict[str, Any], action: str, target: str, details: str) -> None:
    store._write(models.COL_MODERATION, uuid.uuid4().hex, {
        "action": action,
        "target": target,
        "details": str(details)[:500],
        "moderator_user_id": str(user.get("id") or ""),
        "created_at": store._now(),
    })


def resolve_report(user: dict[str, Any], report_id: str, action: str, note: str = "") -> dict[str, Any]:
    _require_moderator(user)
    report = store._read(models.COL_REPORTS, report_id)
    if not report:
        raise HTTPException(404, "Report not found.")
    if str(report.get("status") or "") != "open":
        raise HTTPException(400, "This report has already been resolved.")
    action = str(action or "").strip().lower()
    if action not in {"dismiss", "delete_message", "warn", "suspend"}:
        raise HTTPException(400, "Unsupported moderation action.")
    report["status"] = "resolved"
    report["resolution"] = action
    report["resolution_note"] = str(note or "")[:500]
    report["resolved_by"] = str(user.get("id") or "")
    report["resolved_at"] = store._now()
    report["updated_at"] = report["resolved_at"]
    store._write(models.COL_REPORTS, report_id, report)
    _audit(user, action, str(report.get("message_id") or report_id), note)

    if action == "delete_message":
        store.delete_message(user, str(report.get("message_id") or ""))
    elif action == "suspend":
        # Suspend the reported message's sender, never the person who reported it.
        code = str(report.get("offender_code") or "")
        target = store.participant_by_code(code) or {}
        uid = str(target.get("user_id") or report.get("offender_user_id") or "")
        if uid:
            doc = store._read(models.COL_PARTICIPANTS, uid) or {}
            doc["status"] = models.MEMBER_STATUS_SUSPENDED
            doc["updated_at"] = store._now_s()
            store._write(models.COL_PARTICIPANTS, uid, doc)
    return {"ok": True, "status": "resolved", "action": action}


def moderation_history(user: dict[str, Any]) -> list[dict[str, Any]]:
    _require_moderator(user)
    items = []
    for doc in store._list(models.COL_MODERATION, 500):
        items.append({
            "action": str(doc.get("action") or ""),
            "target": str(doc.get("target") or ""),
            "details": str(doc.get("details") or ""),
            "moderator_user_id": str(doc.get("moderator_user_id") or ""),
            "created_at": int(doc.get("created_at") or 0),
        })
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items


def restrict_participant(user: dict[str, Any], code: str, status: str) -> dict[str, Any]:
    _require_moderator(user)
    participant = store.participant_by_code(code, include_inactive=True)
    if not participant:
        raise HTTPException(404, "Participant not found.")
    status = str(status or "").strip().lower()
    if status not in {models.MEMBER_STATUS_ACTIVE, models.MEMBER_STATUS_SUSPENDED}:
        raise HTTPException(400, "Unsupported membership status.")
    uid = str(participant.get("user_id") or "")
    participant["status"] = status
    participant["updated_at"] = store._now_s()
    store._write(models.COL_PARTICIPANTS, uid, participant)
    if status == models.MEMBER_STATUS_ACTIVE:
        request = store._read(models.COL_ACCESS_REQUESTS, uid) or {}
        if request and str(request.get("status") or "") != "approved":
            request["status"] = "approved"
            request["decision"] = "moderator"
            request["decided_by"] = str(user.get("id") or "")
            request["decided_at"] = store._now_s()
            request["updated_at"] = request["decided_at"]
            store._write(models.COL_ACCESS_REQUESTS, uid, request)
    _audit(user, "set_membership_" + status, str(participant.get("code") or ""), "")
    return {"ok": True, "code": str(participant.get("code") or ""), "status": status}


def set_member_role(user: dict[str, Any], code: str, role: str) -> dict[str, Any]:
    _require_moderator(user)
    participant = store.participant_by_code(code)
    if not participant:
        raise HTTPException(404, "Participant not found.")
    role = str(role or "").strip().lower()
    if role not in {models.ROLE_MEMBER, models.ROLE_MODERATOR, models.ROLE_ADMIN}:
        raise HTTPException(400, "Unsupported chat role.")
    participant["role"] = role
    participant["updated_at"] = store._now_s()
    store._write(models.COL_PARTICIPANTS, str(participant.get("user_id") or ""), participant)
    _audit(user, "set_role_" + role, str(participant.get("code") or ""), "")
    return {"ok": True, "code": str(participant.get("code") or ""), "role": role}


def _update_code_list(user: dict[str, Any], field: str, code: str, remove: bool) -> dict[str, Any]:
    store.require_participant(user)
    code = str(code or "").strip().upper()
    if not store.CODE_RE.fullmatch(code) or not store.participant_by_code(code):
        raise HTTPException(404, "Participant not found.")
    if code == str(store.require_participant(user).get("code") or ""):
        raise HTTPException(400, "You cannot block or mute yourself.")
    uid = str(user.get("id") or "")
    doc = store._read(models.COL_BLOCKS, uid) or {"user_id": uid, "blocked_codes": [], "muted_codes": []}
    values = doc.get(field) if isinstance(doc.get(field), list) else []
    values = [str(x) for x in values if store.CODE_RE.fullmatch(str(x))]
    if remove:
        values = [x for x in values if x != code]
    elif code not in values:
        values.append(code)
    doc[field] = values
    doc["updated_at"] = store._now_s()
    store._write(models.COL_BLOCKS, uid, doc)
    return {"ok": True, "code": code, "removed": remove}


def block_participant(user: dict[str, Any], code: str) -> dict[str, Any]:
    return _update_code_list(user, "blocked_codes", code, False)


def unblock_participant(user: dict[str, Any], code: str) -> dict[str, Any]:
    return _update_code_list(user, "blocked_codes", code, True)


def mute_participant(user: dict[str, Any], code: str) -> dict[str, Any]:
    return _update_code_list(user, "muted_codes", code, False)


def unmute_participant(user: dict[str, Any], code: str) -> dict[str, Any]:
    return _update_code_list(user, "muted_codes", code, True)


def moderation_lists(user: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "blocked": sorted(service.blocked_codes(user)),
        "muted": sorted(service.muted_codes(user)),
    }
