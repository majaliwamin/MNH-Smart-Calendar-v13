"""CRARA API: authenticated chat, private memory, tasks and reminders."""
import logging, os, re, threading, time, uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import deque
from hmac import compare_digest
from io import BytesIO
from fastapi import APIRouter, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from app.class_rep.config import provider_config, provider_configs
from app.class_rep.schemas import ChatRequest, ChatResponse
from app.class_rep.assistant import reply
from app.class_rep.providers import ProviderError, cloudflare_diagnostic
from app.class_rep.documents import ingest, list_documents, delete_document, DocumentError
from app.class_rep.voice import transcribe, speak, VoiceError
from app.class_rep import memory
from app.class_rep.language_intelligence import resolve_response_language
from app.class_rep.linguistic_knowledge import lexicon_stats
from app.services.authentication import role_for_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/class-rep", tags=["CRARA"])
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: dict[str, deque] = {}
_RATE_WINDOW_SECONDS, _RATE_LIMIT = 60, 30
_ANALYTICS_QUERY = re.compile(r"analytics|performance|missed sessions?|attendance|delivery mode|online vs|face.to.face|teaching hours", re.I)
_ANALYTICS_ROLES = {"hod", "coordinator", "executive_dean"}

_LANGUAGE_TOGGLE_OWNER_EMAIL = "majaliwamin@gmail.com"


def _is_language_toggle_owner(user: dict) -> bool:
    """Only the designated signed-in account may use CRARA language preferences."""
    return str((user or {}).get("email", "")).strip().casefold() == _LANGUAGE_TOGGLE_OWNER_EMAIL


def _rate(key: str, limit: int = _RATE_LIMIT):
    now = time.monotonic()
    with _RATE_LOCK:
        bucket = _RATE_BUCKETS.setdefault(key, deque())
        while bucket and now - bucket[0] >= _RATE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, "Too many assistant requests. Please wait a minute.")
        bucket.append(now)


def _durable_storage_ready() -> bool:
    if not os.getenv("RENDER"):
        return True
    data_dir = os.getenv("MNH_DATA_DIR", "").strip()
    return bool(os.getenv("DATABASE_URL", "").strip()) or bool(data_dir and os.path.ismount(data_dir))


def _require_durable_storage():
    if not _durable_storage_ready():
        raise HTTPException(
            503,
            "Private CRARA memory is temporarily unavailable because durable storage is not configured. "
            "Do not create an account yet; the current free web-service filesystem is temporary."
        )


def _user(request: Request):
    _require_durable_storage()
    user = memory.resolve_session(request.cookies.get("cara_session"))
    if not user:
        raise HTTPException(401, "Sign in to your CRARA account to use private conversations and memory.")
    return user


def _cookie(response: Response, token: str):
    production = os.getenv("MNH_ENV", "").lower() == "production" or bool(os.getenv("RENDER"))
    response.set_cookie("cara_session", token, max_age=memory.SESSION_SECONDS,
                        httponly=True, secure=production, samesite="lax", path="/")


def _admin(token: str | None):
    expected = os.getenv("MNH_CLASSREP_DOCUMENT_ADMIN_TOKEN", "").strip()
    if not expected or not token or not compare_digest(token, expected):
        raise HTTPException(401, "A valid document administrator credential is required.")


def _require_document_admin(token: str | None):
    return _admin(token)


@router.post("/auth/register")
def register(payload: dict, request: Request, response: Response):
    _require_durable_storage()
    _rate("register:" + (request.client.host if request.client else "unknown"), 8)
    try:
        user = memory.create_account(payload.get("name"), payload.get("email"), payload.get("password"))
    except memory.MemoryError as exc:
        raise HTTPException(400, str(exc)) from exc
    _cookie(response, memory.create_session(user["id"]))
    return {"authenticated": True, "user": user}


@router.post("/auth/login")
def login(payload: dict, request: Request, response: Response):
    _require_durable_storage()
    _rate("login:" + (request.client.host if request.client else "unknown"), 8)
    user = memory.verify_account(payload.get("email", ""), payload.get("password", ""))
    if not user:
        raise HTTPException(401, "Email or password is incorrect.")
    _cookie(response, memory.create_session(user["id"]))
    return {"authenticated": True, "user": user}


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    memory.revoke_session(request.cookies.get("cara_session"))
    response.delete_cookie("cara_session", path="/", httponly=True, samesite="lax")
    return {"authenticated": False}


