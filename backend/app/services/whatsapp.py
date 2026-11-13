"""WhatsApp delivery for timetable reminders (Meta WhatsApp Cloud API).

Credentials live only in the environment, never in the repository:

    MNH_WHATSAPP_TOKEN        permanent access token for the WhatsApp Business account
    MNH_WHATSAPP_PHONE_ID     the sender phone-number id ("from" number)
    MNH_WHATSAPP_API_VERSION  Graph API version (default v21.0)
    MNH_WHATSAPP_SENDER_NAME  name shown at the top of every message
    MNH_WHATSAPP_ENABLED      "0" pauses sending without removing credentials

The sender that recipients see is the WhatsApp Business **profile display name**,
"Maternal & Neonatal Health Smart Time Table", approved in Meta Business Manager.
The same name is printed as the first line of every message so the sender is never
in doubt, even on clients that truncate the profile name.
"""
import json
import os
import re
import urllib.error
import urllib.request

from app.config import WHATSAPP_SENDER_NAME

DEFAULT_COUNTRY = os.getenv("MNH_DEFAULT_COUNTRY", "265")  # Malawi


class WhatsAppError(RuntimeError):
    """Delivery failed, or credentials/configuration are missing."""


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def token() -> str:
    return _env("MNH_WHATSAPP_TOKEN")


def phone_number_id() -> str:
    return _env("MNH_WHATSAPP_PHONE_ID")


def api_version() -> str:
    return _env("MNH_WHATSAPP_API_VERSION", "v21.0")


def enabled() -> bool:
    return _env("MNH_WHATSAPP_ENABLED", "1").lower() not in ("0", "false", "no", "off")


def configured() -> bool:
    return bool(token() and phone_number_id())


def status() -> dict:
    """What the server can currently do — safe to show in the interface."""
    return {
        "provider": "Meta WhatsApp Cloud API",
        "configured": configured(),
        "enabled": enabled(),
        "sender": WHATSAPP_SENDER_NAME,
        "phoneNumberId": phone_number_id() or None,
        "apiVersion": api_version(),
        "missing": [name for name, value in (("MNH_WHATSAPP_TOKEN", token()), ("MNH_WHATSAPP_PHONE_ID", phone_number_id())) if not value],
    }


def normalise_phone(raw, default_country: str = DEFAULT_COUNTRY) -> str:
    """Return an E.164 number without the '+', defaulting to Malawi for local numbers.

    +265 881 988 156 -> 265881988156
    0881988156       -> 265881988156
    881988156        -> 265881988156
    """
    digits = re.sub(r"[^\d]", "", str(raw or ""))
    if not digits:
        raise WhatsAppError("Enter a phone number, for example +265881988156.")
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith(default_country) and len(digits) >= len(default_country) + 8:
        pass  # already international
    elif digits.startswith("0") and len(digits) == 10:
        digits = default_country + digits[1:]
    elif len(digits) == 9:
        digits = default_country + digits
    if not 8 <= len(digits) <= 15:
        raise WhatsAppError(f"'{raw}' is not a valid international phone number.")
    return digits


def send_text(to, body: str, *, timeout: int = 20) -> dict:
    """Send one plain-text WhatsApp message. Raises WhatsAppError with a readable reason."""
    if not enabled():
        raise WhatsAppError("WhatsApp sending is switched off (MNH_WHATSAPP_ENABLED=0).")
    if not configured():
        raise WhatsAppError(
            "WhatsApp is not configured on this server yet. Set MNH_WHATSAPP_TOKEN and "
            "MNH_WHATSAPP_PHONE_ID to the WhatsApp Business Cloud API credentials."
        )
    number = normalise_phone(to)
    text = str(body or "").strip()
    if not text:
        raise WhatsAppError("There is nothing to send.")
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": number,
        "type": "text",
        "text": {"preview_url": False, "body": text[:4000]},
    }
    request = urllib.request.Request(
        f"https://graph.facebook.com/{api_version()}/{phone_number_id()}/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            failure = json.loads(error.read().decode("utf-8") or "{}")
            detail = str((failure.get("error") or {}).get("message") or "")
        except (ValueError, AttributeError):
            detail = ""
        raise WhatsAppError(f"WhatsApp rejected the message ({error.code}). {detail}".strip()) from error
    except urllib.error.URLError as error:
        raise WhatsAppError(f"WhatsApp could not be reached: {error.reason}") from error
    message_id = ""
    try:
        message_id = str(((data.get("messages") or [])[0] or {}).get("id", ""))
    except (IndexError, AttributeError, TypeError):
        message_id = ""
    return {"ok": True, "to": number, "messageId": message_id, "sender": WHATSAPP_SENDER_NAME}
