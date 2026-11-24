"""Secure retrieval of chat-owned media.

Media is stored outside static mounts and is only served after the shared chat
visibility rules confirm the participant may see the owning message.
"""
from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import FileResponse

from . import store

_INLINE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf",
                 ".webm", ".ogg", ".m4a", ".mp3", ".wav"}


def media_response(user: dict, file_id: str) -> FileResponse:
    if not store.can_access_media(user, file_id):
        raise HTTPException(404, "Media not found.")
    path = store.get_media_path(file_id)
    if not path:
        raise HTTPException(404, "Media not found.")
    safe_name = "".join(ch for ch in path.name if ch.isalnum() or ch in "._-") or "file"
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if path.suffix.lower() not in _INLINE_TYPES:
        headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'
    return FileResponse(path, media_type=None, headers=headers)