@router.get("/auth/me")
def me(request: Request, response: Response):
    if not _durable_storage_ready():
        return {"authenticated": False, "user": None, "storage_ready": False,
                "message": "Private CRARA memory is waiting for a persistent database or an attached persistent disk."}
    token = request.cookies.get("cara_session")
    user = memory.resolve_session(token)
    if user and token:
        # Keep the browser's persistent cookie expiry aligned with the sliding
        # server-side session expiry, so returning users are not asked to sign in.
        _cookie(response, token)
    return {"authenticated": bool(user), "user": user, "storage_ready": True}


@router.get("/diagnostics/provider")
def provider_diagnostics(request: Request):
    """Authenticated, one-shot Cloudflare token and Workers AI smoke test."""
    user = _user(request)
    _rate("provider-diagnostics:" + user["id"], 5)
    result = cloudflare_diagnostic()
    logger.info(
        "CRARA provider diagnostic user_id=%s configured=%s token_valid=%s token_http_status=%s "
        "inference_success=%s inference_http_status=%s token_error_codes=%s inference_error_codes=%s",
        user["id"], result.get("configured"), result.get("token_valid"),
        result.get("token_http_status"), result.get("inference_success"),
        result.get("inference_http_status"), ",".join(result.get("token_error_codes", [])) or "-",
        ",".join(result.get("inference_error_codes", [])) or "-",
    )
    return result


