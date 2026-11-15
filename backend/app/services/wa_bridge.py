"""WhatsApp bridge sender — the single path for all automatic WhatsApp sending.

Meta's Cloud API is retired from this app (Amienz, 2026-11-13): messages now go
through the WhatsApp bridge running on the Asterisk server. The bridge is
addressed purely by environment variables, so any HTTP bridge works without
code changes:

    MNH_WA_BRIDGE_URL     base URL, e.g. http://asterisk.internal:3000 (WAHA)
                          or a cloudflared hostname in front of the bridge
    MNH_WA_BRIDGE_TOKEN   shared secret. Sent as both "Authorization: Bearer
                          <token>" and "X-Api-Key: <token>" so WAHA and generic
                          bridges both authenticate (omit for no-auth bridges)
    MNH_WA_BRIDGE_STYLE   waha | generic   (default waha)
    MNH_WA_BRIDGE_SESSION WAHA session name (default "default")
    MNH_WA_BRIDGE_TIMEOUT request timeout seconds (default 20)
    MNH_WA_SENDER_NUMBER  the account that sends (digits, e.g. 26599130362);
                          informational — shown in status, never a credential
    MNH_WA_PROFILE_NAME   display/push name for the account (defaults to the
                          application name, MNH_WHATSAPP_SENDER_NAME)

A target is either one person (a phone number) or a whole group. Both are
addressed with a WAHA "chat id":

    265881988156             -> 265881988156@c.us        (one person)
    1203630…@g.us            -> 1203630…@g.us            (a group)
    <digits>@s.whatsapp.net  -> <digits>@s.whatsapp.net

WAHA style  : POST {base}/api/sendText  {"session":…, "chatId":…, "text":…}
              PUT  {base}/api/{session}/profile/name  {"name":…}
Generic style: POST {base}/send        {"phone":…, "chatId":…, "message":…}
              POST {base}/profile/name {"name":…}

Only the application name is ever shown to a recipient: call set_profile_name()
once after the bridge is configured so the account itself carries the app name
(never the sending phone number).

Every send returns a normalised result so callers can log outcomes. This
module never checks consent — callers (AI trigger, reminders, drafts) must
enforce consent, do-not-contact and the emergency stop BEFORE calling.
"""
import json
import os
import urllib.error
import urllib.request

from app.config import WHATSAPP_SENDER_NAME

# Chat-id servers WhatsApp uses. Group ids end in "@g.us"; people end in
# "@c.us" (Cloud/Web) or "@s.whatsapp.net" (multi-device).
CHAT_SERVERS = ("c.us", "g.us", "s.whatsapp.net", "lid", "broadcast")
GROUP_SUFFIX = "@g.us"


class BridgeError(RuntimeError):
    """Bridge unconfigured, unreachable, or it refused the message."""


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def base_url() -> str:
    return _env("MNH_WA_BRIDGE_URL").rstrip("/")


def style() -> str:
    return _env("MNH_WA_BRIDGE_STYLE", "waha").lower()


def session() -> str:
    return _env("MNH_WA_BRIDGE_SESSION", "default")


def configured() -> bool:
    return bool(base_url())


def sender_number() -> str:
    """The WhatsApp account that sends (digits only). Informational, never a secret."""
    return "".join(ch for ch in _env("MNH_WA_SENDER_NUMBER") if ch.isdigit())


def profile_name() -> str:
    """The name the account should carry — the application name by default."""
    return _env("MNH_WA_PROFILE_NAME") or WHATSAPP_SENDER_NAME


def status() -> dict:
    return {
        "provider": "WhatsApp bridge on the Asterisk server",
        "configured": configured(),
        "style": style(),
        "session": session(),
        "sender": sender_number() or None,
        "profileName": profile_name(),
        "missing": ["MNH_WA_BRIDGE_URL"] if not configured() else [],
    }


