"""Pure schedule helpers shared by the API and the Excel exporter (no FastAPI imports)."""
import re
from datetime import date, timedelta

WEEK_START = date(2026, 11, 9)          # Monday
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
LUNCH_START, LUNCH_END = 12 * 60, 13 * 60 + 30   # 12:00–13:30
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
    elif str(data.get("code", data.get("title", ""))).strip().lower() == "journal club":
        start_text, end_text = "13:00", "14:00"
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


def sessions_from_collections(collections: dict) -> list:
    """Resolve every stored weekday session (Mon–Fri only) into display-ready dicts."""
    modules = collections.get("modules", {})
    facilitators = collections.get("facilitators", {})
    out = []
    for item_id, data in collections.get("cells", {}).items():
        interval = cell_interval(item_id, data)
        if not interval:
            continue
        day, start, end, label = interval
        code = str(data.get("code", label)).strip()
        module = modules.get(code, {})
        out.append({
            "id": item_id, "day": day, "date": WEEK_START + timedelta(days=day),
            "weekday": WEEKDAY_NAMES[day], "start_min": start, "end_min": end,
            "start": clock(start), "end": clock(end), "code": code,
            "module_title": str(module.get("title") or data.get("title") or label),
            "lecturer": resolve_lecturer(module, facilitators, str(data.get("facilitator") or "")),
            "activity": str(data.get("title") or label),
            "mode": str(data.get("mode") or "unspecified"),
            "status": str(data.get("status") or data.get("outcome") or "scheduled"),
            "notes": str(data.get("notes") or ""),
        })
    # Fixed recurring Tuesday Journal Club (13:00–14:00) when it is not already a stored cell.
    if not any(s["code"].lower() == "journal club" for s in out):
        for rid, rec in collections.get("recurring", {}).items():
            if str(rec.get("title", "")).strip().lower() == "journal club" and str(rec.get("day", "")).strip().lower() == "tuesday":
                out.append({"id": f"recurring-{rid}", "day": 1, "date": WEEK_START + timedelta(days=1),
                            "weekday": "Tuesday", "start_min": 780, "end_min": 840, "start": "13:00", "end": "14:00",
                            "code": "Journal Club", "module_title": "Journal Club", "lecturer": "",
                            "activity": "Journal Club", "mode": "unspecified", "status": "scheduled",
                            "notes": str(rec.get("notes") or "")})
    out.sort(key=lambda s: (s["day"], s["start_min"], s["end_min"], s["code"]))
    return out


def overlaps_lunch(session: dict) -> bool:
    return session["start_min"] < LUNCH_END and session["end_min"] > LUNCH_START