@router.get("/status")
def status():
    cfg, configured = provider_config(), provider_configs()
    cloudflare = bool(os.getenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", "").strip() and os.getenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "").strip())
    stt = os.getenv("MNH_CLASSREP_CLOUDFLARE_STT_MODEL", "").strip()
    return {"ready": bool(configured), "provider": cfg["provider"], "model": cfg["model"],
            "secret_configured": bool(configured), "connection": "not_tested",
            "fallbacks": [p["provider"] for p in configured[1:]],
            "provider_priority": ["cloudflare", "huggingface", "groq"],
            "knowledge_sources": ["timetable", "modules", "facilitators", "examinations", "recurring_activities",
                                  "announcements", "resources", "uploaded_documents", "account_conversations",
                                  "account_memories", "account_tasks", "curated_chichewa_lexicon"],
            "language_intelligence": {
                "version": lexicon_stats()["version"],
                "lexicon_entries": lexicon_stats()["entries"],
                "capabilities": ["language_detection", "intent_mode_detection", "source_grounded_retrieval",
                                 "independent_output_validation"],
            },
            "document_uploads": "enabled",
            "document_search": "keyword_then_semantic_fallback" if cloudflare else "keyword_only",
            "embedding_model": os.getenv("MNH_CLASSREP_CLOUDFLARE_EMBEDDING_MODEL", "@cf/google/embeddinggemma-2"),
            "voice": "enabled" if cloudflare and stt else "disabled_missing_voice_model",
            "speech_to_text_model": stt or None,
            "text_to_speech_model": os.getenv("MNH_CLASSREP_CLOUDFLARE_TTS_MODEL", "@cf/deepgram/aura-2-en"),
            "management_analytics": "role_restricted",
            "management_analytics_roles": ["hod", "coordinator", "executive_dean"],
            "account_memory": "persistent_account_scoped" if _durable_storage_ready() else "disabled_missing_durable_storage", "reminder_delivery": "in_app_only"}



def _explicit_reminder(user_id: str, message: str):
    """Create only explicit time-bound reminders; default unspecified time to 09:00 Blantyre."""
    follow_up = re.search(r"\bfollow up on (.+?) next week\b", message.strip(), re.I)
    if follow_up:
        target = (datetime.now(ZoneInfo("Africa/Blantyre")) + timedelta(days=7)).replace(hour=9, minute=0, second=0, microsecond=0)
        reminder = memory.create_reminder(user_id, {
            "message": "Follow up on " + follow_up.group(1).strip(),
            "scheduled_at": int(target.timestamp()), "timezone": "Africa/Blantyre"
        })
        return reminder, target
    match = re.search(r"\bremind me (tomorrow|today|next week|on monday|on tuesday|on wednesday|on thursday|on friday|on saturday|on sunday|on \d{4}-\d{2}-\d{2})(?: at (\d{1,2}:\d{2})| at (\d{1,2})(?:\s*(am|pm))?)? to (.+)$", message.strip(), re.I)
    if not match:
        return None
    tz = ZoneInfo("Africa/Blantyre")
    now = datetime.now(tz)
    phrase, clock, hour_only, meridiem, task = match.groups()
    day = phrase.lower()
    if day == "today":
        target = now
    elif day == "tomorrow":
        target = now + timedelta(days=1)
    elif day == "next week":
        target = now + timedelta(days=7)
    elif day.startswith("on ") and day[3:7].isdigit():
        target = datetime.strptime(day[3:], "%Y-%m-%d").replace(tzinfo=tz)
    elif day.startswith("on "):
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        wanted = weekdays.index(day[3:])
        delta = (wanted - now.weekday()) % 7 or 7
        target = now + timedelta(days=delta)
    else:
        return None
    if clock:
        hour, minute = map(int, clock.split(":"))
    elif hour_only:
        hour, minute = int(hour_only), 0
        if meridiem:
            hour = hour % 12 + (12 if meridiem.lower() == "pm" else 0)
    else:
        hour, minute = 9, 0
    if hour > 23 or minute > 59:
        return None
    target = target.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        return None
    reminder = memory.create_reminder(user_id, {
        "message": task.strip(), "scheduled_at": int(target.timestamp()),
        "timezone": "Africa/Blantyre"
    })
    return reminder, target


def _explicit_project(user_id: str, message: str, conversation_id: str = ""):
    match = re.search(r"\b(?:(?:create|start|track)\s+(?:a\s+)?project(?:\s+called|\s+named|\s*:\s*)\s*|my project is\s+)(.+)$", message.strip(), re.I)
    if not match:
        return None
    title = match.group(1).strip().rstrip(".!?")[:180]
    if not title:
        return None
    for existing in memory.list_projects(user_id):
        if existing.get("title", "").strip().casefold() == title.casefold() and existing.get("status") not in ("completed", "archived"):
            return existing
    return memory.upsert_project(user_id, {"title": title, "status": "active", "related_conversation": conversation_id})


def _explicit_task(user_id: str, message: str, conversation_id: str = ""):
    match = re.search(r"\b(?:create|add|track)\s+(?:a\s+)?task(?:\s+to|\s*:\s*)\s*(.+)$", message.strip(), re.I)
    if not match:
        return None
    title = match.group(1).strip().rstrip(".!?")[:180]
    if not title:
        return None
    for existing in memory.list_tasks(user_id):
        if existing.get("title", "").strip().casefold() == title.casefold() and existing.get("status") not in ("completed", "cancelled"):
            return existing
    active_projects = [p for p in memory.list_projects(user_id) if p.get("status") == "active"]
    task_data = {"title": title, "status": "not_started", "priority": "normal", "related_conversation": conversation_id}
    if len(active_projects) == 1:
        task_data["project_id"] = active_projects[0]["id"]
        task_data["project"] = active_projects[0]["title"]
    return memory.upsert_task(user_id, task_data)


@router.get("/language")
def get_language(request: Request):
    user = _user(request)
    if not _is_language_toggle_owner(user):
        return {"response_language": "EN"}
    return {"response_language": memory.get_response_language(user["id"])}


@router.put("/language")
def update_language(request: Request, payload: dict):
    user = _user(request)
    if not _is_language_toggle_owner(user):
        raise HTTPException(403, "The CRARA response-language setting is restricted to its designated owner account.")
    try:
        language = memory.set_response_language(user["id"], payload.get("response_language", ""))
    except memory.MemoryError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"response_language": language}


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request, x_cara_analytics_password: str | None = Header(default=None)):
    user = _user(request)
    _rate("chat:" + user["id"] + ":" + (request.client.host if request.client else "unknown"))
    analytics_context = None
    if _ANALYTICS_QUERY.search(payload.message):
        role = role_for_password(x_cara_analytics_password or "")
        if role not in _ANALYTICS_ROLES:
            raise HTTPException(403, "Management analytics require an authorised HOD, coordinator or executive dean password.")
        from app.api.routes import analytics as get_analytics
        analytics_context = {"authorised_role": role, "summary": get_analytics()}
    conversation_id = re.sub(r"[^a-zA-Z0-9_-]", "", payload.conversation_id or "")[:80] or uuid.uuid4().hex
    history = [item.model_dump() for item in payload.history]
    persisted_preference, explicit_preference = memory.response_language_state(user["id"])
    selected_language = resolve_response_language(
        payload.response_language,
        payload.message.strip(),
        persisted_preference=persisted_preference,
        explicit_preference=explicit_preference,
        history=history,
    )
    try:
        project_created = _explicit_project(user["id"], payload.message.strip(), conversation_id)
        if project_created:
            confirmation = (
                "Ndasunga pulojekiti ya '" + project_created["title"] + "' m’zolemba za CRARA."
                if selected_language == "CH" else
                "I have saved the project '" + project_created["title"] + "' to your CRARA project records."
            )
            memory.save_turn(user["id"], conversation_id, payload.message.strip(), confirmation)
            return ChatResponse(reply=confirmation, provider="CRARA project memory",
                                model="persistent project record", conversation_id=conversation_id)
        task_created = _explicit_task(user["id"], payload.message.strip(), conversation_id)
        if task_created:
            confirmation = (
                "Ndasunga ntchito yoti '" + task_created["title"] + "' m’ndandanda wa ntchito wa CRARA, osayamba."
                if selected_language == "CH" else
                "I have saved the task “" + task_created["title"] + "” to your CRARA task list as not started."
            )
            memory.save_turn(user["id"], conversation_id, payload.message.strip(), confirmation)
            return ChatResponse(reply=confirmation, provider="CRARA task engine",
                                model="persistent task memory", conversation_id=conversation_id)
        reminder_created = _explicit_reminder(user["id"], payload.message.strip())
        if reminder_created:
            reminder, scheduled_for = reminder_created
            when = scheduled_for.strftime("%A, %d %B %Y, %H:%M")
            confirmation = (
                "Ndakonzekeretsa chikumbutso cha '" + reminder["message"] + "' pa " + when +
                " (Africa/Blantyre). Chidzawoneka mu CRARA mukabwerera; palibe njira ya SMS, imelo kapena push notification."
                if selected_language == "CH" else
                "I have scheduled an in-app reminder for “" + reminder["message"] + "” at " + when + " (Africa/Blantyre). It will appear in CRARA when you return; no SMS, email or push notification channel is configured."
            )
            memory.save_turn(user["id"], conversation_id, payload.message.strip(), confirmation)
            return ChatResponse(reply=confirmation, provider="CRARA reminder engine",
                                model="persistent in-app reminder", conversation_id=conversation_id)
        stage_started = time.monotonic()
        retrieved = memory.retrieve_context(user["id"], payload.message.strip(), conversation_id)
        memory_ms = round((time.monotonic() - stage_started) * 1000)
        stage_started = time.monotonic()
        answer, provider, model, updated = reply(payload.message.strip(),
            history,
            management_analytics=analytics_context, memory_context=retrieved, owner_id=user['id'],
            response_language=selected_language)
        provider_pipeline_ms = round((time.monotonic() - stage_started) * 1000)
        stage_started = time.monotonic()
        memory.save_turn(user["id"], conversation_id, payload.message.strip(), answer)
        save_ms = round((time.monotonic() - stage_started) * 1000)
        logger.info("CRARA timing memory_ms=%s provider_pipeline_ms=%s save_ms=%s prompt_history=%s",
                    memory_ms, provider_pipeline_ms, save_ms, min(len(payload.history), 6))
        return ChatResponse(reply=answer, provider=provider, model=model,
                            context_updated_at=updated, conversation_id=conversation_id)
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("CRARA request failed")
        raise HTTPException(503, "CRARA is temporarily unavailable. Please try again later.") from exc


