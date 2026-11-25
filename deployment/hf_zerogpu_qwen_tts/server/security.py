from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from .config import settings


def require_bearer(authorization: str | None = Header(default=None)) -> None:
    if not settings.require_auth:
        return
    expected = settings.api_key.strip()
    if not expected:
        raise HTTPException(status_code=503, detail="QWEN_TTS_API_KEY is not configured on the inference server.")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    provided = authorization.split(" ", 1)[1].strip()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token.")
