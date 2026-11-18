"""CRARA -> WhatsApp sending: one guarded, explicit send path.

CRARA is advisory and drafts messages; it does not dispatch them (see
``docs/communications-deployment.md``). This module adds the single narrow
exception the class rep asked for: send one plain-text WhatsApp message to a
number on an explicit allowlist, only after the user confirms, and only while
every Communications Centre safeguard allows it.

Transport is the WAHA bridge in ``app/services/wa_bridge.py``. Meta's WhatsApp
Cloud API is retired from this app: ``app/services/whatsapp.py`` is kept for
phone normalisation only and is not used to send.

Safeguards, all enforced server-side, checked in this order:

  1. ``MNH_CLASSREP_WHATSAPP_ENABLED=0`` switches the feature off outright.
  2. ``confirm`` must be true, so the browser has to ask the user first.
  3. The target must be a single number on ``MNH_CLASSREP_WHATSAPP_ALLOWED``
     (comma-separated; defaults to +265881988156). Groups are refused.
  4. The emergency stop must be off.
  5. The number must not be on the do-not-contact list.
  6. If the number belongs to a saved contact, that contact must hold WhatsApp
     consent and must not have opted out.

Every refusal and every failure is written to the ``comm_audit`` table, so an
attempt never disappears silently.

Wiring (two lines in ``backend/app/main.py``):

    from app.class_rep.whatsapp import router as class_rep_whatsapp_router
    app.include_router(class_rep_whatsapp_router)

Until those two lines are added, this module is inert: nothing imports it, so
importing it here cannot affect the running application.
"""
import os

from fastapi import APIRouter, Body, Cookie, HTTPException

from app.services import comm_contacts, comm_service, wa_bridge

router = APIRouter(prefix="/api/class-rep")

DEFAULT_ALLOWED_NUMBER = "+265881988156"
MAX_BODY_LENGTH = 4000


class SendError(RuntimeError):
    """A send was refused, or the bridge could not deliver it."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def enabled() -> bool:
    """False when the admin has switched CRARA WhatsApp sending off."""
    return _env("MNH_CLASSREP_WHATSAPP_ENABLED", "1").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _digits(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def allowed_numbers() -> list:
    """E.164 digits (no '+') that CRARA may send to."""
    raw = _env("MNH_CLASSREP_WHATSAPP_ALLOWED", DEFAULT_ALLOWED_NUMBER)
    out = []
    for part in raw.split(","):
        digits = _digits(part)
        if digits and digits not in out:
            out.append(digits)
    return out


def _contact_for(digits: str):
    """The saved contact whose number matches, if there is one."""
    for contact in comm_contacts.list_contacts():
        if _digits(contact.get("phone")) == digits:
            return contact
    return None


def status() -> dict:
    """What the class rep UI may know. Numbers are counted, never listed."""
    return {
        "enabled": enabled(),
        "bridgeConfigured": wa_bridge.configured(),
        "allowedRecipients": len(allowed_numbers()),
        "emergencyStop": comm_service.emergency_stop(),
        "sender": wa_bridge.profile_name(),
        "missing": [] if wa_bridge.configured() else ["MNH_WA_BRIDGE_URL"],
    }


def send(to: str, body: str, *, confirm: bool, actor: str = "public") -> dict:
    """Send one WhatsApp text to an allowlisted number.

    Raises ``SendError`` with an HTTP status the route can pass straight on.
    """
    if not enabled():
        raise SendError(
            "CRARA WhatsApp sending is switched off (MNH_CLASSREP_WHATSAPP_ENABLED=0).",
            403,
        )
    if not confirm:
        raise SendError(
            "Confirm the recipient and the message before sending.",
            400,
        )
    text = str(body or "").strip()
    if not text:
        raise SendError("There is nothing to send.", 400)

    try:
        chat_id = wa_bridge.normalise_target(to)
    except wa_bridge.BridgeError as error:
        raise SendError(str(error), 400) from error

    if wa_bridge.is_group(chat_id):
        raise SendError(
            "CRARA sends to one WhatsApp number, not to a group.",
            400,
        )

    digits = _digits(chat_id)
    if digits not in allowed_numbers():
        comm_contacts.audit(
            actor, "crara-whatsapp-blocked", digits, "number is not on the allowlist"
        )
        raise SendError(
            "That number is not on the CRARA WhatsApp allowlist. Add it to "
            "MNH_CLASSREP_WHATSAPP_ALLOWED to permit it.",
            403,
        )

    if comm_service.emergency_stop():
        comm_contacts.audit(
            actor, "crara-whatsapp-blocked", digits, "emergency stop is on"
        )
        raise SendError(
            "All communications are paused by the emergency stop. Switch it off "
            "in Settings to continue.",
            403,
        )

    if digits in comm_contacts.dnc_phones():
        comm_contacts.audit(
            actor, "crara-whatsapp-blocked", digits, "number is on the do-not-contact list"
        )
        raise SendError(
            "That number is on the do-not-contact list and can never be messaged.",
            403,
        )

    contact = _contact_for(digits)
    if contact is not None:
        allowed, reason = comm_contacts.contact_allowed(contact, "whatsapp")
        if not allowed:
            comm_contacts.audit(actor, "crara-whatsapp-blocked", digits, reason)
            raise SendError(f"That contact cannot be messaged: {reason}.", 403)

    if not wa_bridge.configured():
        raise SendError(
            "The WhatsApp bridge is not configured on this server. Set "
            "MNH_WA_BRIDGE_URL (and MNH_WA_BRIDGE_TOKEN if the bridge uses auth).",
            503,
        )

    try:
        result = wa_bridge.send_text(chat_id, text[:MAX_BODY_LENGTH])
    except wa_bridge.BridgeError as error:
        comm_contacts.audit(actor, "crara-whatsapp-failed", digits, str(error)[:200])
        raise SendError(str(error), 502) from error

    comm_contacts.audit(actor, "crara-whatsapp-sent", digits, text[:200])
    return {
        "ok": True,
        "status": "sent",
        "to": digits,
        "chatId": chat_id,
        "sender": wa_bridge.profile_name(),
        "bridgeResponse": result.get("bridgeResponse"),
    }


@router.get("/whatsapp/status")
def whatsapp_status(mnh_session: str | None = Cookie(None)):
    """Whether CRARA can send right now, and why not."""
    return status()


@router.post("/whatsapp/send")
def whatsapp_send(
    mnh_session: str | None = Cookie(None),
    data: dict = Body(default={}),
):
    """Send one WhatsApp text. Requires ``confirm: true`` from the UI."""
    try:
        return send(
            str(data.get("to") or ""),
            str(data.get("body") or ""),
            confirm=bool(data.get("confirm")),
        )
    except SendError as error:
        raise HTTPException(
            status_code=error.status_code, detail=str(error)
        ) from error
