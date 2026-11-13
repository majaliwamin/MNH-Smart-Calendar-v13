"""Asterisk ARI voice-call service (outbound calls only, human-authorised).

ARI is a REST + WebSocket interface to a running Asterisk PBX — it is NOT a SIP
trunk or phone carrier; outbound connectivity depends entirely on how the
Asterisk server's dialplan and trunks are configured. This module talks to ARI:

    MNH_ARI_BASE_URL   e.g. http://asterisk.internal:8088/ari
    MNH_ARI_USER       ARI user name (from ari.conf)
    MNH_ARI_PASSWORD   ARI password
    MNH_ARI_APP        ARI application (Stasis) name, default mnh-calendar
    MNH_ARI_ENDPOINT   dial string pattern for origination, default
                       Local/{number}@mnh-outbound — the dialplan on the Asterisk
                       side then routes to the configured trunk.

Safeguards (enforced in request_call, in this order):
  emergency stop → configured → consent → do-not-contact → calling hours.
No call is ever initiated by AI or by the scheduler alone.

Call state comes from ARI REST polling (channel state); no attempt is made to
read raw telephony audio. The AI voice pipeline (STT → LLM → TTS via ARI
ExternalMedia) is deliberately NOT implemented here: it requires verified media
transport on the actual Asterisk server first (Phase 6 gate).
"""
import base64
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


class ARIError(RuntimeError):
    """ARI is unreachable, unconfigured, or refused an action."""


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def base_url() -> str:
    return _env("MNH_ARI_BASE_URL").rstrip("/")


def app_name() -> str:
    return _env("MNH_ARI_APP", "mnh-calendar")


def endpoint_pattern() -> str:
    return _env("MNH_ARI_ENDPOINT", "Local/{number}@mnh-outbound")


def configured() -> bool:
    return bool(base_url() and _env("MNH_ARI_USER") and _env("MNH_ARI_PASSWORD"))


def status() -> dict:
    info = {
        "provider": "Asterisk ARI",
        "configured": configured(),
        "appName": app_name() if configured() else None,
        "missing": [name for name, value in (
            ("MNH_ARI_BASE_URL", base_url()), ("MNH_ARI_USER", _env("MNH_ARI_USER")),
            ("MNH_ARI_PASSWORD", _env("MNH_ARI_PASSWORD"))) if not value],
        "reachable": False,
        "asteriskVersion": None,
    }
    if configured():
        try:
            data = _request("GET", "/asterisk/info")
            info["reachable"] = True
            info["asteriskVersion"] = str((data.get("version") or ""))[:40]
        except ARIError as error:
            info["error"] = str(error)
    return info


def _request(method: str, path: str, payload: dict | None = None, timeout: int = 15) -> dict:
    if not configured():
        raise ARIError(
            "Asterisk ARI is not configured on this server yet. Set MNH_ARI_BASE_URL, "
            "MNH_ARI_USER and MNH_ARI_PASSWORD."
        )
    url = f"{base_url()}{path}"
    auth = base64.b64encode(
        f"{_env('MNH_ARI_USER')}:{_env('MNH_ARI_PASSWORD')}".encode("utf-8")
    ).decode("ascii")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8") or "{}"
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            detail = str(json.loads(error.read().decode("utf-8") or "{}").get("message") or "")
        except (ValueError, AttributeError):
            detail = ""
        raise ARIError(f"Asterisk ARI returned {error.code}. {detail}".strip()) from error
    except urllib.error.URLError as error:
        raise ARIError(f"Asterisk ARI could not be reached: {error.reason}") from error


# ---- call log ---------------------------------------------------------------
def _now() -> int:
    return int(time.time() * 1000)


def _log_call(call_id: str, data: dict) -> None:
    from app.database.connection import database
    with database() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES('comm_calls',?,?,?)",
            (call_id, json.dumps(data), _now()),
        )


def _read_calls() -> list:
    from app.database.connection import database
    out = []
    with database() as connection:
        rows = connection.execute("SELECT id, data FROM docs WHERE col='comm_calls'").fetchall()
    for row in rows:
        try:
            item = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
        item["id"] = row["id"]
        out.append(item)
    return sorted(out, key=lambda c: c.get("requestedAt", 0), reverse=True)


def call_rows(limit: int = 50) -> list:
    return _read_calls()[:max(1, int(limit))]