@router.post("/conversation/turn")
def conversation_turn(request: Request, payload: dict):
    user = _user(request)
    message = str(payload.get("message", "")).strip()[:4000]
    answer = str(payload.get("reply", "")).strip()[:6000]
    conversation_id = str(payload.get("conversation_id") or uuid.uuid4().hex)[:80]
    if not message or not answer:
        raise HTTPException(400, "A user message and assistant response are required.")
    project = _explicit_project(user["id"], message, conversation_id)
    if project:
        answer = "I have saved the project '" + project["title"] + "' to your CRARA project records."
    task = None if project else _explicit_task(user["id"], message, conversation_id)
    if task:
        answer = "I have saved the task “" + task["title"] + "” to your CRARA task list as not started."
    reminder_result = _explicit_reminder(user["id"], message)
    if reminder_result:
        reminder, scheduled_for = reminder_result
        answer = "I have scheduled an in-app reminder for “" + reminder["message"] + "” at " + scheduled_for.strftime("%A, %d %B %Y, %H:%M") + " (Africa/Blantyre). It will appear in CRARA when you return; no SMS, email or push notification channel is configured."
    memory.save_turn(user["id"], conversation_id, message, answer)
    return {"saved": True, "conversation_id": conversation_id, "reply": answer}


@router.get("/memories")
def memories_list(request: Request):
    return {"memories": memory.list_memories(_user(request)["id"])}


@router.post("/memories")
def memories_save(request: Request, payload: dict):
    try:
        return memory.save_memory(_user(request)["id"], payload)
    except memory.MemoryError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/memories/{memory_id}")
