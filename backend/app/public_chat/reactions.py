"""Emoji reaction storage with one reaction per user and message."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from . import models, service, settings, store


def _reaction_id(message_id: str, user_id: str, emoji: str) -> str:
    import hashlib
    raw = f"{message_id}|{user_id}|{emoji}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def toggle_reaction(user: dict[str, Any], message_id: str, emoji: str) -> dict[str, Any]:
    service.check_rate(user, "reaction")
    participant = store.require_participant(user)
    message = store._message_doc(message_id)
    if not message or not store._message_visible(message, participant, service.blocked_codes(user)):
        raise HTTPException(404, "Message not found.")
    if message.get("deleted"):
        raise HTTPException(400, "Deleted messages cannot be reacted to.")
    emoji = str(emoji or "").strip()
    if emoji not in settings.ALLOWED_REACTIONS:
        raise HTTPException(400, "Unsupported reaction.")
    uid = str(user.get("id") or "")
    doc_id = _reaction_id(message_id, uid, emoji)
    existing = store._read(models.COL_REACTIONS, doc_id)
    if existing:
        store._delete(models.COL_REACTIONS, doc_id)
        added = False
    else:
        store._write(models.COL_REACTIONS, doc_id, {
            "message_id": message_id,
            "user_id": uid,
            "sender_code": str(participant.get("code") or ""),
            "emoji": emoji,
            "created_at": store._now(),
        })
        added = True
    reactions = store._reaction_summaries(uid).get(message_id, {})
    return {
        "message_id": message_id,
        "added": added,
        "reactions": reactions,
    }
