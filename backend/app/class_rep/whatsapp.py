"""CRARA -> WhatsApp sending: WAHA bridge, with a click-to-chat fallback.

CRARA is advisory and drafts messages (see ``docs/communications-deployment.md``).
This module adds the single narrow exception: send one plain-text WhatsApp
message to a number on an explicit allowlist, after the user confirms, and only
while every Communications Centre safeguard allows it.

Delivery modes:

  **bridge**  A paired WhatsApp session on the Asterisk/VPS host, reached through
              ``app/services/wa_bridge.py`` (WAHA, ``POST /api/sendText``).
              This is the intended production path: it runs on hardware you
              already own, it is unmetered, and it needs no third-party account
              or card. Asterisk itself cannot carry WhatsApp (it is a SIP/RTP
              PBX), so the WhatsApp session runs as a separate container on the
              same VPS and Asterisk is untouched. Needs ``MNH_WA_BRIDGE_URL``.

  **link**    Nothing configured: return an official click-to-chat link
              (``https://wa.me/<number>?text=...``). Free, no account.

Twilio support remains in this file but is **never selected automatically**.
It is reachable only by setting ``MNH_CLASSREP_WHATSAPP_TRANSPORT=twilio``
explicitly, because Twilio trials are not available in every country. With the
variable unset, the choice is bridge, then link.

    auto     (default) bridge if configured, else link
    bridge   always the WAHA bridge
    twilio   only when set by hand
    link     always the click-to-chat link

Meta's WhatsApp Cloud API is not implemented here: registering a production
sender requires a payment method this deployment does not have.
``app/services/whatsapp.py`` is imported only for its offline phone normaliser.

Safeguards, all enforced server-side, checked before any mode:

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
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, Body, Cookie, HTTPException

from app.services import comm_contacts, comm_service, wa_bridge

router = APIRouter(prefix="/api/class-rep")

DEFAULT_ALLOWED_NUMBER = "+265881988156"
DEFAULT_TWILIO_FROM = "+14155238886"
MAX_BODY_LENGTH = 4000
TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
TRANSPORT_CHOICES = ("auto", "bridge", "twilio", "link")


class SendError(RuntimeError):
    """A send was refused, or the provider could not deliver it."""

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


def twilio_configured() -> bool:
    return bool(_env("MNH_TWILIO_ACCOUNT_SID") and _env("MNH_TWILIO_AUTH_TOKEN"))


def transport() -> str:
    """The operator's explicit choice, or 'auto'."""
    chosen = _env("MNH_CLASSREP_WHATSAPP_TRANSPORT", "auto").lower()
    return chosen if chosen in TRANSPORT_CHOICES else "auto"


def mode() -> str:
    """Which transport a send would use right now.

    Automatic selection is bridge, then link. Twilio is never chosen for you:
    its trials are not available in every country, so it must be asked for.
    """
    chosen = transport()
    if chosen in ("bridge", "twilio", "link"):
        return chosen
    if wa_bridge.configured():
        return "bridge"
    return "link"


def ready() -> bool:
    """True when the selected mode can actually deliver a message."""
    current = mode()
    if current == "twilio":
        return twilio_configured()
    if current == "bridge":
        return wa_bridge.configured()
    return False


def build_link(digits: str, text: str) -> str:
    """Official click-to-chat link. Digits only, no '+', URL-encoded text."""
    return "https://wa.me/{}?text={}".format(
        _digits(digits),
        urllib.parse.quote(str(text or ""), safe=""),
    )


def _post_form(url: str, fields: dict, user: str, password: str, timeout: int = 20) -> dict:
    """POST an application/x-www-form-urlencoded body with HTTP Basic auth."""
    data = urllib.parse.urlencode(fields).encode("utf-8")
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8") or "{}"
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            failure = json.loads(error.read().decode("utf-8") or "{}")
            detail = str(failure.get("message") or "")
            code = failure.get("code")
            if code:
                detail = f"{detail} (Twilio error {code})"
        except (ValueError, AttributeError):
            detail = ""
        raise SendError(
            f"Twilio rejected the message ({error.code}). {detail}".strip(), 502
        ) from error
    except urllib.error.URLError as error:
        raise SendError(f"Twilio could not be reached: {error.reason}", 502) from error
    try:
        return json.loads(raw)
    except ValueError:
        return {"raw": raw[:200]}


def _twilio_send(digits: str, text: str) -> dict:
    """Send through Twilio's WhatsApp channel. Only used when asked for by hand."""
    sid = _env("MNH_TWILIO_ACCOUNT_SID")
    token = _env("MNH_TWILIO_AUTH_TOKEN")
    sender = _env("MNH_TWILIO_WHATSAPP_FROM", DEFAULT_TWILIO_FROM)
    if not sender.startswith("whatsapp:"):
        sender = f"whatsapp:{sender}"
    result = _post_form(
        TWILIO_API.format(sid=sid),
        {"To": f"whatsapp:+{digits}", "From": sender, "Body": text},
        sid,
        token,
    )
    return {
        "provider": "twilio",
        "messageId": str(result.get("sid") or ""),
        "providerStatus": str(result.get("status") or "queued"),
    }


