"""Communications core: message drafts, wa.me links, templates, jobs, safeguards.

STATUS MODEL (never claim delivery from anything else):
  draft        — message prepared, nothing opened yet
  opened       — the user clicked a generated wa.me link; WhatsApp conversation opened
  sent-manual  — the human pressed Send inside WhatsApp and confirmed it in this app
  cancelled    — draft discarded

Opening a link NEVER marks a message as delivered. The existing Cloud API
reminder worker (`reminders.py`) is a separate, unchanged channel.

Scheduled jobs only ever CREATE drafts and flag them for a responsible human.
Nothing in this module sends automatically.
"""
import json
import time
import urllib.parse
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from app.config import TIMEZONE
from app.database.connection import database
from app.services import comm_contacts, whatsapp

TZ = ZoneInfo(TIMEZONE)
CALL_WINDOW_START = dtime(8, 0)   # MNH_CALL_WINDOW_START / _END override
CALL_WINDOW_END = dtime(18, 0)
MAX_RECIPIENTS_PER_DRAFT = 50
JOB_COOLDOWN_MINUTES = 60  # duplicate prevention window for scheduled jobs


class CommError(RuntimeError):
    """Request is not acceptable, or a safeguard blocks it."""


def _env(name: str, default: str = "") -> str:
    import os
    return (os.getenv(name) or default).strip()


def _now() -> int:
    return int(time.time() * 1000)


def _write_doc(collection: str, item_id: str, data: dict) -> None:
    with database() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (collection, item_id, json.dumps(data), _now()),
        )


def _collection_rows(collection: str) -> list:
    with database() as connection:
        rows = connection.execute("SELECT id, data FROM docs WHERE col=?", (collection,)).fetchall()
    out = []
    for row in rows:
        try:
            item = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
        item["id"] = row["id"]
        out.append(item)
    return out


# ---- emergency stop ----------------------------------------------------------
def emergency_stop() -> bool:
    settings = _collection_rows("settings")
    for row in settings:
        if row.get("id") == "comm":
            return bool(row.get("emergencyStop", False))
    return False


def set_emergency_stop(actor: str, value: bool) -> dict:
    existing = next((r for r in _collection_rows("settings") if r.get("id") == "comm"), None) or {}
    data = {"id": "comm", "emergencyStop": bool(value), "updatedAt": _now(),
            "callWindowStart": existing.get("callWindowStart", "08:00"),
            "callWindowEnd": existing.get("callWindowEnd", "18:00")}
    _write_doc("settings", "comm", data)
    comm_contacts.audit(actor, "emergency-stop-on" if value else "emergency-stop-off")
    return data


def _guard_preparation(actor: str) -> None:
    if emergency_stop():
        comm_contacts.audit(actor, "blocked-emergency-stop")
        raise CommError("All communications are paused by the emergency stop. Switch it off in Settings to continue.")


# ---- wa.me links ---------------------------------------------------------------
def wa_link(number: str, body: str) -> str:
    """Official Click-to-Chat link: digits only (no '+'), URL-encoded message."""
    digits = whatsapp.normalise_phone(number)
    return f"https://wa.me/{digits}?text={urllib.parse.quote(str(body or ''), safe='')}"


# ---- templates ---------------------------------------------------------------
def list_templates() -> list:
    return sorted(_collection_rows("comm_templates"), key=lambda t: t.get("title", "").lower())


def upsert_template(actor: str, data: dict, template_id: str | None = None) -> dict:
    title = str(data.get("title") or "").strip()
    body = str(data.get("body") or "").strip()
    if not title or not body:
        raise CommError("A template needs a title and body text.")
    item_id = template_id or f"tpl-{_now()}"
    entry = {"title": title[:120], "body": body[:2000], "updatedAt": _now()}
    _write_doc("comm_templates", item_id, entry)
    entry["id"] = item_id
    comm_contacts.audit(actor, "template-saved", item_id, title)
    return entry


def delete_template(actor: str, template_id: str) -> None:
    with database() as connection:
        connection.execute("DELETE FROM docs WHERE col='comm_templates' AND id=?", (template_id,))
    comm_contacts.audit(actor, "template-deleted", template_id)


# ---- drafts ---------------------------------------------------------------
def _recipient_rows(contact_ids: list) -> list:
    if not contact_ids:
        raise CommError("Select at least one recipient.")
    if len(contact_ids) > MAX_RECIPIENTS_PER_DRAFT:
        raise CommError(f"Select at most {MAX_RECIPIENTS_PER_DRAFT} recipients per draft.")
    rows = []
    for contact_id in contact_ids:
        contact = comm_contacts.get_contact(contact_id)
        if not contact:
            raise CommError(f"Contact {contact_id} no longer exists.")
        allowed, reason = comm_contacts.contact_allowed(contact, "whatsapp")
        rows.append({
            "contactId": contact_id,
            "name": contact.get("name", ""),
            "phone": contact.get("phone", ""),
            "status": "ready" if allowed else "blocked",
            "blockReason": "" if allowed else reason,
        })
    if all(r["status"] == "blocked" for r in rows):
        raise CommError("None of the selected recipients has WhatsApp consent (check the do-not-contact list and consent flags).")
    return rows


