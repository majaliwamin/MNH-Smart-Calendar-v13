"""HTTP boundary for the Class Rep Assistant."""
import logging
import threading
import time
from collections import deque
from fastapi import APIRouter, HTTPException, Request
from app.class_rep.config import provider_config
from app.class_rep.schemas import ChatRequest, ChatResponse
from app.class_rep.assistant import reply
from app.class_rep.providers import ProviderError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/class-rep", tags=["Class Representative Assistant"])
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: dict[str, deque] = {}
_RATE_WINDOW_SECONDS = 60
_RATE_LIMIT = 15


def _enforce_rate_limit(client_key: str) -> None:
    """Best-effort per-process abuse control; shared limits need a central cache."""
    now = time.monotonic()
    with _RATE_LOCK:
        bucket = _RATE_BUCKETS.setdefault(client_key, deque())
        while bucket and now - bucket[0] >= _RATE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= _RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Too many assistant requests. Please wait a minute and try again.")
        bucket.append(now)
        # Bound memory if many transient client addresses reach the public endpoint.
        if len(_RATE_BUCKETS) > 2000:
            for key in list(_RATE_BUCKETS)[:500]:
                if not _RATE_BUCKETS[key] or now - _RATE_BUCKETS[key][-1] >= _RATE_WINDOW_SECONDS:
                    _RATE_BUCKETS.pop(key, None)


@router.get("/status")
def status():
    cfg = provider_config()
    return {"ready": bool(cfg["api_key"] and cfg["model"]),
            "provider": cfg["provider"], "model": cfg["model"],
            "secret_configured": bool(cfg["api_key"])}


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request):
    client_key = request.client.host if request.client else "unknown"
    _enforce_rate_limit(client_key)
    try:
        text, provider, model, updated = reply(payload.message.strip(), [item.model_dump() for item in payload.history])
        return ChatResponse(reply=text, provider=provider, model=model, context_updated_at=updated)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Class Rep Assistant request failed")
        raise HTTPException(status_code=503, detail="The Class Rep Assistant is temporarily unavailable. Please try again later.") from exc
