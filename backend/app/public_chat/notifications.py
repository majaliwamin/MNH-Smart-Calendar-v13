"""In-app chat notifications built on the existing WebSocket/unread path.

MNH Calendar-v13 has no browser push or mail notification channel. This module
delivers targeted in-app events and respects each member's preferences and
muted/blocked participants without creating a second notification system.
"""
from __future__ import annotations

from typing import Any, Callable

from . import models, service, store

_PREFERENCE_FOR_KIND = {
    "reply": "replies",
    "mention": "mentions",
    "private_reply": "private",
    "access": "access",
    "moderation": "moderation",
}


def targets_for_message(message: dict[str, Any]) -> set[str]:
    """Return user ids that should be notified about a newly created message."""
    sender_uid = str(message.get("sender_user_id") or "")
    sender_code = str(message.get("sender_code") or "")
    if message.get("kind") == "private":
        # Private previews must never reach a mentioned or quoted third party.
        uid = str(message.get("private_recipient_user_id") or "")
        return {uid} if uid and uid != sender_uid else set()
    targets: set[str] = set()
    for code in message.get("mentions") or []:
        participant = store.participant_by_code(str(code))
        uid = str((participant or {}).get("user_id") or "")
        if uid and uid != sender_uid:
            targets.add(uid)
    reply = message.get("reply_to") if isinstance(message.get("reply_to"), dict) else None
    if reply:
        code = str(reply.get("sender_code") or "")
        if code and code != sender_code:
            participant = store.participant_by_code(code)
            uid = str((participant or {}).get("user_id") or "")
            if uid and uid != sender_uid:
                targets.add(uid)
    return targets


def notification_event(message: dict[str, Any], kind: str) -> dict[str, Any]:
    label = {
        "reply": "New reply",
        "mention": "You were mentioned",
        "private_reply": "New private reply",
    }.get(kind, "New chat activity")
    return {
        "type": "notification",
        "kind": kind,
        "label": label,
        "sender_identity": str(message.get("sender_identity") or message.get("sender_code") or ""),
        "preview": str(message.get("text") or "")[:120] or "Voice note or attachment",
        "message_id": str(message.get("id") or ""),
        "kind_of_message": str(message.get("kind") or "public"),
    }


def dispatch(event: dict[str, Any], targets: set[str], send_to_users: Callable[[dict[str, Any], set[str]], None]) -> None:
    """Send a targeted notification only to users who allow that event type."""
    kind = str(event.get("kind") or "reply")
    preference_key = _PREFERENCE_FOR_KIND.get(kind, "replies")
    allowed: set[str] = set()
    for uid in targets:
        if not uid:
            continue
        fake_user = {"id": uid}
        try:
            prefs = service.notification_preferences(fake_user)
            blocked = service.blocked_codes(fake_user)
        except Exception:
            continue
        if not prefs.get(preference_key, True):
            continue
        sender_code = str(event.get("sender_code") or "")
        if sender_code and sender_code in blocked:
            continue
        allowed.add(uid)
    if allowed:
        send_to_users(event, allowed)


def dispatch_for_message(message: dict[str, Any], send_to_users: Callable[[dict[str, Any], set[str]], None]) -> None:
    sender_code = str(message.get("sender_code") or "")
    targets = targets_for_message(message)
    if not targets:
        return
    if message.get("kind") == "private":
        kinds = {"private_reply"}
    else:
        kinds = set()
        if any(store.CODE_RE.fullmatch(str(code)) and store.participant_by_code(str(code)) for code in (message.get("mentions") or [])):
            kinds.add("mention")
        if (message.get("reply_to") or {}).get("id"):
            kinds.add("reply")
    for kind in kinds:
        event = notification_event(message, kind)
        event["sender_code"] = sender_code
        dispatch(event, targets, send_to_users)


def access_event(kind: str, message: str, target_user_ids: set[str]) -> dict[str, Any]:
    return {
        "type": "notification",
        "kind": kind,
        "label": "Chat access update",
        "preview": str(message or "")[:200],
        "message_id": "",
        "sender_code": "",
    }


def send_access_notification(event: dict[str, Any], targets: set[str],
                             send_to_users: Callable[[dict[str, Any], set[str]], None]) -> None:
    dispatch(event, targets, send_to_users)
