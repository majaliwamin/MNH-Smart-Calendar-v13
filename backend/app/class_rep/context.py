"""Read-only retrieval of authoritative shared MNH calendar context."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from app.database.connection import database
from app.config import TIMEZONE

COLLECTIONS = ("cells", "modules", "facilitators", "examinations", "recurring", "communications", "resources")
MAX_CONTEXT_CHARS = 24000


def _bounded_value(value, depth: int = 0):
    """Keep individual shared records small and JSON-safe for provider context."""
    if depth > 4:
        return str(value)[:300]
    if isinstance(value, str):
        return value[:900]
    if isinstance(value, dict):
        return {str(key)[:100]: _bounded_value(item, depth + 1)
                for key, item in list(value.items())[:30]}
    if isinstance(value, list):
        return [_bounded_value(item, depth + 1) for item in value[:20]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:300]


def build_calendar_context(limit: int = 180) -> tuple[str, str | None]:
    """Build a bounded, read-only snapshot. The assistant cannot mutate calendar data."""
    with database() as connection:
        rows = connection.execute(
            "SELECT col,id,data,updated_at FROM docs WHERE col IN (" + ",".join("?" for _ in COLLECTIONS) + ") ORDER BY updated_at DESC LIMIT ?",
            (*COLLECTIONS, limit),
        ).fetchall()
    grouped = {name: [] for name in COLLECTIONS}
    newest = None
    for row in rows:
        try:
            data = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
        grouped[row["col"]].append({"id": str(row["id"])[:100], **_bounded_value(data)})
        stamp = row["updated_at"]
        if stamp is not None and (newest is None or stamp > newest):
            newest = stamp
    now = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="minutes")
    payload = {"timezone": TIMEZONE, "local_now": now, "records": grouped}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Remove oldest records until the complete JSON document fits; never slice JSON mid-record.
    while len(encoded) > MAX_CONTEXT_CHARS:
        candidates = [name for name, items in grouped.items() if items]
        if not candidates:
            break
        largest = max(candidates, key=lambda name: len(grouped[name]))
        grouped[largest].pop()
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    updated = datetime.fromtimestamp(newest / 1000, ZoneInfo(TIMEZONE)).isoformat(timespec="minutes") if newest else None
    return encoded, updated
