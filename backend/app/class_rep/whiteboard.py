"""Structured, code-free whiteboard instruction engine for CRARA classroom lessons.

The model never executes code. It may only return one of the fixed instruction
names below, and every argument is validated before the object is sent to the
additive classroom whiteboard. Deterministic local teaching data is used when
providers are unavailable, following the existing CRARA teaching pattern.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import math
import os
import re
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.class_rep import memory
from app.class_rep.classroom_permissions import classroom_role
from app.class_rep.output_validation import repair_math_delimiters, validate_reply
from app.class_rep.providers import ProviderError, complete

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/class-rep/whiteboard", tags=["CRARA Whiteboard"])

SESSION_COLLECTION = "cara_whiteboard_sessions"
WHITEBOARD_INSTRUCTIONS = frozenset({
    "WRITE_TEXT", "DRAW_STROKE", "DRAW_LINE", "DRAW_ARROW", "DRAW_CIRCLE",
    "DRAW_RECTANGLE", "DRAW_CURVE", "DRAW_GRAPH", "RENDER_EQUATION",
    "HIGHLIGHT", "ERASE", "MOVE_OBJECT", "RESIZE_OBJECT", "EDIT_TEXT",
    "ADD_PAGE", "DELETE_PAGE", "NAVIGATE_PAGE", "UNDO", "REDO",
    "CLEAR_BOARD", "ZOOM", "PAN",
})
CHAT_MODES = ("Active", "Question Queue", "Host-selected", "Chat-only", "Silent monitoring")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_GUEST_ID_RE = re.compile(r"^guest_[A-Za-z0-9_-]{8,96}$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_FORBIDDEN_ARG_KEYS = frozenset({
    "code", "script", "javascript", "js", "eval", "exec", "function",
    "expression", "lambda", "html", "onclick", "onload", "href", "src",
})
_BANNED_OUTPUT = ("penrose", "scholarmw", "voice training", "vtc", "your logo", "physics")
_CONTROL_TTL_SECONDS = 300
# A CRARA co-host grant must survive a normal lesson without asking the human
# host to click again every five minutes. It is still signed and room-scoped.
_COHOST_TTL_SECONDS = 7200
_CONTROL_TYPES = frozenset({"mode", "permissions", "teaching", "cohost"})
_TEACHING_STATES = frozenset({"idle", "teaching", "listening", "answering", "paused", "stopped"})
_MAX_INSTRUCTIONS = 40
_MAX_POINTS = 500
_MAX_PAGES = 50
_TIMELINE_TYPES = frozenset({"TEACHING", "CAPTION", "SPEAK", "BOARD", "PAUSE", "RESUME", "INTERRUPT"})
_MAX_TIMELINE_SEGMENTS = 80
_MAX_TIMELINE_AT_MS = 120_000

_ALLOWED_ARGS: dict[str, frozenset[str]] = {
    "WRITE_TEXT": frozenset({"text", "x", "y", "style"}),
    "DRAW_STROKE": frozenset({"points", "style"}),
    "DRAW_CURVE": frozenset({"points", "style"}),
    "DRAW_GRAPH": frozenset({"points", "label", "style"}),
    "DRAW_LINE": frozenset({"x1", "y1", "x2", "y2", "style"}),
    "DRAW_ARROW": frozenset({"x1", "y1", "x2", "y2", "style"}),
    "DRAW_CIRCLE": frozenset({"x1", "y1", "x2", "y2", "style"}),
    "DRAW_RECTANGLE": frozenset({"x1", "y1", "x2", "y2", "style"}),
    "RENDER_EQUATION": frozenset({"latex", "x", "y", "style"}),
    "HIGHLIGHT": frozenset({"id"}),
    "ERASE": frozenset({"id"}),
    "MOVE_OBJECT": frozenset({"id", "dx", "dy"}),
    "RESIZE_OBJECT": frozenset({"id", "scale"}),
    "EDIT_TEXT": frozenset({"id", "text", "latex"}),
    "ADD_PAGE": frozenset(),
    "DELETE_PAGE": frozenset({"index"}),
    "NAVIGATE_PAGE": frozenset({"index"}),
    "UNDO": frozenset(),
    "REDO": frozenset(),
    "CLEAR_BOARD": frozenset(),
    "ZOOM": frozenset({"value", "factor"}),
    "PAN": frozenset({"dx", "dy"}),
}

_LOCAL_FALLBACK = {
    "narration": (
        "In hypothesis testing we begin with a null hypothesis and an alternative hypothesis, "
        "choose a significance level, compute a test statistic, and compare the p-value with that level. "
        "If the p-value is smaller than alpha, we reject the null hypothesis; otherwise we do not reject it."
    ),
    "caption": "Hypothesis testing: state hypotheses, choose alpha, compute the statistic, then decide.",
    "instructions": [
        {"type": "WRITE_TEXT", "args": {"text": "Hypothesis Testing — decision flow", "x": 90, "y": 90,
                                        "style": {"color": "#2563eb", "width": 5}}},
        {"type": "WRITE_TEXT", "args": {"text": "H0: no effect    H1: there is an effect", "x": 90, "y": 160,
                                        "style": {"color": "#000000", "width": 4}}},
        {"type": "RENDER_EQUATION", "args": {"latex": "z=\\frac{\\bar{x}-\\mu_0}{\\sigma/\\sqrt{n}}", "x": 90, "y": 240}},
        {"type": "DRAW_GRAPH", "args": {"points": [[120, 560], [260, 520], [400, 500], [540, 520], [680, 560]], "label": "standard normal curve"}},
        {"type": "DRAW_ARROW", "args": {"x1": 120, "y1": 380, "x2": 520, "y2": 380,
                                        "style": {"color": "#dc2626", "width": 4}}},
        {"type": "WRITE_TEXT", "args": {"text": "p < alpha  ->  reject H0", "x": 130, "y": 430,
                                        "style": {"color": "#dc2626", "width": 4}}},
        {"type": "WRITE_TEXT", "args": {"text": "p >= alpha  ->  do not reject H0", "x": 130, "y": 500,
                                        "style": {"color": "#16a34a", "width": 4}}},
    ],
    "provider": "crara-whiteboard-local-v1",
    "model": "verified-statistical-teaching-data-v1",
    "speak": True,
}


class WhiteboardInstructionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str = Field(default="local", max_length=160)
    lesson: str = Field(default="Hypothesis Testing", max_length=120)
    prompt: str = Field(min_length=1, max_length=600)
    sender: str = Field(default="Student", max_length=80)
    mode: str = Field(default="Active", max_length=40)
    pages: int = Field(default=1, ge=1, le=_MAX_PAGES)
    ids: list[str] = Field(default_factory=list, max_length=100)
    position: int = Field(default=0, ge=0, le=_MAX_TIMELINE_AT_MS)
    context: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="before")
    @classmethod
    def _accept_from_alias(cls, values: Any) -> Any:
        if isinstance(values, dict) and "sender" not in values and "from" in values:
            values = dict(values)
            values["sender"] = values.pop("from")
        return values

    @model_validator(mode="after")
    def _clean_context(self) -> "WhiteboardInstructionRequest":
        self.context = [str(item)[:300] for item in self.context[:20] if str(item).strip()][-8:]
        return self


class WhiteboardInstructionResponse(BaseModel):
    ok: bool = True
    narration: str
    caption: str
    instructions: list[dict[str, Any]]
    speak: bool = True
    provider: str
    model: str | None = None
    control: dict[str, Any] | None = None
    timeline: dict[str, Any] | None = None


class WhiteboardSessionRequest(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    lesson: str = Field(default="Hypothesis Testing", max_length=120)
    pages: list[dict[str, Any]] = Field(default_factory=list, max_length=_MAX_PAGES)
    pageIndex: int = Field(default=0, ge=0, le=_MAX_PAGES - 1)
    chatMode: str = Field(default="Active", max_length=40)
    permissions: dict[str, Any] = Field(default_factory=dict)
    authority: str = Field(default="", max_length=2000)


class WhiteboardControlRequest(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    type: str = Field(min_length=1, max_length=40)
    value: dict[str, Any] = Field(default_factory=dict, max_length=40)
    authority: str = Field(default="", max_length=2000)


class WhiteboardAuthorizeRequest(WhiteboardControlRequest):
    token: str = Field(min_length=1, max_length=2000)


def _clean_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]", "", str(value or ""))[:160] or "local"


def _has_banned_output(value: Any) -> bool:
    text = str(value or "").casefold()
    return any(term in text for term in _BANNED_OUTPUT)


def _user(request: Request) -> dict:
    user = memory.resolve_session(request.cookies.get("cara_session"))
    if user:
        return user
    guest_id = str(request.cookies.get("cara_guest") or "")
    if _GUEST_ID_RE.fullmatch(guest_id):
        return {"id": guest_id, "name": "Guest", "email": ""}
    raise HTTPException(401, "Start a guest CRARA session before using the shared whiteboard.")


def _require_host(request: Request) -> dict:
    user = _user(request)
    if classroom_role(user) != "host":
        raise HTTPException(403, "Only the classroom host can save or restore the shared board session.")
    return user


def _sanitize_permissions(value: Any) -> dict[str, Any]:
    src = value if isinstance(value, dict) else {}
    granted = src.get("granted")
    return {
        "canWrite": bool(src.get("canWrite", True)),
        "canControl": bool(src.get("canControl", False)),
        "boardLocked": bool(src.get("boardLocked", False)),
        "boardOwner": str(src.get("boardOwner") or "")[:160],
        "granted": [str(item)[:160] for item in granted[:100]] if isinstance(granted, list) else [],
    }


def _control_secret() -> bytes:
    secret = (
        os.getenv("MNH_CLASSREP_DOCUMENT_ADMIN_TOKEN", "").strip()
        or os.getenv("MNH_ADMIN_PASSWORD", "").strip()
        or os.getenv("MNH_LIVEKIT_API_SECRET", "").strip()
        or "crara-whiteboard-control"
    )
    return secret.encode("utf-8")


def _sign_control(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(_control_secret(), body, hashlib.sha256).hexdigest()
    encoded = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
    return encoded + "." + signature


def _teaching_control(key: str) -> dict[str, Any]:
    value = {"value": "teaching"}
    return {
        "type": "teaching",
        "value": value,
        "token": _sign_control({
            "typ": "crara-whiteboard-control",
            "sub": "crara-lesson-service",
            "room": _clean_key(key),
            "type": "teaching",
            "value": value,
            "exp": int(time.time()) + _CONTROL_TTL_SECONDS,
        }),
    }


def _verify_control(token: str, expected: dict[str, Any]) -> dict[str, Any] | None:
    try:
        encoded, signature = str(token or "").split(".", 1)
        body = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(body)
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    check = hmac.new(_control_secret(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, check):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    if payload.get("typ") != "crara-whiteboard-control":
        return None
    for key, value in expected.items():
        if payload.get(key) != value:
            return None
    return payload


def _require_control_issuer(request: Request, key: str, authority: str = "") -> tuple[dict, str]:
    """Accept the human host or a signed, room-scoped CRARA co-host grant.

    The grant is a bearer token issued by the host through /control. Sessions,
    join codes and other account-level operations remain strictly host-only.
    """
    user = _user(request)
    if classroom_role(user) == "host":
        return user, user["id"]
    signed = _verify_control(authority, {
        "typ": "crara-whiteboard-control",
        "room": _clean_key(key),
        "type": "cohost",
    })
    if signed and signed.get("value", {}).get("enabled") is True:
        return user, str(signed.get("sub") or user["id"])
    raise HTTPException(403, "Only the classroom host or an authorised CRARA co-host can control this board.")


def _number(value: Any, low: float, high: float, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return default
    result = min(high, max(low, float(value)))
    return result


def _valid_points(value: Any) -> bool:
    if not isinstance(value, list) or not value or len(value) > _MAX_POINTS:
        return False
    for point in value:
        if isinstance(point, (list, tuple)):
            if len(point) != 2:
                return False
            x, y = point
        elif isinstance(point, dict):
            x, y = point.get("x"), point.get("y")
        else:
            return False
        if _number(x, -10000, 10000) is None or _number(y, -10000, 10000) is None:
            return False
    return True


def _valid_style(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, dict) or len(value) > 8:
        return False
    allowed = {"color", "width", "opacity", "highlight"}
    if any(key not in allowed for key in value):
        return False
    if "color" in value and (not isinstance(value["color"], str) or not _COLOR_RE.fullmatch(value["color"])):
        return False
    if "width" in value and _number(value["width"], 1, 40) is None:
        return False
    if "opacity" in value and _number(value["opacity"], 0.05, 1) is None:
        return False
    if "highlight" in value and not isinstance(value["highlight"], bool):
        return False
    return True


def validate_instruction(raw: Any) -> dict[str, Any] | None:
    """Return a sanitised instruction or None. No callable or code is accepted."""
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("type") or raw.get("op") or "").strip().upper()
    if name not in WHITEBOARD_INSTRUCTIONS:
        return None
    args = raw.get("args", raw)
    if not isinstance(args, dict) or len(args) > 20:
        return None
    if _FORBIDDEN_ARG_KEYS.intersection(args):
        return None
    if not set(args).issubset(_ALLOWED_ARGS[name]):
        return None
    clean: dict[str, Any] = {}
    for key, value in args.items():
        if key == "text":
            if not isinstance(value, str) or not value.strip() or len(value) > 1200 or _has_banned_output(value):
                return None
            clean[key] = value[:1200]
        elif key == "latex":
            if not isinstance(value, str) or not value.strip() or len(value) > 800 or _has_banned_output(value):
                return None
            clean[key] = value[:800]
        elif key == "label":
            if not isinstance(value, str) or len(value) > 120 or _has_banned_output(value):
                return None
            clean[key] = value[:120]
        elif key == "id":
            if not isinstance(value, str) or not _ID_RE.fullmatch(value):
                return None
            clean[key] = value
        elif key in {"x", "y", "x1", "y1", "x2", "y2", "dx", "dy"}:
            number = _number(value, -10000, 10000)
            if number is None:
                return None
            clean[key] = round(number, 3)
        elif key == "scale":
            number = _number(value, 0.1, 5)
            if number is None:
                return None
            clean[key] = round(number, 3)
        elif key == "factor":
            number = _number(value, 0.1, 10)
            if number is None:
                return None
            clean[key] = round(number, 3)
        elif key == "value":
            number = _number(value, 0.2, 5)
            if number is None:
                return None
            clean[key] = round(number, 3)
        elif key == "index":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value >= _MAX_PAGES:
                return None
            clean[key] = value
        elif key == "points":
            if not _valid_points(value):
                return None
            clean[key] = value[:_MAX_POINTS]
        elif key == "style":
            if not _valid_style(value):
                return None
            if value is not None:
                clean[key] = value
    if name in {"WRITE_TEXT", "RENDER_EQUATION"} and ("text" not in clean and "latex" not in clean):
        return None
    if name in {"DRAW_STROKE", "DRAW_CURVE", "DRAW_GRAPH"} and "points" not in clean:
        return None
    if name in {"MOVE_OBJECT", "PAN"} and "dx" not in clean and "dy" not in clean:
        return None
    return {"type": name, "args": clean}


def validate_instructions(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values[:_MAX_INSTRUCTIONS]:
        clean = validate_instruction(value)
        if clean:
            result.append(clean)
    return result


def parse_payload(text: str) -> dict[str, Any] | None:
    """Parse one JSON object, tolerating a single markdown code fence."""
    if not isinstance(text, str):
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(cleaned[start:end + 1])
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _prompt(payload: WhiteboardInstructionRequest) -> list[dict[str, str]]:
    names = ", ".join(sorted(WHITEBOARD_INSTRUCTIONS))
    ids = ", ".join(payload.ids[:30]) or "none"
    return [
        {
            "role": "system",
            "content": (
                "You are the CRARA classroom whiteboard planner for the English-only lesson "
                f"'{payload.lesson}'. Return ONLY one JSON object. No prose, no markdown, no code. "
                "Schema: {\"narration\": string, \"caption\": string, \"instructions\": array}. "
                "narration is what the lecturer says aloud (1-4 sentences, plain text). "
                "caption is a short board caption. instructions must contain 1-12 objects of the form "
                "{\"type\": TIER, \"args\": OBJECT}. The only permitted TIER values are: " + names + ". "
                "Use WRITE_TEXT, RENDER_EQUATION, DRAW_ARROW and DRAW_GRAPH where helpful. "
                "Equation args use {\"latex\": string, \"x\": number, \"y\": number}. "
                "Text args use {\"text\": string, \"x\": number, \"y\": number, \"style\"?: {\"color\":\"#2563eb\",\"width\":4}}. "
                "Graph args use {\"points\": [[x,y], ...], \"label\"?: string}. "
                "Existing object ids available for EDIT/ERASE/HIGHLIGHT/MOVE: " + ids + ". "
                "Never emit JavaScript, HTML, file paths, URLs, tool calls, or any instruction type "
                "outside the whitelist. Do not mention any product other than CRARA."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Chat mode: {payload.mode}. Current page count: {payload.pages}. "
                f"Timeline position: {payload.position}ms. "
                f"Recent captions and voice context: {' | '.join(payload.context) or 'none'}.\n"
                f"Question from {payload.sender}: {payload.prompt}\n"
                "Plan a clear spoken explanation and a small synchronized whiteboard illustration."
            ),
        },
    ]


def _clean_narration(value: Any, question: str) -> str:
    text = repair_math_delimiters(str(value or "").strip())[:1200]
    if not text or _has_banned_output(text):
        return ""
    result = validate_reply(text, question, "EN", mode="converse", evidence_available=False)
    return text if result.ok else ""


def _fallback_response() -> dict[str, Any]:
    return json.loads(json.dumps(_LOCAL_FALLBACK))


def _timeline_text(value: Any, limit: int) -> str:
    text = repair_math_delimiters(str(value or "").strip())[:limit]
    return "" if _has_banned_output(text) else text


def validate_timeline(raw: Any) -> dict[str, Any] | None:
    """Validate a bounded, code-free lesson timeline before it reaches clients."""
    if not isinstance(raw, dict):
        return None
    segments = raw.get("segments")
    if not isinstance(segments, list) or not segments or len(segments) > _MAX_TIMELINE_SEGMENTS:
        return None
    timeline_id = str(raw.get("id") or "")
    if not _ID_RE.fullmatch(timeline_id):
        return None
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            return None
        kind = str(segment.get("type") or "").strip().upper()
        if kind not in _TIMELINE_TYPES:
            return None
        segment_id = str(segment.get("id") or "seg-" + str(index + 1))
        if not _ID_RE.fullmatch(segment_id) or segment_id in seen:
            return None
        seen.add(segment_id)
        raw_at = segment.get("atMs", segment.get("at_ms", index * 1000))
        if (isinstance(raw_at, bool) or not isinstance(raw_at, (int, float)) or
                not math.isfinite(float(raw_at)) or float(raw_at) < 0 or
                float(raw_at) > _MAX_TIMELINE_AT_MS):
            return None
        number = float(raw_at)
        payload = segment.get("payload") if isinstance(segment.get("payload"), dict) else {}
        clean_payload: dict[str, Any] = {}
        if kind == "SPEAK":
            text = _timeline_text(payload.get("text"), 600)
            if not text:
                return None
            clean_payload = {"text": text}
        elif kind == "CAPTION":
            text = _timeline_text(payload.get("text"), 300)
            if not text:
                return None
            clean_payload = {"text": text}
        elif kind == "BOARD":
            instruction = validate_instruction(payload.get("instruction"))
            if not instruction:
                return None
            clean_payload = {"instruction": instruction}
        elif kind == "TEACHING":
            value = str(payload.get("value") or "").strip()
            if value not in _TEACHING_STATES:
                return None
            clean_payload = {"value": value}
        elif kind == "INTERRUPT":
            clean_payload = {"reason": _timeline_text(payload.get("reason") or payload.get("text"), 300) or "Question received."}
        clean.append({"id": segment_id, "type": kind, "atMs": int(number), "payload": clean_payload})
    clean.sort(key=lambda item: item["atMs"])
    started = _number(raw.get("startedAt"), 0, 2**62, int(time.time() * 1000))
    last_at = clean[-1]["atMs"]
    duration = _number(raw.get("durationMs"), last_at, _MAX_TIMELINE_AT_MS, last_at)
    return {
        "id": timeline_id,
        "version": 1,
        "lesson": str(raw.get("lesson") or "Hypothesis Testing")[:120],
        "owner": str(raw.get("owner") or "")[:160],
        "startedAt": int(started or 0),
        "durationMs": int(duration or 0),
        "segments": clean,
    }


def _build_timeline(key: str, lesson: str, narration: str, caption: str,
                    instructions: list[dict[str, Any]], speak: bool) -> dict[str, Any] | None:
    """Derive a shared timeline locally; timing is never trusted from the model."""
    segments: list[dict[str, Any]] = []

    def add(kind: str, at_ms: int, segment_payload: dict[str, Any]) -> None:
        segments.append({
            "id": "seg-" + str(len(segments) + 1),
            "type": kind,
            "atMs": min(at_ms, _MAX_TIMELINE_AT_MS),
            "payload": segment_payload,
        })

    add("TEACHING", 0, {"value": "teaching"})
    board_caption = _timeline_text(caption, 300)
    if board_caption:
        add("CAPTION", 0, {"text": board_caption})
    if speak:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", narration) if part.strip()][:8]
        for index, sentence in enumerate(sentences):
            text = _timeline_text(sentence, 600)
            if text:
                add("SPEAK", 120 + index * 2200, {"text": text})
    for index, instruction in enumerate(instructions[:_MAX_INSTRUCTIONS]):
        add("BOARD", 480 + index * 900, {"instruction": instruction})
    seed = (key + "|" + narration + "|" + str(int(time.time() * 1000))).encode("utf-8")
    last_at = max(segment["atMs"] for segment in segments)
    return validate_timeline({
        "id": "tl-" + hashlib.sha1(seed).hexdigest()[:12],
        "lesson": lesson,
        "startedAt": int(time.time() * 1000),
        "durationMs": min(_MAX_TIMELINE_AT_MS, last_at + 600),
        "segments": segments,
    })


def _finalize_response(payload: WhiteboardInstructionRequest, narration: str, caption: str,
                       instructions: list[dict[str, Any]], provider: str,
                       model: str | None) -> WhiteboardInstructionResponse:
    speak = payload.mode != "Chat-only"
    return WhiteboardInstructionResponse(
        narration=narration,
        caption=caption,
        instructions=instructions,
        speak=speak,
        provider=provider,
        model=model,
        control=_teaching_control(payload.key),
        timeline=_build_timeline(payload.key, payload.lesson, narration, caption, instructions, speak),
    )


def generate_instructions(payload: WhiteboardInstructionRequest) -> WhiteboardInstructionResponse:
    """Generate validated instructions, falling back to deterministic teaching data."""
    try:
        answer, provider, model = complete(_prompt(payload))
        parsed = parse_payload(answer)
        narration = _clean_narration(parsed.get("narration") if parsed else "", payload.prompt)
        instructions = validate_instructions(parsed.get("instructions") if parsed else [])
        caption = str((parsed or {}).get("caption") or "").strip()[:300]
        if _has_banned_output(caption):
            caption = ""
        if narration and instructions:
            return _finalize_response(
                payload, narration, caption or narration[:160], instructions, provider, model
            )
    except ProviderError:
        logger.warning("CRARA whiteboard provider unavailable; using deterministic teaching data")
    except Exception:
        logger.exception("CRARA whiteboard instruction generation failed; using deterministic teaching data")

    fallback = _fallback_response()
    narration = _clean_narration(fallback["narration"], payload.prompt) or fallback["narration"]
    instructions = validate_instructions(fallback["instructions"])
    return _finalize_response(
        payload, narration, fallback["caption"], instructions,
        fallback["provider"], fallback["model"]
    )


def _rate_ok(request: Request) -> bool:
    # Reuse the shared CRARA request throttle without importing route internals.
    bucket = getattr(request.app.state, "crara_whiteboard_requests", None)
    if bucket is None:
        from collections import deque
        bucket = deque()
        request.app.state.crara_whiteboard_requests = bucket
    now = time.monotonic()
    while bucket and now - bucket[0] >= 60:
        bucket.popleft()
    if len(bucket) >= 60:
        return False
    bucket.append(now)
    return True


@router.post("/instructions", response_model=WhiteboardInstructionResponse)
def instructions(request: Request, payload: WhiteboardInstructionRequest):
    _user(request)
    if not _rate_ok(request):
        raise HTTPException(429, "Too many whiteboard requests. Please wait a minute.")
    return generate_instructions(payload)


@router.post("/control")
def issue_control(request: Request, payload: WhiteboardControlRequest):
    """Issue a signed token for a host or authorised co-host control change."""
    user, _ = _require_control_issuer(request, payload.key, payload.authority)
    if payload.type not in _CONTROL_TYPES:
        raise HTTPException(400, "Unsupported whiteboard control type.")
    if payload.type == "cohost" and classroom_role(user) != "host":
        raise HTTPException(403, "Only the classroom host can grant or revoke CRARA co-host control.")
    if payload.type == "mode":
        mode = str(payload.value.get("mode") or "").strip()
        if mode not in CHAT_MODES:
            raise HTTPException(400, "Unsupported chat mode.")
        value = {"mode": mode}
    elif payload.type == "teaching":
        teaching = str(payload.value.get("value") or "").strip()
        if teaching not in _TEACHING_STATES:
            raise HTTPException(400, "Unsupported lesson state.")
        value = {"value": teaching}
    elif payload.type == "cohost":
        enabled = payload.value.get("enabled")
        if not isinstance(enabled, bool):
            raise HTTPException(400, "Cohost control requires a boolean enabled value.")
        value = {"enabled": enabled}
    else:
        value = _sanitize_permissions(payload.value)
    ttl = _COHOST_TTL_SECONDS if payload.type == "cohost" else _CONTROL_TTL_SECONDS
    token = _sign_control({
        "typ": "crara-whiteboard-control",
        "sub": user["id"],
        "room": _clean_key(payload.key),
        "type": payload.type,
        "value": value,
        "exp": int(time.time()) + ttl,
    })
    return {"ok": True, "type": payload.type, "value": value, "token": token}


@router.post("/authorize")
def authorize_control(request: Request, payload: WhiteboardAuthorizeRequest):
    """Verify a control token before applying a remote permission change."""
    _user(request)
    if payload.type not in _CONTROL_TYPES:
        raise HTTPException(400, "Unsupported whiteboard control type.")
    signed = _verify_control(payload.token, {
        "typ": "crara-whiteboard-control",
        "room": _clean_key(payload.key),
        "type": payload.type,
    })
    if not signed or signed.get("value") != payload.value:
        raise HTTPException(403, "This whiteboard control change is not authorised.")
    return {"ok": True}


@router.post("/session")
def save_session(request: Request, payload: WhiteboardSessionRequest):
    _, owner_id = _require_control_issuer(request, payload.key, payload.authority)
    key = _clean_key(payload.key)
    body = payload.model_dump()
    raw = json.dumps(body, ensure_ascii=False)
    if len(raw) > 2_500_000:
        raise HTTPException(413, "This whiteboard session is too large to save.")
    pages = [page for page in payload.pages if isinstance(page, dict)][:_MAX_PAGES]
    saved = {
        "key": key,
        "owner_id": owner_id,
        "lesson": payload.lesson.strip()[:120] or "Hypothesis Testing",
        "pages": pages,
        "pageIndex": payload.pageIndex,
        "chatMode": payload.chatMode if payload.chatMode in CHAT_MODES else "Active",
        "permissions": _sanitize_permissions(payload.permissions),
        "savedAt": int(time.time() * 1000),
    }
    memory._write(SESSION_COLLECTION, memory._doc_id(owner_id, key), saved)
    return {"ok": True, "savedAt": saved["savedAt"], "key": key}


@router.get("/session")
def load_session(request: Request, key: str = "local", authority: str = ""):
    _, owner_id = _require_control_issuer(request, key, authority)
    saved = memory._read(SESSION_COLLECTION, memory._doc_id(owner_id, _clean_key(key)))
    if not saved or saved.get("owner_id") != owner_id:
        return {"ok": True, "session": None}
    return {"ok": True, "session": saved}