def memories_delete(memory_id: str, request: Request):
    if not memory.delete_memory(_user(request)["id"], memory_id):
        raise HTTPException(404, "Memory not found.")
    return {"deleted": True, "id": memory_id}


@router.get("/projects")
def projects_list(request: Request):
    return {"projects": memory.list_projects(_user(request)["id"])}


@router.post("/projects")
def projects_create(request: Request, payload: dict):
    try:
        return memory.upsert_project(_user(request)["id"], payload)
    except memory.MemoryError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/projects/{project_id}")
def projects_update(project_id: str, request: Request, payload: dict):
    payload["id"] = project_id
    try:
        return memory.upsert_project(_user(request)["id"], payload)
    except memory.MemoryError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/tasks")
def tasks_list(request: Request):
    return {"tasks": memory.list_tasks(_user(request)["id"])}


@router.post("/tasks")
def tasks_create(request: Request, payload: dict):
    try:
        return memory.upsert_task(_user(request)["id"], payload)
    except memory.MemoryError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/tasks/{task_id}")
def tasks_update(task_id: str, request: Request, payload: dict):
    payload["id"] = task_id
    try:
        return memory.upsert_task(_user(request)["id"], payload)
    except memory.MemoryError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/reminders")
def reminders_list(request: Request):
    return {"reminders": memory.list_reminders(_user(request)["id"]), "delivery": "in_app_only"}


@router.post("/reminders")
def reminders_create(request: Request, payload: dict):
    try:
        return memory.create_reminder(_user(request)["id"], payload)
    except memory.MemoryError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/reminders/{reminder_id}")
def reminders_update(reminder_id: str, request: Request, payload: dict):
    user_id = _user(request)["id"]
    item = next((x for x in memory.list_reminders(user_id) if x["id"] == reminder_id), None)
    if not item:
        raise HTTPException(404, "Reminder not found.")
    action = payload.get("action")
    if action in ("cancel", "complete"):
        item["status"] = "cancelled" if action == "cancel" else "completed"
    elif payload.get("scheduled_at") is not None:
        item["scheduled_at"] = int(payload["scheduled_at"])
        if item["scheduled_at"] <= int(time.time()):
            raise HTTPException(400, "Choose a future reminder time.")
        item["status"] = "scheduled"
    else:
        raise HTTPException(400, "Choose cancel, complete or a future scheduled_at.")
    memory._write(memory.COL_REMINDERS, memory._doc_id(user_id, reminder_id),
                  {k: v for k, v in item.items() if k not in ("id", "updated_at")})
    return {"id": reminder_id, **item}


@router.get("/conversations")
def conversations_list(request: Request):
    return {"conversations": memory.list_conversations(_user(request)["id"])}


@router.get("/documents")
def documents_list(request: Request):
    _user(request)
    return {"documents": list_documents(_user(request)["id"])}


@router.post("/documents")
async def documents_upload(request: Request, file: UploadFile = File(...),
                           x_cara_admin_token: str | None = Header(default=None)):
    _user(request)
    filename = (file.filename or "").replace("\\\\", "/").split("/")[-1][:180]
    content = await file.read(10 * 1024 * 1024 + 1)
    await file.close()
    try:
        return ingest(filename, content, owner_id=_user(request)["id"])
    except DocumentError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/documents/{document_id}")
def documents_delete(document_id: str, request: Request,
                     x_cara_admin_token: str | None = Header(default=None)):
    _user(request)
    _admin(x_cara_admin_token)
    if not document_id.isalnum() or len(document_id) != 32:
        raise HTTPException(400, "Invalid document identifier.")
    if not delete_document(document_id, owner_id=_user(request)["id"]):
        raise HTTPException(404, "Document not found.")
    return {"deleted": True, "id": document_id}


@router.post("/transcribe")
async def transcribe_audio(request: Request, file: UploadFile = File(...)):
    _user(request)
    _rate("voice:" + (_user(request)["id"]), 10)
    content = await file.read(5 * 1024 * 1024 + 1)
    content_type = file.content_type or ""
    await file.close()
    try:
        return {"text": transcribe(content, content_type)}
    except VoiceError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/speak")
def speak_text(payload: dict, request: Request):
    _user(request)
    _rate("voice:" + _user(request)["id"], 10)
    try:
        audio, media_type = speak(str(payload.get("text", ""))[:1800])
        return StreamingResponse(BytesIO(audio), media_type=media_type,
            headers={"Cache-Control": "no-store", "Content-Disposition": 'inline; filename="cara-response.mp3"'})
    except VoiceError as exc:
        raise HTTPException(503, str(exc)) from exc
