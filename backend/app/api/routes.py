"""Versioned-compatible REST endpoints used by the web and Flutter clients."""
import json
import re
import time
from datetime import date, timedelta
from io import BytesIO
from fastapi import APIRouter, Body, Cookie, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from app.config import COOKIE_SECURE, SESSION_SECONDS
from app.database.connection import database
from app.services.authentication import role_for_password, create_session, get_session, delete_session
from app.services.audit_service import write_activity, VISIBLE_ROLES
from app.services.backup_service import list_backups

router = APIRouter(prefix="/api")
ALLOWED_COLLECTIONS = {"cells", "resources", "settings", "modules", "facilitators", "examinations", "recurring", "communications"}
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_. –-]{0,99}$")
COOKIE_NAME = "mnh_session"

from app.services.schedule import DEFAULT_SESSION_RANGES, minutes as _minutes_checked, cell_interval as _cell_interval  # noqa: E402


def _minutes(value: str) -> int | None:
    return _minutes_checked(value)


def _validate_restore_intervals(cleaned):
    intervals = []
    recurring = []
    for collection, item_id, raw_data, _ in cleaned:
        data = json.loads(raw_data)
        if collection == "cells":
            interval = _cell_interval(item_id, data)
            if interval:
                intervals.append(interval)
        elif collection == "recurring":
            recurring.append(data)
    by_day = {}
    for day, start, end, label in intervals:
        for other_start, other_end, other_label in by_day.setdefault(day, []):
            if start < other_end and end > other_start:
                raise HTTPException(400, f"Backup contains overlapping sessions: {label} and {other_label}.")
        by_day[day].append((start, end, label))
    for recurring_item in recurring:
        if str(recurring_item.get("day", "")).strip().lower() != "tuesday":
            continue
        match = re.fullmatch(r"\s*(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})\s*", str(recurring_item.get("time", "")))
        if not match:
            continue
        start, end = _minutes(match.group(1)), _minutes(match.group(2))
        if start is None or end is None or end <= start:
            continue
        recurring_title = str(recurring_item.get("title", "")).strip().lower()
        for other_start, other_end, other_title in by_day.get(1, []):
            if other_title.strip().lower() == recurring_title:
                continue
            if other_start < end and other_end > start:
                raise HTTPException(400, "Backup contains a Tuesday session overlapping a recurring activity.")


def current_session(mnh_session: str | None):
    return get_session(mnh_session)


def require_editor(mnh_session: str | None):
    session = current_session(mnh_session)
    if not session:
        raise HTTPException(status_code=401, detail="Please sign in with an authorised editing password.")
    return session


@router.get("/ping")
def ping():
    return {"ok": True, "storage": "shared"}


@router.get("/health")
def health():
    with database() as c:
        count = c.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        last = c.execute("SELECT MAX(at) FROM audit").fetchone()[0]
    backups = list_backups()
    return {"ok": True, "storage": "shared", "documents": count,
            "last_change": last, "backup_count": len(backups),
            "last_backup": backups[0].stat().st_mtime if backups else None}


