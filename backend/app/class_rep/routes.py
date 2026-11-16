"""HTTP boundary for the Class Rep Assistant."""
import logging
import threading
import time
from collections import deque
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Header\nfrom fastapi.responses import StreamingResponse\nfrom hmac import compare_digest\nimport os\nfrom io import BytesIO
from app.class_rep.config import provider_config, provider_configs
from app.class_rep.schemas import ChatRequest, ChatResponse
from app.class_rep.assistant import reply
from app.class_rep.providers import ProviderError\nfrom app.class_rep.documents import ingest, list_documents, delete_document, DocumentError\nfrom app.class_rep.voice import transcribe, speak, VoiceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/class-rep", tags=["Class Representative Assistant"])
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: dict[str, deque] = {}
_RATE_WINDOW_SECONDS = 60
_RATE_LIMIT = 30


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
        if len(_RATE_BUCKETS) > 2000:
            for key in list(_RATE_BUCKETS)[:500]:
                if not _RATE_BUCKETS[key] or now - _RATE_BUCKETS[key][-1] >= _RATE_WINDOW_SECONDS:
                    _RATE_BUCKETS.pop(key, None)


@router.get("/status")
def status():
    cfg = provider_config()
    configured = provider_configs()
    return {
        "ready": bool(configured),
        "provider": cfg["provider"],
        "model": cfg["model"],
        "secret_configured": bool(configured),
        "fallbacks": [item["provider"] for item in configured[1:]],
        "provider_priority": ["cloudflare", "huggingface", "groq"],
        "knowledge_sources": [
            "timetable", "modules", "facilitators", "examinations",
            "recurring_activities", "announcements", "resources",
            "recent_activity_history",
        ],
        "document_uploads": "not_enabled",
        "voice": "not_enabled",
    }


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



def _require_document_admin(token: str | None) -> None:
    expected = os.getenv("MNH_CLASSREP_DOCUMENT_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Document administration is disabled until MNH_CLASSREP_DOCUMENT_ADMIN_TOKEN is configured.")
    if not token or not compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="A valid document administrator credential is required.")


@router.get("/documents")
def documents_list():
    """List document titles only; extracted contents remain server-side."""
    return {"documents": list_documents()}


@router.post("/documents")
async def documents_upload(file: UploadFile = File(...),
                           x_cara_admin_token: str | None = Header(default=None)):
    _require_document_admin(x_cara_admin_token)
    filename = (file.filename or "").replace("\\", "/").split("/")[-1][:180]
    content = await file.read(10 * 1024 * 1024 + 1)
    await file.close()
    try:
        return ingest(filename, content)
    except DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/documents/{document_id}")
def documents_delete(document_id: str, x_cara_admin_token: str | None = Header(default=None)):
    _require_document_admin(x_cara_admin_token)
    if not document_id.isalnum() or len(document_id) != 32:
        raise HTTPException(status_code=400, detail="Invalid document identifier.")
    if not delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": True, "id": document_id}


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    content = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    try:
        return {"text": transcribe(content, file.content_type or "")}
    except VoiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/speak")
def speak_text(payload: dict):
    text_value = str(payload.get("text", ""))[:1800]
    try:
        audio, media_type = speak(text_value)
        return StreamingResponse(BytesIO(audio), media_type=media_type,
                                 headers={"Cache-Control": "no-store",
                                          "Content-Disposition": 'inline; filename="cara-response.mp3"'})
    except VoiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
