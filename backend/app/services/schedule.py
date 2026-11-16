"""Pure schedule helpers shared by the API and the Excel exporter (no FastAPI imports)."""
import re
from datetime import date, timedelta

WEEK_START = date(2026, 11, 9)          # Monday
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
LUNCH_START, LUNCH_END = 12 * 60, 13 * 60 + 30   # 12:00–13:30
RECURRING_ACTIVITIES = (
    {"id": "journal-club", "title": "Journal Club", "day": 1, "weekday": "Tuesday", "start": "13:00", "end": "14:00"},
    {"id": "seminar-mnh", "title": "Seminar in MNH", "day": 3, "weekday": "Thursday", "start": "10:00", "end": "12:00"},
)
DEFAULT_SESSION_RANGES = (
    "08:00-10:00", "10:00-12:00", "12:00-13:30", "13:30-15:30",
    "15:30-17:30", "17:30-19:00", "19:00-21:00",
)
_TITLES = r"\b(professor|prof|doctor|dr|mr|mrs|ms|miss|mx)\b\.?"


def minutes(value: str):
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value or ""):
        return None
    return int(value[:2]) * 60 + int(value[3:])


def clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def cell_interval(item_id: str, data: dict):
    """Return (day_index, start_min, end_min, label) for a stored timetable cell, or None."""
    legacy = re.fullmatch(r"(\d+)_(\d+)", item_id)
    if legacy:
        day = int(legacy.group(2))
        slot = int(legacy.group(1))
        fallback = DEFAULT_SESSION_RANGES[slot] if 0 <= slot < len(DEFAULT_SESSION_RANGES) else ""
    else:
        day = data.get("dayIndex")
        fallback = ""
    if type(day) is not int or day < 0 or day >= 5:
        return None
    if data.get("startTime") and data.get("endTime"):
        start_text, end_text = str(data["startTime"]), str(data["endTime"])
    elif legacy:
        match = re.fullmatch(r"\s*(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})\s*", str(data.get("timeLabel", "")))
        start_text, end_text = (match.group(1), match.group(2)) if match else tuple(fallback.split("-")) if fallback else ("", "")
    else:
        return None
    start, end = minutes(start_text.zfill(5)), minutes(end_text.zfill(5))
    if start is None or end is None or end <= start:
        return None
    return day, start, end, str(data.get("code", data.get("title", item_id)))


def _normal(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", re.sub(_TITLES, "", str(name or "").lower())).strip()


def resolve_lecturer(module: dict, facilitators: dict, fallback: str = "") -> str:
    """Lecturer comes from the Modules + Facilitators records; never invented."""
    module = module or {}
    lecturer = str(module.get("facilitator") or fallback or "").strip()
    if lecturer.lower() == "not specified":
        lecturer = ""
    fid = str(module.get("facilitatorId") or "")
    if fid and fid in facilitators:
        return str(facilitators[fid].get("name") or lecturer)
    wanted = _normal(lecturer)
    if wanted:
        for record in facilitators.values():
            candidate = str(record.get("name") or "")
            normal = _normal(candidate)
            if normal == wanted or normal.endswith(wanted):
                return candidate
    return lecturer


def initials(name: str) -> str:
    """Initials that ignore professional titles: 'Dr D Mzinza' -> 'DM'."""
    words = [w for w in re.split(r"\s+", re.sub(_TITLES, " ", str(name or ""), flags=re.I).replace(".", " ")) if w]
    if not words:
        return ""
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


def sessions_from_collections(collections: dict, week_start: date | None = None) -> list:
    """Resolve stored weekday sessions for the requested Monday–Friday academic week."""
    week_start = week_start or WEEK_START
    modules = collections.get("modules", {})
    facilitators = collections.get("facilitators", {})
    out = []
    for item_id, data in collections.get("cells", {}).items():
        if str(data.get("weekStart") or week_start.isoformat()) != week_start.isoformat():
            continue
        interval = cell_interval(item_id, data)
        if not interval:
            continue
        day, start, end, label = interval
        code = str(data.get("code", label)).strip()
        module = modules.get(code, {})
        out.append({
            "id": item_id, "day": day, "date": week_start + timedelta(days=day),
            "weekday": WEEKDAY_NAMES[day], "start_min": start, "end_min": end,
            "start": clock(start), "end": clock(end), "code": code,
            "module_title": str(module.get("title") or data.get("title") or label),
            "lecturer": resolve_lecturer(module, facilitators, str(data.get("facilitator") or "")),
            "activity": str(data.get("title") or label),
            "mode": str(data.get("mode") or "unspecified"),
            "status": str(data.get("status") or data.get("outcome") or "scheduled"),
            "notes": str(data.get("notes") or ""),
        })
    # Recurring records are editable shared documents. Keep the two programme defaults
    # only for a brand-new database; once records exist, enabled flags control visibility.
    stored_recurring = collections.get("recurring")
    recurring_items = []
    if stored_recurring is None:
        recurring_items = [dict(item, presenter="", enabled=True) for item in RECURRING_ACTIVITIES]
    else:
        for item_id, data in stored_recurring.items():
            if data.get("enabled") is False:
                continue
            title = str(data.get("title") or item_id).strip()
            weekday = str(data.get("day") or "").strip()
            day = next((i for i, name in enumerate(WEEKDAY_NAMES) if name.casefold() == weekday.casefold()), None)
            match = re.fullmatch(r"\s*(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})\s*", str(data.get("time") or ""))
            if day is None or not match:
                continue
            recurring_items.append({"id": item_id, "title": title, "day": day, "weekday": WEEKDAY_NAMES[day],
                                    "start": match.group(1), "end": match.group(2),
                                    "presenter": str(data.get("presenter") or ""), "notes": str(data.get("notes") or "")})
    recurring_codes = {str(item["title"]).casefold() for item in recurring_items}
    out = [session for session in out if session["code"].casefold() not in recurring_codes]
    for item in recurring_items:
        start, end = minutes(item["start"]), minutes(item["end"])
        if start is None or end is None or end <= start:
            continue
        out.append({
            "id": f"recurring-{item['id']}", "day": item["day"],
            "date": week_start + timedelta(days=item["day"]),
            "weekday": item["weekday"], "start_min": start, "end_min": end,
            "start": item["start"], "end": item["end"], "code": item["title"],
            "module_title": item["title"], "lecturer": item["presenter"],
            "activity": item["title"], "mode": "unspecified", "status": "scheduled",
            "notes": str(item.get("notes") or ""),
        })
    out.sort(key=lambda s: (s["day"], s["start_min"], s["end_min"], s["code"]))
    return out


def overlaps_lunch(session: dict) -> bool:
    return session["start_min"] < LUNCH_END and session["end_min"] > LUNCH_START
