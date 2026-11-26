"""Secure retrieval of chat-owned media.

Media is served only after shared chat visibility rules confirm the participant
may see the owning message. Files are cached locally for fast serving and also
restored from cloud-backed blob storage when the local cache is missing.
"""
from __future__ import annotations

import mimetypes

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response

from . import store

_INLINE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf",
                 ".webm", ".ogg", ".m4a", ".mp3", ".wav"}
_AUDIO_TYPES = {
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}


def _media_type(path_name: str, fallback: str = "") -> str:
    ext = "." + path_name.rsplit(".", 1)[-1].lower() if "." in path_name else ""
    if ext in _AUDIO_TYPES:
        return _AUDIO_TYPES[ext]
    if fallback:
        return fallback
    guessed, _ = mimetypes.guess_type(path_name)
    return guessed or "application/octet-stream"


def media_response(user: dict, file_id: str):
    if not store.can_access_media(user, file_id, consume_view_once=True):
        raise HTTPException(404, "Media not found.")
    path = store.get_media_path(file_id)
    if path:
        safe_name = "".join(ch for ch in path.name if ch.isalnum() or ch in "._-") or "file"
        ext = path.suffix.lower()
        media_type = _media_type(safe_name)
        headers = {
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Accept-Ranges": "bytes",
        }
        if ext not in _INLINE_TYPES:
            headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'
        return FileResponse(path, media_type=media_type, headers=headers)

    blob = store.get_media_blob(file_id)
    if not blob:
        raise HTTPException(404, "Media not found.")
    safe_name = "".join(ch for ch in str(blob.get("file_name") or "file") if ch.isalnum() or ch in "._-") or "file"
    mime = str(blob.get("mime_type") or "application/octet-stream")
    ext = "." + safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Accept-Ranges": "bytes",
    }
    if ext not in _INLINE_TYPES:
        headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'
    return Response(content=blob["data"], media_type=_media_type(safe_name, mime), headers=headers)