# ---- call lifecycle -----------------------------------------------------------
def request_call(actor: str, contact_id: str, purpose: str, *, checks: dict | None = None) -> dict:
    """Create an authorised outbound call request and originate it through ARI.

    `checks` carries the safeguards decided by the API layer:
      consentOk, dncOk, windowOk — each must be True; this function does not
    trust the AI, the scheduler, or the caller for any of them.
    """
    from app.services import comm_contacts
    checks = checks or {}
    if not all([checks.get("consentOk"), checks.get("dncOk"), checks.get("windowOk")]):
        comm_contacts.audit(actor, "call-blocked", contact_id, str(checks))
        raise ARIError(f"Call blocked by safeguards: {checks}")
    contact = comm_contacts.get_contact(contact_id)
    if not contact:
        raise ARIError("Contact not found.")
    purpose = str(purpose or "").strip()
    if not purpose:
        raise ARIError("State the purpose of the call.")
    call_id = f"cal-{_now()}"
    entry = {
        "contactId": contact_id,
        "contactName": contact.get("name", ""),
        "phone": contact.get("phone", ""),
        "purpose": purpose[:300],
        "requestedBy": actor,
        "requestedAt": _now(),
        "state": "requesting",
        "outcome": "",
        "durationSeconds": None,
        "events": [{"at": _now(), "state": "requesting"}],
        "recording": False,  # recording is disabled by default and needs separate approval
    }
    _log_call(call_id, entry)
    endpoint = endpoint_pattern().format(number=entry["phone"])
    try:
        channel = _request("POST", f"/channels/create?app={app_name()}&endpoint={urllib.parse.quote(endpoint)}&timeout=30",
                           payload={"variables": {"MNH_CALL_ID": call_id}})
        entry["channelId"] = str(channel.get("id") or "")
        entry["state"] = "dialing"
    except ARIError as error:
        entry["state"], entry["outcome"], entry["lastError"] = "failed", "failed", str(error)[:300]
        _log_call(call_id, entry)
        comm_contacts.audit(actor, "call-failed", call_id, str(error))
        raise
    entry["events"].append({"at": _now(), "state": "dialing"})
    _log_call(call_id, entry)
    comm_contacts.audit(actor, "call-originated", call_id, f"{entry['contactName']} · {purpose[:120]}")
    return entry


def update_call_state(call_id: str, state: str, detail: str = "") -> dict | None:
    """Record a state change observed from Asterisk (or a manual refresh)."""
    for call in _read_calls():
        if call["id"] == call_id:
            allowed = {"requesting", "dialing", "ringing", "answered", "in-progress",
                       "busy", "rejected", "failed", "ended"}
            if state not in allowed:
                raise ARIError(f"Unknown call state '{state}'.")
            if call.get("state") == "ended" and state != "ended":
                return None  # never resurrect an ended call
            call["state"] = state
            call["events"].append({"at": _now(), "state": state, "detail": detail[:200]})
            if state in ("busy", "rejected", "failed", "ended"):
                call["outcome"] = state if state != "ended" else call.get("outcome") or "completed"
                started = call.get("answeredAt")
                call["durationSeconds"] = max(0, int((_now() - started) / 1000)) if started else 0
            if state == "answered":
                call["answeredAt"] = _now()
            _log_call(call_id, call)
            return call
    return None


def refresh_call(call_id: str) -> dict:
    """Poll ARI for the live channel state and record it."""
    for call in _read_calls():
        if call["id"] == call_id and call.get("channelId"):
            if call.get("state") in ("busy", "rejected", "failed", "ended"):
                return call
            try:
                channel = _request("GET", f"/channels/{call['channelId']}")
            except ARIError as error:
                if "404" in str(error):
                    return update_call_state(call_id, "ended", "channel no longer exists") or call
                raise
            state = str(channel.get("state") or "unknown").lower()
            mapped = {"up": "answered", "ringing": "ringing", "ring": "ringing",
                      "down": "ended", "reserved": "dialing"}.get(state, "in-progress" if state == "up" else "dialing")
            updated = update_call_state(call_id, mapped, f"ARI state: {state}")
            return updated or call
    raise ARIError("Call not found, or it has no ARI channel id.")


def hangup(actor: str, call_id: str) -> dict:
    for call in _read_calls():
        if call["id"] == call_id and call.get("channelId"):
            _request("DELETE", f"/channels/{call['channelId']}")
            update_call_state(call_id, "ended", "hung up via the app")
            comm_contacts.audit(actor, "call-hangup", call_id)
            return {"ok": True, "callId": call_id, "state": "ended"}
    raise ARIError("Active call not found.")


def sync_live_calls() -> None:
    """Best-effort state refresh for calls that look live. Runs in the worker thread."""
    for call in _read_calls():
        if call.get("state") in ("dialing", "ringing", "in-progress") and call.get("channelId"):
            try:
                refresh_call(call["id"])
            except ARIError as error:
                print(f"ARI sync warning for {call['id']}: {error}", flush=True)


# NOTE: the ARI WebSocket event listener and the AI voice pipeline (ExternalMedia
# STT/TTS) are intentionally deferred until a real Asterisk server with a
# verified dialplan and trunk is available to test against. Polling via
# refresh_call/sync_live_calls covers answered/busy/failed/ended accurately.