def create_draft(actor: str, contact_ids: list, body: str, *, title: str = "", aiAssisted: bool = False) -> dict:
    """Prepare one draft per recipient. Human review is implied: nothing is opened or sent here."""
    _guard_preparation(actor)
    text = str(body or "").strip()
    if not text:
        raise CommError("Write the message before preparing recipients.")
    recipients = _recipient_rows(contact_ids)
    draft_id = f"dft-{_now()}"
    entry = {
        "title": str(title or "")[:120],
        "body": text[:4000],
        "aiAssisted": bool(aiAssisted),
        "createdBy": actor,
        "createdAt": _now(),
        "recipients": recipients,
    }
    _write_doc("comm_drafts", draft_id, entry)
    entry["id"] = draft_id
    entry["links"] = [
        {"contactId": r["contactId"], "link": wa_link(r["phone"], text)}
        for r in recipients if r["status"] == "ready"
    ]
    comm_contacts.audit(actor, "draft-created", draft_id, f"{len(recipients)} recipients" + (" (AI-assisted)" if aiAssisted else ""))
    return entry


def draft_rows(limit: int = 50) -> list:
    rows = sorted(_collection_rows("comm_drafts"), key=lambda d: d.get("createdAt", 0), reverse=True)[:max(1, int(limit))]
    for row in rows:
        row["links"] = [
            {"contactId": r["contactId"], "link": wa_link(r["phone"], row.get("body", ""))}
            for r in row.get("recipients", []) if r["status"] == "ready"
        ]
    return rows


def mark_draft(actor: str, draft_id: str, contact_id: str, status: str) -> dict:
    """Record that a conversation was opened, or that the human confirmed sending."""
    if status not in ("opened", "sent-manual", "cancelled"):
        raise CommError("Status must be 'opened', 'sent-manual' or 'cancelled'.")
    with database() as connection:
        row = connection.execute("SELECT data FROM docs WHERE col='comm_drafts' AND id=?", (draft_id,)).fetchone()
    if not row:
        raise CommError("Draft not found.")
    try:
        entry = json.loads(row["data"])
    except (TypeError, json.JSONDecodeError) as error:
        raise CommError("Draft record is damaged.") from error
    hit = False
    for recipient in entry.get("recipients", []):
        if recipient.get("contactId") == contact_id:
            if recipient.get("status") == "blocked":
                raise CommError("That recipient is blocked by consent or the do-not-contact list.")
            recipient["status"] = status
            recipient["statusAt"] = _now()
            hit = True
    if not hit:
        raise CommError("That contact is not a recipient of this draft.")
    _write_doc("comm_drafts", draft_id, entry)
    comm_contacts.audit(actor, f"draft-{status}", draft_id, contact_id)
    return {"ok": True, "draftId": draft_id, "contactId": contact_id, "status": status}


# ---- scheduled jobs ---------------------------------------------------------------
def schedule_job(actor: str, data: dict) -> dict:
    """Queue a reminder job. Jobs CREATE DRAFTS ONLY — they never send messages."""
    _guard_preparation(actor)
    kind = str(data.get("kind") or "").strip()
    if kind not in ("lecture-reminder", "exam-reminder", "deadline", "meeting", "announcement", "custom"):
        raise CommError("Choose a job type (lecture-reminder, exam-reminder, deadline, meeting, announcement or custom).")
    when_raw = str(data.get("runAt") or "").strip()
    try:
        run_at = datetime.fromisoformat(when_raw).replace(tzinfo=TZ)
    except ValueError as error:
        raise CommError("Provide the run time as an ISO datetime, e.g. 2026-11-16T07:30.") from error
    if run_at < datetime.now(TZ):
        raise CommError("Choose a future time for the scheduled job.")
    contact_ids = list(data.get("contactIds") or [])
    if not contact_ids:
        raise CommError("Select at least one recipient for the job.")
    # duplicate prevention: same kind + same minute + same recipients within the cooldown
    fingerprint = f"{kind}|{run_at.strftime('%Y-%m-%d %H:%M')}|{','.join(sorted(map(str, contact_ids)))}"
    for existing in _collection_rows("comm_jobs"):
        if existing.get("fingerprint") == fingerprint and existing.get("status") == "pending":
            raise CommError("An identical job is already scheduled and pending.")
    job_id = f"job-{_now()}"
    entry = {
        "kind": kind,
        "runAt": run_at.isoformat(timespec="seconds"),
        "runEpoch": run_at.timestamp(),
        "title": str(data.get("title") or "")[:120],
        "instructions": str(data.get("instructions") or "")[:2000],
        "body": str(data.get("body") or "")[:4000],
        "contactIds": [str(c) for c in contact_ids],
        "createdBy": actor,
        "createdAt": _now(),
        "status": "pending",       # pending | done | failed | cancelled
        "attempts": 0,
        "lastError": "",
        "draftId": "",
        "fingerprint": fingerprint,
    }
    _write_doc("comm_jobs", job_id, entry)
    entry["id"] = job_id
    comm_contacts.audit(actor, "job-scheduled", job_id, f"{kind} at {entry['runAt']}")
    return entry


