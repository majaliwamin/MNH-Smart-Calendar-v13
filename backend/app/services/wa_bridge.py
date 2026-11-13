"""WhatsApp bridge sender — the single path for all automatic WhatsApp sending.

Meta's Cloud API is retired from this app (Amienz, 2026-11-13): messages now go
through the WhatsApp bridge running on the Asterisk server. The bridge is
addressed purely by environment variables, so any HTTP bridge works without
code changes:

    MNH_WA_BRIDGE_URL     base URL, e.g. http://asterisk.internal:3000 (WAHA)
                          or a cloudflared hostname in front of the bridge
    MNH_WA_BRIDGE_TOKEN   shared secret sent as "Authorization: Bearer <token>"
                          (omit the variable for bridges with no auth)
    MNH_WA_BRIDGE_STYLE   waha | generic   (default waha)
    MNH_WA_BRIDGE_SESSION WAHA session name (default "default")
    MNH_WA_BRIDGE_TIMEOUT request timeout seconds (default 20)

WAHA style  : POST {base}/api/sendText  {"session":..., "chatId":"<digits>@c.us", "text":...}
Generic style: POST {base}/send        {"phone":"<digits>", "message":<body>}
              (adapt MNH_WA_BRIDGE_STYLE or point at a tiny adapter Worker if
              your bridge speaks another shape)

Every send returns a normalised result so callers can log outcomes. This
module never checks consent — callers (AI trigger, reminders, drafts) must
enforce consent, do-not-contact and the emergency stop BEFORE calling.
"""
import json
import os
import urllib.error
import urllib.request


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


def status() -> dict:
    return {
        "provider": "WhatsApp bridge on the Asterisk server",
        "configured": configured(),
        "style": style(),
        "missing": ["MNH_WA_BRIDGE_URL"] if not configured() else [],
    }


def send_text(number: str, body: str, *, timeout: int | None = None) -> dict:
    """Send one WhatsApp text through the bridge. `number` is digits (E.164, no '+')."""
    digits = str(number or "").strip().lstrip("+")
    if not digits.isdigit():
        raise BridgeError(f"'{number}' is not a valid WhatsApp number.")
    text = str(body or "").strip()
    if not text:
        raise BridgeError("Cannot send an empty message.")
    if not configured():
        raise BridgeError(
            "The WhatsApp bridge is not configured on this server yet. "
            "Set MNH_WA_BRIDGE_URL (and optionally MNH_WA_BRIDGE_TOKEN / _STYLE / _SESSION)."
        )
    if style() == "waha":
        url = f"{base_url()}/api/sendText"
        payload = {"session": session(), "chatId": f"{digits}@c.us", "text": text}
    else:
        url = f"{base_url()}/send"
        payload = {"phone": digits, "message": text}
    headers = {"Content-Type": "application/json"}
    token = _env("MNH_WA_BRIDGE_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
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
        raise BridgeError(f"The WhatsApp bridge rejected the message ({error.code}). {detail}".strip()) from error
    except urllib.error.URLError as error:
        raise BridgeError(f"The WhatsApp bridge could not be reached: {error.reason}") from error
    try:
        result = json.loads(raw)
    except ValueError:
        result = {"raw": raw[:200]}
    return {"ok": True, "bridgeResponse": result, "to": digits}