@router.get("/export/timetable.xlsx")
def export_timetable_xlsx():
    """Download an independent, editable Excel copy of the Monday–Friday timetable."""
    try:
        from app.services.excel_export import build_timetable_workbook
    except ImportError as exc:
        raise HTTPException(503, "Excel export is unavailable: install backend requirements (openpyxl).") from exc
    with database() as connection:
        rows = connection.execute("SELECT col,id,data FROM docs ORDER BY col,id").fetchall()
    collections = {}
    for row in rows:
        try:
            collections.setdefault(row["col"], {})[row["id"]] = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
    payload = build_timetable_workbook(collections)
    filename = "MNH-Smart-Calendar-Editable-Timetable.xlsx"
    return StreamingResponse(BytesIO(payload), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@router.get("/analytics")
def analytics(mnh_session: str | None = Cookie(default=None)):
    session = current_session(mnh_session)
    management_roles = {"hod", "coordinator", "executive_dean"}
    if not session or session.get("role") not in management_roles:
        raise HTTPException(403, "Analytics are restricted to HOD, coordinator and executive dean accounts.")

    with database() as connection:
        rows = connection.execute(
            "SELECT col,id,data FROM docs WHERE col IN ('cells','modules','facilitators')"
        ).fetchall()

    modules = {}
    facilitators = {}
    sessions = []
    for row in rows:
        data = json.loads(row["data"])
        if row["col"] == "modules":
            modules[row["id"]] = data
        elif row["col"] == "facilitators":
            facilitators[row["id"]] = data
        elif row["col"] == "cells":
            item_id = row["id"]
            legacy = re.fullmatch(r"(\d+)_(\d+)", item_id)
            if legacy:
                slot, day = int(legacy.group(1)), int(legacy.group(2))
                if day >= 5:
                    continue
                fallback = DEFAULT_SESSION_RANGES[slot] if slot < len(DEFAULT_SESSION_RANGES) else ""
                match = re.fullmatch(r"(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})", str(data.get("timeLabel", "")))
                start_text, end_text = (match.group(1), match.group(2)) if match else tuple(fallback.split("-")) if fallback else ("", "")
            else:
                day = data.get("dayIndex")
                start_text, end_text = str(data.get("startTime", "")), str(data.get("endTime", ""))
                if type(day) is not int or day < 0 or day >= 5:
                    continue
            start, end = _minutes(start_text), _minutes(end_text)
            if start is None or end is None or end <= start:
                continue
            code = str(data.get("moduleCode") or data.get("code") or data.get("title") or item_id)
            if code.lower() == "journal club":
                continue
            status = str(data.get("status", "scheduled")).lower()
            mode = str(data.get("mode", data.get("delivery", "unspecified"))).lower().replace("-", "_").replace(" ", "_")
            sessions.append({"code": code, "day": day, "minutes": end - start, "status": status, "mode": mode})

    def module_for(code):
        return modules.get(code, {})

    module_codes = set(modules) | {item["code"] for item in sessions}
    module_results = []
    for code in sorted(module_codes):
        module = module_for(code)
        matching = [item for item in sessions if item["code"] == code]
        weekly = [item for item in matching if 0 <= item["day"] < 5]
        total_minutes = sum(item["minutes"] for item in matching)
        weekly_minutes = sum(item["minutes"] for item in weekly)
        module_results.append({
            "code": code,
            "title": str(module.get("title") or code),
            "weeklySessions": len(weekly),
            "weeklyHours": round(weekly_minutes / 60, 2),
            "semesterSessions": len(matching),
            "semesterHours": round(total_minutes / 60, 2),
            "semesterTracked": False,
            "targetSessions": module.get("semesterTargetSessions"),
            "targetHours": module.get("semesterTargetHours"),
            "missedSessions": sum(1 for item in matching if item["status"] == "missed"),
            "completedSessions": sum(1 for item in matching if item["status"] == "completed"),
            "onlineSessions": sum(1 for item in matching if item["mode"] in ("online", "virtual", "remote")),
            "faceToFaceSessions": sum(1 for item in matching if item["mode"] in ("face_to_face", "physical", "in_person", "inperson")),
        })

    total = len(sessions)
    missed = sum(1 for item in sessions if item["status"] == "missed")
    online = sum(1 for item in sessions if item["mode"] in ("online", "virtual", "remote"))
    face = sum(1 for item in sessions if item["mode"] in ("face_to_face", "physical", "in_person", "inperson"))
    unspecified = total - online - face
    return {
        "summary": {
            "sessions": total,
            "hours": round(sum(item["minutes"] for item in sessions) / 60, 2),
            "missed": missed,
            "missedPercent": round(missed / total * 100, 1) if total else 0,
            "online": online,
            "faceToFace": face,
            "unspecified": unspecified,
        },
        "modules": module_results,
        "counts": {"cells": total, "modules": len(modules), "facilitators": len(facilitators)},
        "delivery_modes": {"online": online, "face_to_face": face, "unspecified": unspecified},
        "recorded_additions": total,
        "missed_sessions": missed,
        "note": "Weekly figures describe the configured Monday–Friday timetable template, not a verified attendance register. Semester-to-date sessions and hours are intentionally not reported until dated session-occurrence and attendance records are recorded; timetable template rows must not be mistaken for sessions already delivered. Delivery-mode and missed markers currently describe the saved timetable entries. Set each module's semester targets in Modules; target progress will appear once dated semester records are available."
    }


@router.get("/history")
def history():
    with database() as c:
        rows = c.execute(
            "SELECT at,role,action,collection,item_id,summary FROM audit "
            "WHERE action='added' AND collection IN ('cells','resources','examinations','recurring','communications') ORDER BY seq DESC LIMIT 100"
        ).fetchall()
    return [{"at": r["at"], "role": VISIBLE_ROLES.get(r["role"], "Staff"),
             "action": "added", "collection": r["collection"], "id": r["item_id"], "summary": r["summary"]}
            for r in rows]


@router.get("/backup")
def backup_json():
    with database() as c:
        rows = c.execute("SELECT col,id,data FROM docs ORDER BY col,id").fetchall()
    return {"format": "mnh-calendar-backup", "version": 1, "created_at": int(time.time()*1000),
            "documents": [{"col": r["col"], "id": r["id"], "data": json.loads(r["data"])} for r in rows]}


@router.get("/session")
def session_status(mnh_session: str | None = Cookie(default=None)):
    session = current_session(mnh_session)
    return {"authenticated": bool(session), "role": session["role"] if session else "student"}


@router.get("/export")
def export_all():
    with database() as c:
        rows = c.execute("SELECT col,id,data FROM docs ORDER BY col,id").fetchall()
    return [{"col": r["col"], "id": r["id"], "data": json.loads(r["data"])} for r in rows]


@router.get("/col/{collection}")
def get_collection(collection: str):
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(404, "not found")
    with database() as c:
        rows = c.execute("SELECT id,data FROM docs WHERE col=? ORDER BY id", (collection,)).fetchall()
    return [{"id": r["id"], "data": json.loads(r["data"])} for r in rows]


@router.post("/auth")
def authenticate(request: Request, response: Response, payload: dict = Body(...)):
    password = str(payload.get("password", ""))[:256]
    role = role_for_password(password)
    if not role:
        time.sleep(0.25)
        raise HTTPException(401, "Incorrect password. Editing remains locked.")
    token = create_session(role)
    forwarded = request.headers.get("x-forwarded-proto", "").lower() if request else ""
    is_https = request.url.scheme == "https" or forwarded == "https"
    secure = COOKIE_SECURE == "true" or (COOKIE_SECURE == "auto" and is_https)
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=secure, samesite="none" if secure else "lax", path="/")
    return {"ok": True, "role": role}


