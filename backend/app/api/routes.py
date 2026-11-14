"""Versioned-compatible REST endpoints used by the web and Flutter clients."""
import json
import re
import time
from datetime import date, timedelta
from io import BytesIO
from fastapi import APIRouter, Body, Cookie, HTTPException
from fastapi.responses import StreamingResponse
from app.database.connection import database
from app.services.audit_service import write_activity, VISIBLE_ROLES
from app.services.backup_service import list_backups

router = APIRouter(prefix="/api")
ALLOWED_COLLECTIONS = {"cells", "resources", "settings", "modules", "facilitators", "examinations", "recurring", "communications"}
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_. –-]{0,99}$")

from app.services.schedule import DEFAULT_SESSION_RANGES, WEEK_START, minutes as _minutes_checked, cell_interval as _cell_interval  # noqa: E402


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


def current_session(mnh_session: str | None = None):
    """Compatibility helper for the password-free shared workspace."""
    return {"role": "public"}


def require_editor(mnh_session: str | None = None):
    """Legacy write guard; shared workspace writes are open."""
    return {"role": "public"}


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
def export_timetable_xlsx(modules: str | None = None):
    """Download an independent, editable Excel copy of the Monday–Friday timetable.

    `modules` is an optional comma-separated list of module codes to include
    (defaults to the three programme modules).
    """
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
    selected = [code for code in (modules or "").split(",") if code.strip()]
    payload = build_timetable_workbook(collections, selected or None)
    filename = "MNH-Smart-Calendar-Editable-Timetable.xlsx"
    return StreamingResponse(BytesIO(payload), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@router.get("/export/timetable.pdf")
def export_timetable_pdf(modules: str | None = None):
    """Download a fillable-PDF (AcroForm) timetable the user can type into and save.

    `modules` is an optional comma-separated list of module codes to include.
    """
    try:
        from app.services.pdf_export import build_timetable_pdf
    except ImportError as exc:
        raise HTTPException(503, "PDF export is unavailable: install backend requirements (reportlab).") from exc
    with database() as connection:
        rows = connection.execute("SELECT col,id,data FROM docs ORDER BY col,id").fetchall()
    collections = {}
    for row in rows:
        try:
            collections.setdefault(row["col"], {})[row["id"]] = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
    selected = [code for code in (modules or "").split(",") if code.strip()]
    payload = build_timetable_pdf(collections, selected or None)
    filename = "MNH-Smart-Calendar-Editable-Timetable.pdf"
    return StreamingResponse(BytesIO(payload), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@router.get("/export/modules")
def export_module_list():
    """The module catalogue for the export selection UI (defaults + stored modules)."""
    from app.services.excel_export import module_catalogue
    with database() as connection:
        rows = connection.execute("SELECT col,id,data FROM docs WHERE col='modules'").fetchall()
    collections = {"modules": {}}
    for row in rows:
        try:
            collections["modules"][row["id"]] = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
    return {"modules": module_catalogue(collections)}


@router.get("/analytics")
def analytics(year: int | None = None):
    with database() as connection:
        rows = connection.execute(
            "SELECT col,id,data FROM docs WHERE col IN ('cells','modules','facilitators','examinations')"
        ).fetchall()

    modules = {}
    facilitators = {}
    examinations = []
    sessions = []
    for row in rows:
        data = json.loads(row["data"])
        if row["col"] == "modules":
            modules[row["id"]] = data
        elif row["col"] == "facilitators":
            facilitators[row["id"]] = data
        elif row["col"] == "examinations":
            examinations.append(data)
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

    def code_key(value):
        text = str(value or "").replace("\ufffd", "–").replace("â€“", "–").replace("â€”", "—")
        text = re.sub(r"\s*[-\u2013\u2014]\s*", "-", text)
        return re.sub(r"\s+", " ", text).strip().casefold()

    module_records = {}
    for code, data in modules.items():
        display = str(code).replace("\ufffd", "–").replace("â€“", "–").replace("â€”", "—")
        module_records.setdefault(code_key(code), {"code": display, "data": data})

    def module_for(code):
        record = module_records.get(code_key(code))
        return record["data"] if record else {}

    grouped = {}
    for code in modules:
        key = code_key(code)
        grouped.setdefault(key, {"code": module_records[key]["code"], "sessions": []})
    for item in sessions:
        key = code_key(item["code"])
        record = module_records.get(key)
        display = record["code"] if record else str(item["code"]).replace("\ufffd", "–")
        grouped.setdefault(key, {"code": display, "sessions": []})
        grouped[key]["sessions"].append(item)
    module_results = []
    for key in sorted(grouped, key=lambda value: grouped[value]["code"]):
        code = grouped[key]["code"]
        module = module_for(code)
        matching = grouped[key]["sessions"]
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

    # ---- Management dashboard -------------------------------------------------
    academic_years = {str(WEEK_START.year)}
    for examination in examinations:
        exam_year = str(examination.get("date", ""))[:4]
        if exam_year.isdigit():
            academic_years.add(exam_year)
    academic_years = sorted(academic_years)
    selected_year = str(year) if year is not None else academic_years[-1]
    if selected_year not in academic_years:
        raise HTTPException(400, f"Academic year {selected_year} has no recorded data.")

    module_status = []
    on_track = at_risk = no_sessions = 0
    dashboard_modules = [item for item in module_results if code_key(item["code"]) in module_records]
    if not dashboard_modules:
        dashboard_modules = module_results
    for item in dashboard_modules:
        if item["missedSessions"]:
            status, status_label = "at_risk", "At Risk"
            at_risk += 1
        elif item["weeklySessions"] or item["semesterSessions"]:
            status, status_label = "on_track", "On Track"
            on_track += 1
        else:
            status, status_label = "no_sessions", "No Sessions"
            no_sessions += 1
        module_status.append({
            "code": item["code"],
            "title": item["title"],
            "status": status,
            "statusLabel": status_label,
            "missedSessions": item["missedSessions"],
            "weeklySessions": item["weeklySessions"],
        })

    # Attendance and completion need dated session-occurrence/attendance records, which
    # are not stored yet. Report them as unavailable instead of inferring values from the
    # Monday-Friday timetable template (which is a plan, not delivered sessions).
    attendance_available = False
    overall_attendance = None
    attendance_target = 70
    completion_available = False

    known_modes = online + face
    mode_available = known_modes > 0
    face_percent = round(face / known_modes * 100) if known_modes else None
    online_percent = (100 - face_percent) if face_percent is not None else None

    missed_modules = [item for item in module_status if item["status"] == "at_risk"]
    actions = []
    if missed_modules:
        first = missed_modules[0]
        noun = "module" if at_risk == 1 else "modules"
        verb = "needs" if at_risk == 1 else "need"
        detail = f"{first['code']} – {first['missedSessions']} timetable session"
        detail += " marked missed" if first["missedSessions"] == 1 else "s marked missed"
        if len(missed_modules) > 1:
            detail += f" (+{len(missed_modules) - 1} more)"
        actions.append({"tone": "danger", "title": f"{at_risk} {noun} {verb} attention", "detail": detail})
    if not mode_available and total:
        actions.append({
            "tone": "info",
            "title": "Record delivery modes",
            "detail": f"Delivery mode is unspecified for all {total} timetable entries.",
        })
    if not attendance_available:
        actions.append({
            "tone": "info",
            "title": "Start attendance tracking",
            "detail": "Dated attendance records are required for the attendance charts.",
        })
    today_iso = date.today().isoformat()
    upcoming_exams = sorted(
        (item for item in examinations
         if str(item.get("date", ""))[:4] == selected_year and str(item.get("date", "")) >= today_iso),
        key=lambda item: str(item.get("date", "")),
    )
    if upcoming_exams:
        first_exam = upcoming_exams[0]
        actions.append({
            "tone": "info",
            "title": "Confirm next assessments",
            "detail": f"{first_exam.get('title') or 'Examination'} on {first_exam.get('date')}.",
        })
    actions = actions[:3]

    insights = []
    if not attendance_available:
        insights.append("Attendance is not yet tracked. Record dated attendance to calculate the overall rate and weekly trend.")
    elif overall_attendance is not None:
        verdict = "meeting" if overall_attendance >= attendance_target else "below"
        insights.append(f"Overall attendance is {overall_attendance}%, {verdict} the minimum target (≥{attendance_target}%).")
    if missed_modules:
        first = missed_modules[0]
        insights.append(f"{first['code']} requires attention: {first['missedSessions']} timetable session"
                        + (" is" if first["missedSessions"] == 1 else "s are") + " marked missed.")
    if not mode_available:
        insights.append(f"Delivery mode is unrecorded for all {total} timetable entries; set modes to unlock the session-mode distribution.")
    elif face_percent is not None and face_percent >= online_percent:
        insights.append(f"Face-to-face sessions remain dominant ({face_percent}%). Maintain quality delivery.")
    elif online_percent is not None:
        insights.append(f"Online sessions are the larger share ({online_percent}%). Consider increasing engagement.")
    if no_sessions:
        insights.append(f"{no_sessions} module" + (" has" if no_sessions == 1 else "s have")
                        + " no sessions in the current timetable template.")
    elif on_track:
        insights.append(f"{on_track} module" + (" has" if on_track == 1 else "s have")
                        + " scheduled sessions with no missed markers.")
    if not completion_available:
        insights.append("Completion is not yet tracked; record dated session outcomes to calculate module completion.")
    insights = insights[:4]

    dashboard = {
        "reportingPeriod": f"Academic Year {selected_year}",
        "academicYears": academic_years,
        "selectedYear": selected_year,
        "kpis": {
            "modulesOffered": len(dashboard_modules),
            "onTrack": on_track,
            "atRisk": at_risk,
            "noSessions": no_sessions,
            "missedSessions": missed,
            "overallAttendance": overall_attendance,
            "attendanceTarget": attendance_target,
        },
        "attendance": {
            "available": attendance_available,
            "overall": overall_attendance,
            "target": attendance_target,
            "weeks": [],
            "note": "Dated attendance records are required before an overall rate or weekly trend can be calculated.",
        },
        "completion": {
            "available": completion_available,
            "note": "Dated session outcomes are required before module completion can be calculated.",
        },
        "mode": {
            "available": mode_available,
            "known": known_modes,
            "total": total,
            "faceToFace": face,
            "online": online,
            "unspecified": unspecified,
            "faceToFacePercent": face_percent,
            "onlinePercent": online_percent,
            "note": "Session-mode proportions are calculated only from timetable entries with a recorded delivery mode.",
        },
        "moduleStatus": module_status,
        "modulePerformance": [
            {"code": item["code"], "attendance": None, "completion": None}
            for item in dashboard_modules
        ],
        "actions": actions,
        "insights": insights,
    }

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
        "dashboard": dashboard,
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
def session_status():
    return {"authenticated": True, "role": "public"}


@router.get("/reminders")
def reminders_status(mnh_session: str | None = Cookie(default=None)):
    """What reminder delivery can do right now (never credentials; numbers only to editors)."""
    from app.services import reminders, whatsapp
    reminder_settings = reminders.settings()
    editor = bool(current_session(mnh_session))
    return {
        "ok": True,
        "whatsapp": whatsapp.status(),
        "editor": editor,
        "settings": {"enabled": reminder_settings["enabled"],
                     "leadMinutes": reminder_settings["leadMinutes"],
                     "recipientCount": len(reminder_settings["recipients"]),
                     "recipients": reminder_settings["recipients"] if editor else []},
        "recent": reminders.recent(10) if editor else [],
    }


@router.post("/reminders/test")
def reminders_send_test(payload: dict = Body(default={}), mnh_session: str | None = Cookie(default=None)):
    """Send one sample reminder to a single number, using the real message format."""
    require_editor(mnh_session)
    from app.services import reminders, wa_bridge
    to = str(payload.get("to") or "").strip()
    if not to:
        raise HTTPException(400, "Enter the WhatsApp number that should receive the sample.")
    try:
        result = reminders.send_test(to)
    except wa_bridge.BridgeError as error:
        message = str(error)
        raise HTTPException(503 if "not configured" in message.lower() else 502, message) from error
    return {"ok": True, **result}


@router.post("/reminders/run")
def reminders_run_now(mnh_session: str | None = Cookie(default=None)):
    """Check the timetable immediately instead of waiting for the background worker."""
    require_editor(mnh_session)
    from app.services import reminders
    return reminders.run_once()


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
def authenticate(payload: dict = Body(default={})):
    """Backward-compatible endpoint; no password session is created."""
    return {"ok": True, "role": "public"}


@router.post("/logout")
def logout():
    """Backward-compatible no-op; public access has no session to revoke."""
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
                default_ranges = DEFAULT_SESSION_RANGES
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
