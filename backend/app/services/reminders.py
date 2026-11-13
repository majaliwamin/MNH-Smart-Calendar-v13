"""WhatsApp reminders: message every listed person before a session starts.

Lead times are chosen in the interface (10, 20 and 30 minutes by default) and stored in
the shared `settings/reminders` document, so every device and the server agree:

    {"enabled": true, "leadMinutes": [10, 20, 30], "recipients": ["+265881988156"]}

A background worker checks every few seconds, sends once per session, lead time and
number, and records each attempt in `reminder_log` so a reminder is never repeated.
"""
import json
import threading
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import TIMEZONE
from app.database.connection import database
from app.services import whatsapp
from app.services.schedule import WEEK_START, sessions_from_collections

TZ = ZoneInfo(TIMEZONE)
DEFAULT_LEADS = (10, 20, 30)
WINDOW_SECONDS = 120  # a late tick still delivers instead of skipping the reminder

LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS reminder_log(
  ikey TEXT PRIMARY KEY,
  sent_at TEXT NOT NULL,
  phone TEXT,
  code TEXT,
  starts TEXT,
  lead INTEGER,
  status TEXT,
  detail TEXT
)
"""


def ensure_log() -> None:
    with database() as connection:
        connection.execute(LOG_SCHEMA)


# ---- settings -------------------------------------------------------------
def settings() -> dict:
    """Reminder settings with safe defaults; bad values never break the worker."""
    data = {}
    with database() as connection:
        row = connection.execute("SELECT data FROM docs WHERE col='settings' AND id='reminders'").fetchone()
    if row:
        try:
            data = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            data = {}
    leads = []
    for value in data.get("leadMinutes", DEFAULT_LEADS):
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= minutes <= 240 and minutes not in leads:
            leads.append(minutes)
    recipients = []
    for value in data.get("recipients", []):
        text = str(value or "").strip()
        if text:
            try:
                number = whatsapp.normalise_phone(text)
            except whatsapp.WhatsAppError:
                continue
            if number not in recipients:
                recipients.append(number)
    return {
        "enabled": bool(data.get("enabled", True)),
        "leadMinutes": sorted(leads or list(DEFAULT_LEADS)),
        "recipients": recipients,
    }


# ---- sessions ------------------------------------------------------------
def _collections() -> dict:
    with database() as connection:
        rows = connection.execute("SELECT col,id,data FROM docs").fetchall()
    collections = {}
    for row in rows:
        try:
            collections.setdefault(row["col"], {})[row["id"]] = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
    return collections


def week_sessions(now: datetime | None = None) -> list:
    """Sessions for the academic week that contains `now`, with real dates attached."""
    now = now or datetime.now(TZ)
    try:
        sessions = sessions_from_collections(_collections())
    except Exception:  # a broken record must not stop the reminder worker
        return []
    today = now.date()
    offset_days = (today - WEEK_START).days
    monday = WEEK_START + timedelta(days=(offset_days // 7) * 7)
    for session in sessions:
        session["date"] = monday + timedelta(days=session["day"])
    return sessions


def _start_minutes(session: dict) -> int | None:
    if isinstance(session.get("start_min"), int):
        return session["start_min"]
    text = str(session.get("start") or "")
    if len(text) == 5 and text[2] == ":":
        return int(text[:2]) * 60 + int(text[3:])
    return None


def due_reminders(sessions, now: datetime, leads, window_seconds: int = WINDOW_SECONDS):
    """[(session, lead)] for every reminder whose moment has arrived inside the window."""
    due = []
    for session in sessions:
        start_minutes = _start_minutes(session)
        session_date = session.get("date")
        if start_minutes is None or not isinstance(session_date, date):
            continue
        starts_at = datetime(session_date.year, session_date.month, session_date.day, tzinfo=TZ) + timedelta(minutes=start_minutes)
        for lead in leads:
            elapsed = (now - (starts_at - timedelta(minutes=int(lead)))).total_seconds()
            if 0 <= elapsed < window_seconds:
                due.append((session, int(lead)))
    due.sort(key=lambda item: (item[0]["date"], _start_minutes(item[0]) or 0, -item[1]))
    return due


# ---- messages ------------------------------------------------------------
def reminder_text(session: dict, lead: int, sender: str | None = None) -> str:
    """The message every recipient receives, naming the sender, module and lecturer."""
    sender = sender or whatsapp.WHATSAPP_SENDER_NAME
    when = ""
    session_date = session.get("date")
    if isinstance(session_date, date):
        when = " " + session_date.strftime("%d %b %Y")
    title = str(session.get("module_title") or "").strip()
    code = str(session.get("code") or session.get("activity") or "Session").strip()
    heading = f"Reminder: *{code}*" + (f" — {title}" if title and title != code else "")
    lines = [
        f"*{sender}*",
        heading,
        f"{session.get('weekday', '')}{when} · {session.get('start', '')}–{session.get('end', '')}".strip(),
    ]
    lecturer = str(session.get("lecturer") or "").strip()
    lines.append(f"Lecturer: {lecturer}" if lecturer else "Lecturer: not assigned")
    lines.append(f"Starts in {int(lead)} minutes." if int(lead) else "Starting now.")
    lines.append("Sent automatically by the timetable.")
    return "\n".join(line for line in lines if line)


def test_message(now: datetime | None = None) -> str:
    """Sample reminder used by the 'send test' button — same format as the real ones."""
    now = now or datetime.now(TZ)
    sample = {
        "code": "MNH-TT-TEST",
        "module_title": "Reminder test",
        "weekday": "Today",
        "date": now.date(),
        "start": "10:00",
        "end": "12:00",
        "lecturer": "Programme office (sample)",
    }
    return reminder_text(sample, 10)


# ---- sending -------------------------------------------------------------
def _key(session: dict, lead: int, phone: str) -> str:
    session_date = session.get("date")
    day = session_date.isoformat() if isinstance(session_date, date) else ""
    return f"{day}|{session.get('code', '')}|{session.get('start', '')}|{lead}|{phone}"


def already_sent(key: str) -> bool:
    with database() as connection:
        row = connection.execute("SELECT 1 FROM reminder_log WHERE ikey=?", (key,)).fetchone()
    return bool(row)


def record(key: str, session: dict, lead: int, phone: str, status: str, detail: str = "") -> None:
    session_date = session.get("date")
    starts = ""
    if isinstance(session_date, date):
        starts = f"{session_date.isoformat()} {session.get('start', '')}".strip()
    with database() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO reminder_log(ikey,sent_at,phone,code,starts,lead,status,detail) VALUES(?,?,?,?,?,?,?,?)",
            (key, datetime.now(TZ).isoformat(timespec="seconds"), phone, str(session.get("code", "")), starts, lead, status, detail[:400]),
        )


def run_once(now: datetime | None = None, dry_run: bool = False) -> dict:
    """Send every reminder that is due right now. Safe to call repeatedly."""
    now = now or datetime.now(TZ)
    config = settings()
    if not config["enabled"] and not dry_run:
        return {"ok": True, "sent": 0, "checked": 0, "reason": "reminders are switched off"}
    if not config["recipients"]:
        return {"ok": True, "sent": 0, "checked": 0, "reason": "no recipient numbers saved"}
    ensure_log()
    due = due_reminders(week_sessions(now), now, config["leadMinutes"])
    if not whatsapp.configured() and not dry_run:
        return {"ok": False, "sent": 0, "checked": len(due), "configured": False,
                "error": "WhatsApp credentials are not configured on this server."}
    sent, errors, skipped = 0, [], 0
    for session, lead in due:
        text = reminder_text(session, lead)
        for phone in config["recipients"]:
            key = _key(session, lead, phone)
            if already_sent(key):
                skipped += 1
                continue
            if dry_run:
                record(key, session, lead, phone, "dry-run")
                continue
            try:
                whatsapp.send_text(phone, text)
                record(key, session, lead, phone, "sent")
                sent += 1
            except whatsapp.WhatsAppError as error:
                record(key, session, lead, phone, "error", str(error))
                errors.append(str(error))
    return {"ok": not errors, "sent": sent, "checked": len(due), "skipped": skipped,
            "recipients": len(config["recipients"]), "leadMinutes": config["leadMinutes"],
            "errors": errors[:5]}


def send_test(to: str, now: datetime | None = None) -> dict:
    """Send one sample reminder to a single number (used by the interface's test button)."""
    number = whatsapp.normalise_phone(to)
    body = test_message(now)
    if not whatsapp.configured():
        raise whatsapp.WhatsAppError(
            "WhatsApp is not configured on this server yet. Add MNH_WHATSAPP_TOKEN and "
            "MNH_WHATSAPP_PHONE_ID, then send the test again."
        )
    result = whatsapp.send_text(number, body)
    return {**result, "preview": body}


def recent(limit: int = 20) -> list:
    ensure_log()
    with database() as connection:
        rows = connection.execute(
            "SELECT sent_at,phone,code,starts,lead,status,detail FROM reminder_log ORDER BY sent_at DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
    return [dict(row) for row in rows]


def reminder_worker(stop_event: threading.Event, interval: int = 30) -> None:
    """Background loop started by the application lifespan."""
    try:
        ensure_log()
    except Exception as error:  # never block startup on the reminder log
        print(f"WhatsApp reminder log warning: {error}", flush=True)
    while not stop_event.wait(max(10, int(interval))):
        try:
            run_once()
        except Exception as error:
            print(f"WhatsApp reminder warning: {error}", flush=True)
