"""Authoritative, database-grounded retrieval for timetable questions.

Every timetable answer must be based on a successful read of the shared records.
A failed query is returned explicitly; it is never reported as "no sessions".
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import TIMEZONE
from app.database.connection import database
from app.services.schedule import WEEKDAY_NAMES, sessions_from_collections

logger = logging.getLogger(__name__)

COLLECTIONS = (
    "cells", "modules", "facilitators", "examinations",
    "recurring", "communications", "resources",
)
MAX_RECORDS = 240

TIMETABLE_TERMS = re.compile(
    r"\b(session|sessions|timetable|schedule|scheduled|class|classes|lecture|lectures|"
    r"exam|examination|exams|module|modules|facilitator|lecturer|venue|hall|room|"
    r"today|tomorrow|yesterday|week|weekly|recurring|upcoming|next\s+class|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)
_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_CODE_RE = re.compile(r"\b([A-Z]{2,6}[-\s]?\d{4})\b")
_WEEKDAY_LOOKUP = {name.casefold(): index for index, name in enumerate(WEEKDAY_NAMES)}


@dataclass
class RetrievalContext:
    """Result of one authoritative retrieval pass."""

    ok: bool
    query: str
    error: str | None = None
    generated_at: str = ""
    timezone: str = TIMEZONE
    filters: dict = field(default_factory=dict)
    sessions: list[dict] = field(default_factory=list)
    unresolved_cells: list[dict] = field(default_factory=list)
    examinations: list[dict] = field(default_factory=list)
    recurring: list[dict] = field(default_factory=list)
    modules: list[dict] = field(default_factory=list)
    facilitators: list[dict] = field(default_factory=list)
    venues: list[str] = field(default_factory=list)
    other_activities: list[dict] = field(default_factory=list)
    newest_record_at: str | None = None
    empty_confirmed: bool = False

    def as_dict(self) -> dict:
        return asdict(self)

    def to_prompt_context(self) -> str:
        """Render a bounded JSON block for the external model.

        The block is source data, not instructions. ``ok`` is included so a
        caller can tell the difference between an empty database result and a
        failed query.
        """
        payload = {
            "retrieval_status": "ok" if self.ok else "failed",
            "authoritative": True,
            "timezone": self.timezone,
            "generated_at": self.generated_at,
            "query": self.query[:500],
            "filters": self.filters,
            "sessions": self.sessions,
            "unresolved_cells": self.unresolved_cells,
            "examinations": self.examinations,
            "recurring_activities": self.recurring,
            "modules": self.modules,
            "facilitators": self.facilitators,
            "venues": self.venues,
            "other_activities": self.other_activities,
            "empty_confirmed": self.empty_confirmed,
            "rules": [
                "Use only these records when describing scheduled academic activity.",
                "Do not invent a session, date, time, module, facilitator or venue.",
                "Do not say a date has no sessions unless retrieval_status is ok and empty_confirmed is true.",
                "If retrieval_status is failed, say the timetable query did not succeed.",
            ],
        }
        if not self.ok:
            payload["error"] = "Timetable database query did not succeed."
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def is_timetable_question(query: str | None) -> bool:
    """Return True when a question should trigger authoritative retrieval."""
    text = str(query or "")
    return bool(TIMETABLE_TERMS.search(text))


def _normal_code(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _parse_filters(query: str, now: datetime) -> dict:
    text = str(query or "").casefold()
    filters: dict = {"text": str(query or "")[:500]}

    match = _DATE_RE.search(text)
    if match:
        try:
            filters["date"] = date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except ValueError:
            pass
    if re.search(r"\btoday\b", text):
        filters["date"] = now.date().isoformat()
    elif re.search(r"\btomorrow\b", text):
        filters["date"] = (now.date() + timedelta(days=1)).isoformat()
    elif re.search(r"\byesterday\b", text):
        filters["date"] = (now.date() - timedelta(days=1)).isoformat()

    monday = now.date() - timedelta(days=now.weekday())
    # General questions are answered from the current academic week. An explicit
    # date/week question overrides this without pulling unrelated weeks into scope.
    filters["default_week_start"] = monday.isoformat()
    if re.search(r"\bthis week\b", text):
        filters["week_start"] = monday.isoformat()
    elif re.search(r"\bnext week\b", text):
        filters["week_start"] = (monday + timedelta(days=7)).isoformat()

    weekday = next((name for name in WEEKDAY_NAMES if name.casefold() in text), None)
    if weekday:
        filters["weekday"] = weekday
        filters["weekday_index"] = _WEEKDAY_LOOKUP[weekday.casefold()]

    codes = sorted({_normal_code(item) for item in _CODE_RE.findall(text) if _normal_code(item)})
    if codes:
        filters["codes"] = codes
    return filters


def _load_records(limit: int = MAX_RECORDS) -> tuple[dict, str | None]:
    collections = {name: {} for name in COLLECTIONS}
    newest = None
    with database() as connection:
        rows = connection.execute(
            "SELECT col,id,data,updated_at FROM docs WHERE col IN (" +
            ",".join("?" for _ in COLLECTIONS) + ") ORDER BY updated_at DESC LIMIT ?",
            (*COLLECTIONS, limit),
        ).fetchall()
    for row in rows:
        if row["col"] not in collections:
            continue
        try:
            data = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        collections[row["col"]][str(row["id"])] = data
        stamp = row["updated_at"]
        if stamp is not None and (newest is None or stamp > newest):
            newest = stamp
    return collections, newest


def _week_starts(now: datetime, filters: dict) -> list[date]:
    monday = now.date() - timedelta(days=now.weekday())
    starts = [monday - timedelta(days=7), monday, monday + timedelta(days=7), monday + timedelta(days=14)]
    explicit = filters.get("date") or filters.get("week_start")
    if explicit:
        try:
            parsed = date.fromisoformat(str(explicit))
            start = parsed - timedelta(days=parsed.weekday())
            if start not in starts:
                starts.append(start)
        except (TypeError, ValueError):
            pass
    return sorted(set(starts))


def _bounded(value, limit: int = 500):
    text = str(value or "").strip()
    return text[:limit]


def retrieve_authoritative_context(query: str | None = "", limit: int = MAX_RECORDS) -> RetrievalContext:
    """Read live shared records and resolve them into authoritative facts.

    The function never mutates the database and never fabricates a date or time.
    On any database failure it returns ``ok=False`` with no empty-result claim.
    """
    question = str(query or "")
    now = datetime.now(ZoneInfo(TIMEZONE))
    filters = _parse_filters(question, now)
    try:
        collections, newest = _load_records(limit)
    except Exception as exc:
        logger.warning("AI timetable retrieval failed category=database_error detail=%s", type(exc).__name__)
        return RetrievalContext(
            ok=False,
            query=question[:500],
            error="Timetable database query did not succeed.",
            generated_at=now.isoformat(timespec="seconds"),
            filters=filters,
        )

    sessions: list[dict] = []
    seen_sessions = set()
    resolved_ids = set()
    for week_start in _week_starts(now, filters):
        for item in sessions_from_collections(collections, week_start=week_start):
            key = (str(item["id"]), item["date"].isoformat(), item["start"])
            if key in seen_sessions:
                continue
            seen_sessions.add(key)
            resolved_ids.add(str(item["id"]))
            sessions.append({
                "id": str(item["id"]),
                "date": item["date"].isoformat(),
                "weekday": item["weekday"],
                "start": item["start"],
                "end": item["end"],
                "code": _bounded(item.get("code")),
                "title": _bounded(item.get("activity")),
                "module_title": _bounded(item.get("module_title")),
                "facilitator": _bounded(item.get("lecturer")),
                "mode": _bounded(item.get("mode")),
                "status": _bounded(item.get("status")),
                "week_start": week_start.isoformat(),
            })
    sessions.sort(key=lambda item: (item["date"], item["start"], item["code"]))

    unresolved = []
    for item_id, data in collections["cells"].items():
        if item_id in resolved_ids:
            continue
        unresolved.append({
            "id": item_id,
            "date_resolved": False,
            "dayIndex": data.get("dayIndex"),
            "weekStart": _bounded(data.get("weekStart")),
            "startTime": _bounded(data.get("startTime")),
            "endTime": _bounded(data.get("endTime")),
            "code": _bounded(data.get("code")),
            "title": _bounded(data.get("title")),
        })

    examinations = []
    for item_id, data in collections["examinations"].items():
        examinations.append({
            "id": item_id,
            "title": _bounded(data.get("title")),
            "date": _bounded(data.get("date"), 40),
            "time": _bounded(data.get("time"), 40),
            "venue": _bounded(data.get("venue"), 200),
            "notes": _bounded(data.get("notes")),
        })

    recurring = []
    for item_id, data in collections["recurring"].items():
        recurring.append({
            "id": item_id,
            "title": _bounded(data.get("title")),
            "day": _bounded(data.get("day"), 40),
            "time": _bounded(data.get("time"), 40),
            "venue": _bounded(data.get("venue"), 200),
            "presenter": _bounded(data.get("presenter")),
            "notes": _bounded(data.get("notes")),
            "enabled": data.get("enabled") is not False,
        })

    modules = []
    for item_id, data in collections["modules"].items():
        modules.append({
            "id": item_id,
            "code": item_id,
            "title": _bounded(data.get("title")),
            "facilitator": _bounded(data.get("facilitator")),
        })

    facilitators = []
    for item_id, data in collections["facilitators"].items():
        facilitators.append({
            "id": item_id,
            "name": _bounded(data.get("name")),
            "title": _bounded(data.get("title")),
            "department": _bounded(data.get("department")),
        })

    venues = set()
    for record in examinations + recurring:
        if record["venue"]:
            venues.add(record["venue"])
    for data in collections["cells"].values():
        if data.get("venue"):
            venues.add(_bounded(data["venue"], 200))

    other_activities = []
    for item_id, data in collections["communications"].items():
        other_activities.append({
            "id": item_id,
            "type": "communication",
            "title": _bounded(data.get("title")),
            "message": _bounded(data.get("message")),
        })
    for item_id, data in collections["resources"].items():
        other_activities.append({
            "id": item_id,
            "type": "resource",
            "title": _bounded(data.get("title") or data.get("name")),
        })

    newest_value = None
    if newest is not None:
        newest_value = datetime.fromtimestamp(newest / 1000, ZoneInfo(TIMEZONE)).isoformat(timespec="minutes")

    return RetrievalContext(
        ok=True,
        query=question[:500],
        generated_at=now.isoformat(timespec="seconds"),
        filters=filters,
        sessions=sessions,
        unresolved_cells=unresolved,
        examinations=examinations,
        recurring=recurring,
        modules=modules,
        facilitators=facilitators,
        venues=sorted(venues),
        other_activities=other_activities,
        newest_record_at=newest_value,
        empty_confirmed=not sessions and not examinations and not recurring,
    )
