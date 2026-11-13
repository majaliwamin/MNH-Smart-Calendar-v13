"""Communications contact directory with consent records.

Contacts live in the shared `comm_contacts` document collection so every device
sees the same directory. Consent is stored per channel (whatsapp / voice) and a
separate `comm_dnc` collection is the do-not-contact list: any phone number on
it must never be prepared for messaging or calling, regardless of consent flags.

Phone numbers are normalised with the same rule as the reminder service
(E.164 without '+', defaulting to Malawi, 265).
"""
import json
import time

from app.database.connection import database
from app.services import whatsapp

CATEGORIES = ("staff", "student", "other")


class ContactError(RuntimeError):
    """Contact data or consent request is not acceptable."""


def _now() -> int:
    return int(time.time() * 1000)


def ensure_tables() -> None:
    with database() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS comm_audit(
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 at TEXT NOT NULL,
                 actor TEXT,
                 action TEXT NOT NULL,
                 target TEXT,
                 detail TEXT
               )"""
        )


def audit(actor: str, action: str, target: str = "", detail: str = "") -> None:
    ensure_tables()
    from datetime import datetime
    from app.config import TIMEZONE
    from zoneinfo import ZoneInfo
    with database() as connection:
        connection.execute(
            "INSERT INTO comm_audit(at,actor,action,target,detail) VALUES(?,?,?,?,?)",
            (datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds"), actor, action, target[:120], detail[:500]),
        )


def audit_rows(limit: int = 100) -> list:
    ensure_tables()
    with database() as connection:
        rows = connection.execute(
            "SELECT at,actor,action,target,detail FROM comm_audit ORDER BY id DESC LIMIT ?", (max(1, int(limit)),)
        ).fetchall()
    return [dict(row) for row in rows]


# ---- helpers ---------------------------------------------------------------
def _clean_contact(data: dict, *, require_phone: bool) -> dict:
    name = str(data.get("name") or "").strip()
    if not name:
        raise ContactError("Every contact needs a name.")
    raw_phone = str(data.get("phone") or "").strip()
    if require_phone and not raw_phone:
        raise ContactError(f"Enter a phone number for {name}.")
    phone = ""
    if raw_phone:
        try:
            phone = whatsapp.normalise_phone(raw_phone)
        except whatsapp.WhatsAppError as error:
            raise ContactError(str(error)) from error
    category = str(data.get("category") or "other").strip().lower()
    if category not in CATEGORIES:
        category = "other"
    # Consent arrives either flat (consentWhatsapp/consentVoice) or nested ({consent:{whatsapp,voice}}).
    nested = data.get("consent") if isinstance(data.get("consent"), dict) else {}
    consent_whatsapp = bool(nested.get("whatsapp", data.get("consentWhatsapp", False)))
    consent_voice = bool(nested.get("voice", data.get("consentVoice", False)))
    return {
        "name": name[:120],
        "phone": phone,
        "category": category,
        "notes": str(data.get("notes") or "")[:500],
        "consentWhatsapp": consent_whatsapp,
        "consentVoice": consent_voice,
        "optOut": bool(data.get("optOut", False)),
    }


def _collection_rows(collection: str) -> list:
    with database() as connection:
        rows = connection.execute(
            "SELECT id, data FROM docs WHERE col=? ORDER BY id", (collection,)
        ).fetchall()
    out = []
    for row in rows:
        try:
            item = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
        item["id"] = row["id"]
        out.append(item)
    return out


def _write_doc(collection: str, item_id: str, data: dict) -> None:
    with database() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (collection, item_id, json.dumps(data), _now()),
        )


def _delete_doc(collection: str, item_id: str) -> None:
    with database() as connection:
        connection.execute("DELETE FROM docs WHERE col=? AND id=?", (collection, item_id))


# ---- contacts ---------------------------------------------------------------
def list_contacts() -> list:
    return sorted(_collection_rows("comm_contacts"), key=lambda c: c.get("name", "").lower())


def get_contact(contact_id: str) -> dict | None:
    with database() as connection:
        row = connection.execute(
            "SELECT data FROM docs WHERE col='comm_contacts' AND id=?", (contact_id,)
        ).fetchone()
    if not row:
        return None
    try:
        item = json.loads(row["data"])
    except (TypeError, json.JSONDecodeError):
        return None
    item["id"] = contact_id
    return item


def upsert_contact(actor: str, data: dict, contact_id: str | None = None) -> dict:
    cleaned = _clean_contact(data, require_phone=contact_id is None)
    item_id = contact_id or f"ct-{_now()}"
    existing = get_contact(item_id) if contact_id else None
    if existing:
        cleaned["createdAt"] = existing.get("createdAt", _now())
    else:
        cleaned["createdAt"] = _now()
    cleaned["updatedAt"] = _now()
    _write_doc("comm_contacts", item_id, cleaned)
    cleaned["id"] = item_id
    audit(actor, "contact-updated" if existing else "contact-added", item_id, cleaned["name"])
    return cleaned


def delete_contact(actor: str, contact_id: str) -> None:
    _delete_doc("comm_contacts", contact_id)
    audit(actor, "contact-deleted", contact_id)


def set_consent(actor: str, contact_id: str, channel: str, granted: bool) -> dict:
    if channel not in ("whatsapp", "voice"):
        raise ContactError("Consent channel must be 'whatsapp' or 'voice'.")
    contact = get_contact(contact_id)
    if not contact:
        raise ContactError("Contact not found.")
    contact[f"consent{'Whatsapp' if channel == 'whatsapp' else 'Voice'}"] = bool(granted)
    contact["updatedAt"] = _now()
    _write_doc("comm_contacts", contact_id, contact)
    audit(actor, f"consent-{channel}-{'granted' if granted else 'revoked'}", contact_id, contact["name"])
    return contact


# ---- do-not-contact ----------------------------------------------------------
def dnc_list() -> list:
    return sorted(_collection_rows("comm_dnc"), key=lambda d: d.get("phone", ""))


def dnc_phones() -> set:
    return {str(item.get("phone") or "") for item in dnc_list()}


def dnc_add(actor: str, phone_raw: str, reason: str = "") -> dict:
    try:
        phone = whatsapp.normalise_phone(phone_raw)
    except whatsapp.WhatsAppError as error:
        raise ContactError(str(error)) from error
    entry = {"phone": phone, "reason": str(reason or "")[:300], "addedAt": _now()}
    existing = [d for d in dnc_list() if d.get("phone") == phone]
    item_id = existing[0]["id"] if existing else f"dnc-{_now()}"
    _write_doc("comm_dnc", item_id, entry)
    entry["id"] = item_id
    audit(actor, "dnc-added", phone, reason)
    return entry


def dnc_remove(actor: str, item_id: str) -> None:
    _delete_doc("comm_dnc", item_id)
    audit(actor, "dnc-removed", item_id)


def contact_allowed(contact: dict, channel: str) -> tuple[bool, str]:
    """(allowed, reason) — consent, opt-out and DNC in one check."""
    phone = str(contact.get("phone") or "")
    if contact.get("optOut"):
        return False, "contact opted out"
    if phone and phone in dnc_phones():
        return False, "phone is on the do-not-contact list"
    key = "consentWhatsapp" if channel == "whatsapp" else "consentVoice"
    if not contact.get(key):
        return False, f"no {channel} consent recorded"
    if not phone:
        return False, "contact has no phone number"
    return True, ""
