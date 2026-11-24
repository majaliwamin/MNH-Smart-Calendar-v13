"""Secure retrieval of chat-owned media.

Media is served only after shared chat visibility rules confirm the participant
may see the owning message. Files are cached locally for fast serving and also
restored from cloud-backed blob storage when the local cache is missing.
"""
from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response

from . import store

_INLINE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf",
                 ".webm", ".ogg", ".m4a", ".mp3", ".wav"}


def media_response(user: dict, file_id: str):
    if not store.can_access_media(user, file_id):
        raise HTTPException(404, "Media not found.")
    path = store.get_media_path(file_id)
    if path:
        safe_name = "".join(ch for ch in path.name if ch.isalnum() or ch in "._-") or "file"
        headers = {
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        }
        if path.suffix.lower() not in _INLINE_TYPES:
            headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'
        return FileResponse(path, media_type=None, headers=headers)

    blob = store.get_media_blob(file_id)
    if not blob:
        raise HTTPException(404, "Media not found.")
    safe_name = "".join(ch for ch in str(blob.get("file_name") or "file") if ch.isalnum() or ch in "._-") or "file"
    mime = str(blob.get("mime_type") or "application/octet-stream")
    ext = "." + safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if ext not in _INLINE_TYPES:
        headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'
    return Response(content=blob["data"], media_type=mime, headers=headers)