def normalise_target(target) -> str:
    """Return a WAHA chat id for a person or a group.

    A bare number becomes '<digits>@c.us'; an explicit chat id
    ('…@g.us', '…@c.us', '…@s.whatsapp.net') is kept (server lower-cased).
    """
    text = str(target or "").strip()
    if not text:
        raise BridgeError("Enter a WhatsApp number or group id.")
    if "@" in text:
        local, _, server = text.partition("@")
        local = "".join(ch for ch in local if ch.isdigit())
        server = server.strip().lower()
        if not local or server not in CHAT_SERVERS:
            raise BridgeError(f"'{target}' is not a valid WhatsApp chat id.")
        return f"{local}@{server}"
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        raise BridgeError(f"'{target}' is not a valid WhatsApp number.")
    return f"{digits}@c.us"


def is_group(target) -> bool:
    """True when the target addresses a group rather than a single person."""
    return str(target or "").strip().lower().endswith(GROUP_SUFFIX)


def _call(url: str, payload: dict, *, method: str = "POST", timeout: int | None = None) -> dict:
    """POST/PUT JSON to the bridge and return the decoded response."""
    headers = {"Content-Type": "application/json"}
    token = _env("MNH_WA_BRIDGE_TOKEN")
    if token:
        # WAHA authenticates with "X-Api-Key"; other bridges use "Authorization:
        # Bearer". Send both — each bridge reads the one it understands.
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Api-Key"] = token
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout or int(_env("MNH_WA_BRIDGE_TIMEOUT", "20"))) as response:
            raw = response.read().decode("utf-8") or "{}"
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            detail = str(json.loads(error.read().decode("utf-8") or "{}"))[:200]
        except (ValueError, AttributeError):
            detail = ""
        raise BridgeError(f"The WhatsApp bridge rejected the request ({error.code}). {detail}".strip()) from error
    except urllib.error.URLError as error:
        raise BridgeError(f"The WhatsApp bridge could not be reached: {error.reason}") from error
    try:
        return json.loads(raw)
    except ValueError:
        return {"raw": raw[:200]}


def send_text(target, body: str, *, timeout: int | None = None) -> dict:
    """Send one WhatsApp text to a person (number) or a group (chat id)."""
    chat = normalise_target(target)
    group = chat.endswith(GROUP_SUFFIX)
    text = str(body or "").strip()
    if not text:
        raise BridgeError("Cannot send an empty message.")
    if not configured():
        raise BridgeError(
            "The WhatsApp bridge is not configured on this server yet. "
            "Set MNH_WA_BRIDGE_URL (and optionally MNH_WA_BRIDGE_TOKEN / _STYLE / _SESSION)."
        )
    if style() == "waha":
        result = _call(
            f"{base_url()}/api/sendText",
            {"session": session(), "chatId": chat, "text": text},
            timeout=timeout,
        )
    else:
        result = _call(
            f"{base_url()}/send",
            {"phone": chat.split("@", 1)[0], "chatId": chat, "isGroup": group, "message": text},
            timeout=timeout,
        )
    return {"ok": True, "bridgeResponse": result, "to": chat.split("@", 1)[0], "chatId": chat, "isGroup": group}


def set_profile_name(name: str | None = None, *, timeout: int | None = None) -> dict:
    """Set the WhatsApp account profile (push) name shown to recipients.

    Defaults to the application name so a recipient only ever sees
    "Maternal & Neonatal Health Smart Time Table", never the sending number.
    """
    new_name = str(name or "").strip() or profile_name()
    if not configured():
        raise BridgeError(
            "The WhatsApp bridge is not configured on this server yet. "
            "Set MNH_WA_BRIDGE_URL before setting the display name."
        )
    if style() == "waha":
        result = _call(f"{base_url()}/api/{session()}/profile/name", {"name": new_name},
                       method="PUT", timeout=timeout)
    else:
        result = _call(f"{base_url()}/profile/name", {"name": new_name},
                       method="POST", timeout=timeout)
    return {"ok": True, "name": new_name, "bridgeResponse": result}
