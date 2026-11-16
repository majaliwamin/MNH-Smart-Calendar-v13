"""Read-only retrieval of authoritative shared MNH calendar context."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from app.database.connection import database
from app.config import TIMEZONE

COLLECTIONS = ("cells", "modules", "facilitators", "examinations", "recurring", "communications", "resources")


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
        grouped[row["col"]].append({"id": row["id"], **data})
        stamp = row["updated_at"]
        if stamp is not None and (newest is None or stamp > newest):
            newest = stamp
    now = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="minutes")
    payload = {"timezone": TIMEZONE, "local_now": now, "records": grouped}
    updated = datetime.fromtimestamp(newest / 1000, ZoneInfo(TIMEZONE)).isoformat(timespec="minutes") if newest else None
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))[:24000], updated
