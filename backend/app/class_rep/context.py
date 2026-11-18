"""Read-only retrieval of authoritative shared MNH calendar and activity data."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.database.connection import database
from app.config import TIMEZONE

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
    selected = COLLECTIONS if history_query else (
        ("cells", "modules", "facilitators", "examinations", "recurring")
        if schedule_query else ()
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
    newest = None
    for row in rows:
        try:
            data = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
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

    now = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="minutes")
    payload = {
        "timezone": TIMEZONE,
        "local_now": now,
        "records": grouped,
        "recent_activity_history": activity,
        "data_scope": "live shared application records; read-only",
        "context_scope": "recent activity" if history_query else "timetable" if schedule_query else "not required for this question",
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