def job_rows() -> list:
    return sorted(_collection_rows("comm_jobs"), key=lambda j: j.get("runEpoch", 0))


def run_due_jobs(now: datetime | None = None) -> dict:
    """Create drafts for due jobs. Safe to call repeatedly; failures are recorded, never silent."""
    now = now or datetime.now(TZ)
    results = {"due": 0, "done": 0, "failed": 0, "skipped": 0, "errors": []}
    if emergency_stop():
        return {**results, "skipped": len([j for j in job_rows() if j.get("status") == "pending"]), "reason": "emergency stop"}
    for job in job_rows():
        if job.get("status") != "pending":
            continue
        run_epoch = float(job.get("runEpoch") or 0)
        if run_epoch > now.timestamp():
            continue
        if now.timestamp() - run_epoch > 7 * 24 * 3600:  # abandoned for a week — mark failed
            job["status"], job["lastError"] = "failed", "job was never run (server offline too long)"
            _write_doc("comm_jobs", job["id"], job)
            results["failed"] += 1
            continue
        results["due"] += 1
        job["attempts"] = int(job.get("attempts") or 0) + 1
        try:
            contact_ids = [c for c in job.get("contactIds", []) if comm_contacts.get_contact(c)]
            if not contact_ids:
                raise CommError("None of the job's recipients exist any more.")
            body = str(job.get("body") or "").strip()
            if not body:
                body = f"Reminder: {job.get('title') or job.get('kind')} — prepared by the timetable. Please review before sending."
            draft = create_draft(job.get("createdBy") or "scheduler", contact_ids, body,
                                 title=job.get("title") or job.get("kind"), aiAssisted=bool(job.get("aiAssisted")))
            job["status"], job["draftId"], job["lastError"] = "done", draft["id"], ""
            results["done"] += 1
            comm_contacts.audit("scheduler", "job-done", job["id"], f"draft {draft['id']} awaiting human send")
        except Exception as error:  # record, retry later — never silently disappear
            job["lastError"] = str(error)[:400]
            if job["attempts"] >= 3:
                job["status"] = "failed"
            results["failed"] += 1 if job["status"] == "failed" else 0
            results["errors"].append(f"{job['id']}: {error}")
        _write_doc("comm_jobs", job["id"], job)
    return results


def cancel_job(actor: str, job_id: str) -> dict:
    with database() as connection:
        row = connection.execute("SELECT data FROM docs WHERE col='comm_jobs' AND id=?", (job_id,)).fetchone()
    if not row:
        raise CommError("Job not found.")
    try:
        job = json.loads(row["data"])
    except (TypeError, json.JSONDecodeError) as error:
        raise CommError("Job record is damaged.") from error
    if job.get("status") != "pending":
        raise CommError(f"Only pending jobs can be cancelled (this one is {job.get('status')}).")
    job["status"] = "cancelled"
    _write_doc("comm_jobs", job_id, job)
    comm_contacts.audit(actor, "job-cancelled", job_id)
    return {"ok": True}


# ---- calling-hours safeguard (shared with the ARI service) ------------------------
def call_window() -> tuple[dtime, dtime]:
    try:
        start = dtime.fromisoformat(_env("MNH_CALL_WINDOW_START", "08:00"))
        end = dtime.fromisoformat(_env("MNH_CALL_WINDOW_END", "18:00"))
    except ValueError:
        start, end = CALL_WINDOW_START, CALL_WINDOW_END
    return start, end


def within_call_window(now: datetime | None = None) -> tuple[bool, str]:
    now = now or datetime.now(TZ)
    start, end = call_window()
    if not (start <= now.time() <= end):
        return False, f"calls are only allowed between {start.strftime('%H:%M')} and {end.strftime('%H:%M')} ({TIMEZONE})"
    return True, ""


def history(limit: int = 100) -> list:
    return comm_contacts.audit_rows(limit)


def status() -> dict:
    contacts = comm_contacts.list_contacts()
    return {
        "emergencyStop": emergency_stop(),
        "contacts": len(contacts),
        "withConsent": len([c for c in contacts if c.get("consentWhatsapp")]),
        "dnc": len(comm_contacts.dnc_list()),
        "callWindow": {"start": call_window()[0].strftime("%H:%M"), "end": call_window()[1].strftime("%H:%M")},
        "whatsapp": whatsapp.status(),
        "ai": None,  # filled in by the API layer to keep this module free of the AI import
    }
