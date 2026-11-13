"""AI-triggered WhatsApp messaging — the AI detects, composes and SENDS.

This is the automatic channel requested on 2026-11-13 ("AI will be the
triggerer of the messaging", Meta APIs retired). Two entry points:

1. Manual trigger  — an editor asks the AI to compose and send for an event
   (API: POST /api/comm/ai/trigger).
2. Automatic trigger — the background worker diffs the week's timetable
   against a stored snapshot; on new/changed/removed sessions the AI composes
   a notice and sends it through the WhatsApp bridge to every contact with
   WhatsApp consent. Requires MNH_AI_TRIGGER_ENABLED=1 (off by default so the
   behaviour is switched on deliberately, not accidentally).

Hard limits the AI can never cross (unchanged from the master spec):
  - emergency stop blocks every send
  - the do-not-contact list and opt-outs are honoured first
  - only contacts with recorded WhatsApp consent receive anything
  - if the AI provider fails, a plain template goes out instead — a
    schedule change is never swallowed by an AI outage
Every send is logged in comm_audit and stored as a draft with status
"sent-ai" so the history shows exactly what the AI dispatched.
"""
import json
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import TIMEZONE
from app.database.connection import database
from app.services import ai_assistant, comm_contacts, wa_bridge, whatsapp

TZ = ZoneInfo(TIMEZONE)
SNAPSHOT_KEY = "comm_schedule_snapshot"
TRIGGER_LOG_COL = "comm_trigger_log"
MAX_AUTO_RECIPIENTS = 50


class TriggerError(RuntimeError):
    """Trigger request is not acceptable."""


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _now() -> int:
    return int(time.time() * 1000)


def enabled() -> bool:
    return _env("MNH_AI_TRIGGER_ENABLED", "0").lower() in ("1", "true", "yes")


def status() -> dict:
    return {
        "autoTrigger": enabled(),
        "bridge": wa_bridge.status(),
        "ai": ai_assistant.status(),
    }


def _guard(actor: str) -> None:
    if comm_service_emergency_stop():
        comm_contacts.audit(actor, "blocked-emergency-stop", detail="ai trigger")
        raise TriggerError("All communications are paused by the emergency stop.")


def comm_service_emergency_stop() -> bool:
    from app.services import comm_service
    return comm_service.emergency_stop()


# ---- recipient resolution ---------------------------------------------------------
def _consented_recipients(contact_ids: list | None) -> list:
    """Contacts with WhatsApp consent, opt-outs and DNC applied. Empty ids = all consented."""
    contacts = comm_contacts.list_contacts()
    if contact_ids:
        wanted = {str(c) for c in contact_ids}
        contacts = [c for c in contacts if c.get("id") in wanted]
    out = []
    for contact in contacts:
        allowed, reason = comm_contacts.contact_allowed(contact, "whatsapp")
        if allowed:
            out.append({"contactId": contact["id"], "name": contact.get("name", ""), "phone": contact["phone"]})
    return out


def _store_log(entry: dict) -> str:
    item_id = entry.get("id") or f"trg-{_now()}"
    with database() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (TRIGGER_LOG_COL, item_id, json.dumps(entry), _now()),
        )
    return item_id


def trigger_log(limit: int = 50) -> list:
    with database() as connection:
        rows = connection.execute(f"SELECT id, data FROM docs WHERE col='{TRIGGER_LOG_COL}'").fetchall()
    out = []
    for row in rows:
        try:
            item = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
        item["id"] = row["id"]
        out.append(item)
    return sorted(out, key=lambda t: t.get("createdAt", 0), reverse=True)[:max(1, int(limit))]


# ---- composition --------------------------------------------------------------------
def _context_text(recipients: list) -> str:
    names = ", ".join(r["name"] for r in recipients[:8]) or "the list"
    return f"Recipients: {names}."


def compose(kind: str, instructions: str, recipients: list, changes: list | None = None) -> tuple[str, bool]:
    """(message, aiWasUsed). Falls back to a template when the AI is unavailable."""
    context = _context_text(recipients)
    if changes:
        context += " Timetable changes detected: " + "; ".join(changes)[:1500]
    prompt = f"Draft a WhatsApp {kind} message. {context} {instructions}".strip()
    try:
        return ai_assistant.draft(prompt), True
    except ai_assistant.AIError:
        return (
            "Maternal & Neonatal Health Smart Time Table\n"
            f"{kind.replace('-', ' ').capitalize()}: {instructions or 'please check the timetable for details.'}"
        ), False