@router.post("/logout")
def logout(response: Response, mnh_session: str | None = Cookie(default=None)):
    delete_session(mnh_session)
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax")
    return {"ok": True}


@router.post("/restore")
def restore(payload: dict = Body(...), mnh_session: str | None = Cookie(default=None)):
    require_editor(mnh_session)
    if payload.get("format") != "mnh-calendar-backup" or not isinstance(payload.get("documents"), list):
        raise HTTPException(400, "Unsupported backup format.")
    documents = payload["documents"]
    if len(documents) > 10000:
        raise HTTPException(400, "Backup contains too many records.")
    cleaned = []
    seen_documents = set()
    for item in documents:
        if not isinstance(item, dict):
            raise HTTPException(400, "Backup contains an invalid record.")
        col, item_id, data = item.get("col"), str(item.get("id", "")), item.get("data")
        if col not in ALLOWED_COLLECTIONS or not NAME.fullmatch(item_id) or not isinstance(data, dict):
            raise HTTPException(400, "Backup contains an invalid record.")
        if col == "recurring" and str(data.get("day", "")).strip().lower() in ("sat", "saturday"):
            raise HTTPException(400, "Recurring academic activities must be scheduled Monday to Friday.")
        if col == "cells":
            legacy_day = re.fullmatch(r"\d+_(\d+)", item_id)
            day_index = data.get("dayIndex")
            if (legacy_day and int(legacy_day.group(1)) >= 5) or ("dayIndex" in data and (type(day_index) is not int or day_index < 0 or day_index >= 5)):
                raise HTTPException(400, "Timetable sessions must be assigned Monday to Friday.")
            if ("startTime" in data) != ("endTime" in data) or (("startTime" in data or "endTime" in data) and not isinstance(day_index, int)):
                raise HTTPException(400, "Custom sessions require a weekday, start time and end time.")
            if "startTime" in data:
                start, end = str(data.get("startTime", "")), str(data.get("endTime", ""))
                if _minutes(start) is None or _minutes(end) is None or start >= end:
                    raise HTTPException(400, "Backup contains an invalid session time interval.")
        identity = (col, item_id)
        if identity in seen_documents:
            raise HTTPException(400, "Backup contains duplicate records.")
        seen_documents.add(identity)
        cleaned.append((col, item_id, json.dumps(data, ensure_ascii=False), int(time.time()*1000)))
    _validate_restore_intervals(cleaned)
    with database() as c:
        c.execute("DELETE FROM docs")
        c.executemany("INSERT INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)", cleaned)
    return {"ok": True, "restored": len(cleaned)}


