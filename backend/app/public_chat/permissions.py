"""Server-side authorization helpers for the native public chat."""
from __future__ import annotations

from typing import Any

MODERATOR_ROLES = {"administrator", "hod", "coordinator", "executive_dean"}


def is_moderator(user: dict[str, Any] | None) -> bool:
    return str((user or {}).get("role") or "").strip().lower() in MODERATOR_ROLES


def can_edit_message(user: dict[str, Any], message: dict[str, Any]) -> bool:
    return str(message.get("sender_user_id") or "") == str(user.get("id") or "")


def can_delete_message(user: dict[str, Any], message: dict[str, Any]) -> bool:
    return can_edit_message(user, message) or is_moderator(user)


def can_access_private_message(user: dict[str, Any], message: dict[str, Any]) -> bool:
    uid = str(user.get("id") or "")
    if not uid:
        return False
    return uid in {
        str(message.get("sender_user_id") or ""),
        str(message.get("private_recipient_user_id") or ""),
    }


def can_moderate(user: dict[str, Any] | None) -> bool:
    """App moderators and members promoted in chat may both moderate chat."""
    if is_moderator(user):
        return True
    uid = str((user or {}).get("id") or "")
    if not uid:
        return False
    # Imported lazily: store imports this module for message permissions.
    from . import store
    participant = store.get_participant({"id": uid})
    return str((participant or {}).get("role") or "").strip().lower() in {"moderator", "administrator"}