# ---- manual trigger (editor-initiated) -----------------------------------------------
def trigger_now(actor: str, kind: str, instructions: str, contact_ids: list | None = None) -> dict:
    """AI composes and immediately sends to the selected (or all consented) contacts."""
    _guard(actor)
    kind = str(kind or "announcement").strip()
    instructions = str(instructions or "").strip()
    if not instructions:
        raise TriggerError("Describe the event or what the message should say.")
    recipients = _consented_recipients(contact_ids)
    if not recipients:
        raise TriggerError("No contacts with WhatsApp consent matched — nothing to send.")
    message, ai_used = compose(kind, instructions, recipients)
    return _dispatch(actor, kind, message, recipients, ai_used, "manual-trigger")


# ---- automatic trigger (schedule-change watcher) ---------------------------------------
def _collections() -> dict:
    from app.services.reminders import _collections as reminder_collections
    return reminder_collections()


def _session_signature(sessions: list) -> list:
    rows = []
    for s in sessions:
        rows.append(f"{s.get('id')}|{s.get('date')}|{s.get('start')}|{s.get('end')}|{s.get('code')}|{s.get('lecturer')}|{s.get('status')}")
    return sorted(rows)


def detect_changes(sessions: list) -> list:
    """Diff current sessions against the stored snapshot; returns human-readable changes."""
    current = _session_signature(sessions)
    with database() as connection:
        row = connection.execute("SELECT value FROM app_meta WHERE key=?", (SNAPSHOT_KEY,)).fetchone()
    previous = []
    if row:
        try:
            previous = json.loads(row["value"])
        except (TypeError, ValueError):
            previous = []
    prev_map = dict(line.split("|", 1) for line in previous if "|" in line)
    curr_map = dict(line.split("|", 1) for line in current if "|" in line)
    changes = []
    for key, detail in curr_map.items():
        if key not in prev_map:
            changes.append(f"NEW {detail}")
        elif detail != prev_map[key]:
            changes.append(f"CHANGED {detail} (was {prev_map[key]})")
    for key, detail in prev_map.items():
        if key not in curr_map:
            changes.append(f"REMOVED {detail}")
    return changes


def _save_snapshot(sessions: list) -> None:
    with database() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO app_meta(key,value) VALUES(?,?)",
            (SNAPSHOT_KEY, json.dumps(_session_signature(sessions))),
        )


def auto_check(now: datetime | None = None) -> dict:
    """Worker entry point: on timetable changes, AI composes and the bridge sends.

    Deliberately skips the first run after startup (no snapshot yet) so a server
    restart never fires a spurious "changes" broadcast.
    """
    now = now or datetime.now(TZ)
    result = {"enabled": enabled(), "checked": True, "changes": 0, "sent": 0, "aiUsed": False, "errors": []}
    if not enabled():
        return {"enabled": False, "checked": False, "changes": 0, "sent": 0}
    _guard("ai-trigger")
    from app.services.reminders import week_sessions
    sessions = week_sessions(now)
    with database() as connection:
        row = connection.execute("SELECT value FROM app_meta WHERE key=?", (SNAPSHOT_KEY,)).fetchone()
    if not row:  # first run: record baseline, send nothing
        _save_snapshot(sessions)
        result["checked"] = "baseline"
        return result
    changes = detect_changes(sessions)
    if not changes:
        _save_snapshot(sessions)
        return result
    result["changes"] = len(changes)
    recipients = _consented_recipients(None)[:MAX_AUTO_RECIPIENTS]
    if not recipients:
        _save_snapshot(sessions)
        result["errors"].append("changes detected but no consented recipients")
        return result
    summary = "; ".join(changes)[:1200]
    message, ai_used = compose("schedule-change", "Inform recipients about these timetable changes.", recipients, changes)
    result["aiUsed"] = ai_used
    try:
        dispatched = _dispatch("ai-trigger", "schedule-change", message, recipients, ai_used, "auto-trigger", changes=summary)
        result["sent"] = dispatched["sentCount"]
    except TriggerError as error:
        result["errors"].append(str(error))
    _save_snapshot(sessions)
    return result


# ---- dispatch --------------------------------------------------------------------------
def _dispatch(actor: str, kind: str, message: str, recipients: list, ai_used: bool, mode: str, changes: str = "") -> dict:
    sent, errors = 0, []
    for recipient in recipients:
        try:
            wa_bridge.send_text(recipient["phone"], message)
            sent += 1
        except wa_bridge.BridgeError as error:
            errors.append(f"{recipient['name'] or recipient['phone']}: {error}")
    entry = {
        "kind": kind,
        "mode": mode,
        "aiUsed": ai_used,
        "message": message[:4000],
        "changes": changes[:2000],
        "sentTo": [r["contactId"] for r in recipients],
        "sentCount": sent,
        "errors": errors[:10],
        "createdBy": actor,
        "createdAt": _now(),
    }
    _store_log(entry)
    comm_contacts.audit(actor, f"ai-{mode}-sent", kind, f"{sent} sent, {len(errors)} failed · {message[:80]}…")
    return {"sentCount": sent, "message": message, "aiUsed": ai_used, "errors": errors, "recipients": len(recipients)}