def status() -> dict:
    """What the class rep UI may know. Numbers are counted, never listed."""
    current = mode()
    return {
        "enabled": enabled(),
        "transport": transport(),
        "mode": current,
        "ready": ready(),
        "bridgeConfigured": wa_bridge.configured(),
        "allowedRecipients": len(allowed_numbers()),
        "emergencyStop": comm_service.emergency_stop(),
        "sender": wa_bridge.profile_name(),
        "missing": ["MNH_WA_BRIDGE_URL"] if not wa_bridge.configured() else [],
        "autoSend": current in ("bridge", "twilio"),
    }


def send(to: str, body: str, *, confirm: bool, actor: str = "public") -> dict:
    """Send one WhatsApp text to an allowlisted number.

    ``bridge`` and ``twilio`` deliver; ``link`` returns a click-to-chat URL and
    does not claim delivery.

    Raises ``SendError`` with an HTTP status the route can pass straight on.
    """
    if not enabled():
        raise SendError(
            "CRARA WhatsApp sending is switched off (MNH_CLASSREP_WHATSAPP_ENABLED=0).",
            403,
        )
    if not confirm:
        raise SendError("Confirm the recipient and the message before sending.", 400)
    text = str(body or "").strip()
    if not text:
        raise SendError("There is nothing to send.", 400)

    try:
        chat_id = wa_bridge.normalise_target(to)
    except wa_bridge.BridgeError as error:
        raise SendError(str(error), 400) from error

    if wa_bridge.is_group(chat_id):
        raise SendError("CRARA sends to one WhatsApp number, not to a group.", 400)

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

    clipped = text[:MAX_BODY_LENGTH]
    current = mode()

    if current == "link":
        comm_contacts.audit(actor, "crara-whatsapp-link", digits, clipped[:200])
        return {
            "ok": True,
            "status": "needs_manual_send",
            "mode": "link",
            "to": digits,
            "link": build_link(digits, clipped),
            "detail": (
                "No WhatsApp bridge is configured, so this message was not sent. "
                "Open the link on a phone signed in to WhatsApp and press send."
            ),
        }

    if current == "twilio" and not twilio_configured():
        raise SendError(
            "Twilio is selected (MNH_CLASSREP_WHATSAPP_TRANSPORT=twilio) but "
            "MNH_TWILIO_ACCOUNT_SID and MNH_TWILIO_AUTH_TOKEN are not both set.",
            503,
        )
    if current == "bridge" and not wa_bridge.configured():
        raise SendError(
            "The WhatsApp bridge is selected but MNH_WA_BRIDGE_URL is not set.",
            503,
        )

    try:
        if current == "twilio":
            result = _twilio_send(digits, clipped)
        else:
            result = wa_bridge.send_text(chat_id, clipped)
    except SendError as error:
        comm_contacts.audit(actor, "crara-whatsapp-failed", digits, str(error)[:200])
        raise
    except wa_bridge.BridgeError as error:
        comm_contacts.audit(actor, "crara-whatsapp-failed", digits, str(error)[:200])
        raise SendError(str(error), 502) from error

    comm_contacts.audit(actor, "crara-whatsapp-sent", digits, clipped[:200])
    response = {
        "ok": True,
        "status": "sent",
        "mode": current,
        "to": digits,
        "chatId": chat_id,
    }
    if current == "twilio":
        response.update(result)
    else:
        response["sender"] = wa_bridge.profile_name()
        response["bridgeResponse"] = result.get("bridgeResponse")
    return response


@router.get("/whatsapp/status")
def whatsapp_status(mnh_session: str | None = Cookie(None)):
    """Whether CRARA can send right now, in which mode, and why not."""
    return status()


@router.post("/whatsapp/link")
def whatsapp_link(
    mnh_session: str | None = Cookie(None),
    data: dict = Body(default={}),
):
    """Build a click-to-chat link without sending anything."""
    digits = _digits(data.get("to") or "")
    if digits not in allowed_numbers():
        raise HTTPException(
            status_code=403,
            detail="That number is not on the CRARA WhatsApp allowlist.",
        )
    text = str(data.get("body") or "").strip()[:MAX_BODY_LENGTH]
    return {"ok": True, "to": digits, "link": build_link(digits, text)}


@router.post("/whatsapp/send")
def whatsapp_send(
    mnh_session: str | None = Cookie(None),
    data: dict = Body(default={}),
):
    """Send one WhatsApp text, or return a link when no bridge is configured."""
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