@router.put("/doc/{collection}/{item_id}")
def put_document(collection: str, item_id: str, data: dict = Body(...), mnh_session: str | None = Cookie(default=None)):
    session = require_editor(mnh_session)
    if collection not in ALLOWED_COLLECTIONS or not NAME.fullmatch(item_id):
        raise HTTPException(404, "not found")
    if collection == "modules" and (not str(data.get("title", "")).strip() or len(str(data.get("title", ""))) > 160):
        raise HTTPException(400, "A valid module title is required.")
    if collection == "recurring" and str(data.get("day", "")).strip().lower() in ("sat", "saturday"):
        raise HTTPException(400, "Recurring academic activities must be scheduled Monday to Friday.")
    if collection == "cells":
        legacy_day = re.fullmatch(r"\d+_(\d+)", item_id)
        day_index = data.get("dayIndex")
        if (legacy_day and int(legacy_day.group(1)) >= 5) or ("dayIndex" in data and (type(day_index) is not int or day_index < 0 or day_index >= 5)):
            raise HTTPException(400, "Timetable sessions must be assigned Monday to Friday.")
        if ("startTime" in data) != ("endTime" in data) or (("startTime" in data or "endTime" in data) and not isinstance(day_index, int)):
            raise HTTPException(400, "Custom sessions require a weekday, start time and end time.")
        if "startTime" in data or "endTime" in data:
            start, end = str(data.get("startTime", "")), str(data.get("endTime", ""))
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", start) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", end):
                raise HTTPException(400, "Session start and end times must use HH:MM format.")
            if start >= end:
                raise HTTPException(400, "Session end time must be later than its start time.")
            day_index = data.get("dayIndex")
            if isinstance(day_index, int):
                default_ranges = ["08:00-10:00", "10:00-12:00", "12:00-13:30", "13:30-15:30", "15:30-17:30", "17:30-19:00", "19:00-21:00"]
                with database() as c:
                    existing_rows = c.execute("SELECT id,data FROM docs WHERE col='cells' AND id<>?", (item_id,)).fetchall()
                    recurring_rows = c.execute("SELECT data FROM docs WHERE col='recurring'").fetchall()
                new_start, new_end = int(start[:2]) * 60 + int(start[3:]), int(end[:2]) * 60 + int(end[3:])
                for existing_row in existing_rows:
                    existing_id = existing_row["id"]
                    existing_data = json.loads(existing_row["data"])
                    legacy = re.fullmatch(r"(\d+)_(\d+)", existing_id)
                    existing_day = int(legacy.group(2)) if legacy else existing_data.get("dayIndex")
                    if existing_day != day_index:
                        continue
                    if legacy:
                        slot = int(legacy.group(1))
                        fallback = default_ranges[slot] if 0 <= slot < len(default_ranges) else ""
                    else:
                        fallback = ""
                    if existing_data.get("startTime") and existing_data.get("endTime"):
                        range_text = str(existing_data["startTime"]) + "-" + str(existing_data["endTime"])
                    elif legacy:
                        label = str(existing_data.get("timeLabel", ""))
                        match = re.fullmatch(r"\s*(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})\s*", label)
                        range_text = (match.group(1) + "-" + match.group(2)) if match else fallback
                    else:
                        range_text = ""
                    parts = range_text.split("-")
                    if len(parts) != 2 or not re.fullmatch(r"\d{1,2}:\d{2}", parts[0]) or not re.fullmatch(r"\d{1,2}:\d{2}", parts[1]):
                        continue
                    old_start = int(parts[0][:2]) * 60 + int(parts[0][3:])
                    old_end = int(parts[1][:2]) * 60 + int(parts[1][3:])
                    if new_start < old_end and new_end > old_start:
                        raise HTTPException(409, f"Session overlaps existing timetable entry {existing_id}.")
                if day_index == 1:
                    for recurring_row in recurring_rows:
                        recurring_data = json.loads(recurring_row["data"])
                        if str(recurring_data.get("title", "")).strip().lower() != "journal club" or str(recurring_data.get("day", "")).strip().lower() != "tuesday":
                            continue
                        if str(data.get("code", data.get("title", ""))).strip().lower() == "journal club":
                            continue
                        recurring_range = re.fullmatch(r"\s*(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})\s*", str(recurring_data.get("time", "")))
                        if recurring_range:
                            rs = int(recurring_range.group(1)[:2]) * 60 + int(recurring_range.group(1)[3:])
                            re_ = int(recurring_range.group(2)[:2]) * 60 + int(recurring_range.group(2)[3:])
                            if new_start < re_ and new_end > rs:
                                raise HTTPException(409, "Session overlaps the recurring Tuesday Journal Club.")
    with database() as c:
        exists = c.execute("SELECT 1 FROM docs WHERE col=? AND id=?", (collection, item_id)).fetchone()
        c.execute("INSERT INTO docs(col,id,data,updated_at) VALUES(?,?,?,?) "
                  "ON CONFLICT(col,id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at",
                  (collection, item_id, json.dumps(data, ensure_ascii=False), int(time.time()*1000)))
        if not exists and collection in ("cells", "resources", "examinations", "recurring", "communications"):
            description = next((str(data.get(k, "")).strip() for k in
                                ("title", "activity", "message", "text", "name", "module", "code", "label") if data.get(k)), "")
            kind = "session" if collection == "cells" else "activity"
            summary = "Added %s%s" % (kind, (": " + description[:170]) if description else "")
            write_activity(c, session["role"], "added", collection, item_id, summary)
    return {"ok": True}


@router.delete("/doc/{collection}/{item_id}")
def delete_document(collection: str, item_id: str, mnh_session: str | None = Cookie(default=None)):
    require_editor(mnh_session)
    if collection not in ALLOWED_COLLECTIONS or not NAME.fullmatch(item_id):
        raise HTTPException(404, "not found")
    with database() as c:
        c.execute("DELETE FROM docs WHERE col=? AND id=?", (collection, item_id))
    return {"ok": True}
