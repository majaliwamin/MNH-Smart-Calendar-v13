"""Read-only retrieval of authoritative shared MNH calendar and activity data."""
import json
from datetime import datetime, time as clock_time, timedelta
from zoneinfo import ZoneInfo

from app.database.connection import database
from app.config import TIMEZONE
from app.services.schedule import sessions_from_collections

COLLECTIONS = (
    "cells", "modules", "facilitators", "examinations",
    "recurring", "communications", "resources",
)
MAX_CONTEXT_CHARS = 9000
MAX_ACTIVITY_ITEMS = 60


def _bounded_value(value, depth: int = 0):
    """Keep individual shared records small and JSON-safe for provider context."""
    if depth > 4:
        return str(value)[:300]
    if isinstance(value, str):
        return value[:1400]
    if isinstance(value, dict):
        return {str(key)[:100]: _bounded_value(item, depth + 1)
                for key, item in list(value.items())[:35]}
    if isinstance(value, list):
        return [_bounded_value(item, depth + 1) for item in value[:25]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:300]


def _resolved_schedule(collections: dict, today, now: datetime) -> dict:
    """Resolve raw cells/recurring records into dated, weekday-named sessions.

    Raw cells store a numeric ``dayIndex`` and ``weekStart``. The timetable UI
    resolves those into dates before display; CRARA must receive the same
    resolution instead of being asked to infer calendar days from integers.
    """
    monday = today - timedelta(days=today.weekday())
    weeks = []
    for offset in (0, 7):
        week_start = monday + timedelta(days=offset)
        sessions = []
        for item in sessions_from_collections(collections, week_start=week_start):
            session_date = item["date"]
            starts = datetime.combine(session_date, clock_time.fromisoformat(item["start"]))
            ends = datetime.combine(session_date, clock_time.fromisoformat(item["end"]))
            sessions.append({
                "id": item["id"],
                "date": session_date.isoformat(),
                "weekday": item["weekday"],
                "start": item["start"],
                "end": item["end"],
                "code": item["code"],
                "title": item["activity"],
                "module_title": item["module_title"],
                "lecturer": item["lecturer"],
                "mode": item["mode"],
                "status": item["status"],
                "is_today": session_date == today,
                "is_upcoming": ends >= now.replace(tzinfo=None),
            })
        weeks.append({"week_start": week_start.isoformat(), "sessions": sessions})
    return {
        "note": "Authoritative Monday–Friday sessions resolved from the same live cells and recurring records. "
                "Dates, weekdays and times are already resolved; use this block for today, this week, "
                "next week and upcoming-class questions instead of decoding raw dayIndex values.",
        "weeks": weeks,
    }


def build_calendar_context(query: str | None = None, limit: int = 120) -> tuple[str, str | None]:
    """Build a bounded snapshot from live shared records and non-sensitive audit summaries.

    This reads the same records used by the timetable UI. It does not write, mutate,
    or infer missing calendar facts. Activity history is limited to action summaries.
    """
    text = str(query or "").lower()
    schedule_query = any(term in text for term in (
        "session", "timetable", "schedule", "class", "lecture", "exam", "examination",
        "module", "facilitator", "venue", "today", "tomorrow", "this week", "next week",
        "next class", "upcoming", "recurring",
    ))
    history_query = query is None or any(term in text for term in (
        "recent change", "recent update", "what changed", "activity history", "modified",
        "updated", "who changed", "audit",
    ))
    schedule_query = schedule_query or query is None
    resource_query = any(term in text for term in (
        "resource", "uploaded", "upload", "notes", "lecture note", "document", "pdf",
        "file", "reading", "study material", "learning material",
    ))
    selected = COLLECTIONS if history_query else (
        (("cells", "modules", "facilitators", "examinations", "recurring") + (("resources",) if resource_query else ()))
        if schedule_query else (("resources",) if resource_query else ())
    )
    with database() as connection:
        if selected:
            rows = connection.execute(
                "SELECT col,id,data,updated_at FROM docs WHERE col IN (" +
                ",".join("?" for _ in selected) +
                ") ORDER BY updated_at DESC LIMIT ?",
                (*selected, limit),
            ).fetchall()
        else:
            rows = []
        if history_query:
            try:
                activity_rows = connection.execute(
                    "SELECT at,action,collection,item_id,summary FROM audit "
                    "ORDER BY at DESC LIMIT ?", (MAX_ACTIVITY_ITEMS,)
                ).fetchall()
            except Exception:
                # Older database deployments may not yet have the audit table.
                activity_rows = []
        else:
            activity_rows = []

    grouped = {name: [] for name in COLLECTIONS}
    raw_collections = {name: {} for name in COLLECTIONS}
    newest = None
    for row in rows:
        try:
            data = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
        if row["col"] in raw_collections and isinstance(data, dict):
            raw_collections[row["col"]][str(row["id"])] = data
        # Raw cells/recurring records carry numeric dayIndex values and no dates.
        # Expose only the resolved schedule for timetable questions so the model
        # cannot mix a resolved weekday with an unresolved dayIndex.
        if schedule_query and row["col"] in ("cells", "recurring"):
            continue
        record = _bounded_value(data)
        if not isinstance(record, dict):
            record = {"value": record}
        record["id"] = str(row["id"])[:100]
        grouped[row["col"]].append(record)
        stamp = row["updated_at"]
        if stamp is not None and (newest is None or stamp > newest):
            newest = stamp

    activity = []
    for row in activity_rows:
        activity.append({
            "at": row["at"],
            "action": str(row["action"] or "")[:50],
            "collection": str(row["collection"] or "")[:50],
            "item_id": str(row["item_id"] or "")[:100],
            "summary": str(row["summary"] or "")[:220],
        })
        if row["at"] is not None and (newest is None or row["at"] > newest):
            newest = row["at"]

    now_value = datetime.now(ZoneInfo(TIMEZONE))
    now = now_value.isoformat(timespec="minutes")
    payload = {
        "timezone": TIMEZONE,
        "local_now": now,
        "records": grouped,
        "resolved_schedule": _resolved_schedule(
            raw_collections, now_value.date(), now_value),
        "recent_activity_history": activity,
        "data_scope": "live shared application records; read-only",
        "context_scope": "recent activity" if history_query else "timetable and resources" if schedule_query and resource_query else "resources" if resource_query else "timetable" if schedule_query else "not required for this question",
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Trim oldest records, then oldest activity, without slicing JSON mid-record.
    while len(encoded) > MAX_CONTEXT_CHARS:
        candidates = [name for name, items in grouped.items() if items]
        if candidates:
            largest = max(candidates, key=lambda name: len(grouped[name]))
            grouped[largest].pop()
        elif activity:
            activity.pop()
        else:
            break
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    updated = (
        datetime.fromtimestamp(newest / 1000, ZoneInfo(TIMEZONE)).isoformat(timespec="minutes")
        if newest else None
    )
    return encoded, updated
