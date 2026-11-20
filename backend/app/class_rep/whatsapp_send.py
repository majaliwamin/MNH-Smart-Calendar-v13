"""Two-step WhatsApp sending from CRARA.

CRARA never sends from a free-form model claim. A signed-in user must first ask
for a send, review the exact text and recipient group, then reply with the token
from the preview. The only delivery path is the shared WAHA bridge, and the
communications safeguards (group consent, opt-out, DNC, emergency stop) are
re-checked again immediately before dispatch.
"""
import json
import re
import secrets
import time

from app.class_rep import memory
from app.config import WHATSAPP_SENDER_NAME
from app.database.connection import database
from app.services import comm_contacts, comm_service, wa_bridge

CONFIRM_COLLECTION = "cara_wa_confirmations"
LOG_COLLECTION = "cara_wa_sends"
CONFIRM_SECONDS = 600
MAX_BODY_CHARS = 2000

_TARGET = r"(?P<target>(?:the\s+)?(?:all\s+students|students?|class|cohort|everyone|ophunzira|kalasi|gulu|(?:[A-Za-z0-9][\w\s-]{0,60}?\s+group)))"
_SEND_PATTERNS = (
    re.compile(
        r"^(?:please\s+)?(?:send|post)\s+(?:a\s+)?(?:whatsapp\s+|wa\s+)?"
        r"(?:message|announcement|notice|text)\s+(?:to|on)\s+" + _TARGET +
        r"(?:\s+(?:saying|that|reading))?\s*[:\-–—]?\s+(?P<body>.+)$", re.I),
    re.compile(
        r"^(?:please\s+)?(?:send|post)\s+(?:the\s+)?(?:students?|class|cohort|everyone)\s+"
        r"(?:a\s+)?(?:whatsapp\s+)?(?:message|announcement|notice|text)"
        r"(?:\s+(?:saying|that))?\s*[:\-–—]?\s+(?P<body>.+)$", re.I),
    re.compile(
        r"^(?:please\s+)?(?:message|notify|tell)\s+" + _TARGET +
        r"(?:\s+(?:saying|that))?\s*[:\-–—]?\s+(?P<body>.+)$", re.I),
    re.compile(
        r"^(?:chonde\s+)?(?:tumiza|tumizani)\s+(?:uthenga|whatsapp|message)\s+(?:kwa|ku|to)\s+" + _TARGET +
        r"(?:\s+(?:woti|wakuti|saying|that))?\s*[:\-–—]?\s+(?P<body>.+)$", re.I),
    re.compile(
        r"^(?:chonde\s+)?(?:uzani|dziwitsani)\s+" + _TARGET +
        r"(?:\s+(?:kuti|that))?\s*[:\-–—]?\s+(?P<body>.+)$", re.I),
)
_CONFIRM_PATTERN = re.compile(
    r"^\s*(?:confirm\s+send|t_simikizani\s+kutumiza|confirm)\s+([A-F0-9]{6,12})[.!?]?\s*$", re.I)


class SendError(RuntimeError):
    """A send request is blocked or could not be dispatched safely."""


def _text(language: str, english: str, chichewa: str) -> str:
    return chichewa if str(language or "EN").strip().upper() == "CH" else english


def _now() -> int:
    return int(time.time())


def _read_confirmation(user_id: str, token: str) -> dict | None:
    item_id = f"{user_id}:{token.upper()}"
    with database() as connection:
        row = connection.execute(
            "SELECT data FROM docs WHERE col=? AND id=?", (CONFIRM_COLLECTION, item_id)
        ).fetchone()
    if not row:
        return None
    try:
        record = json.loads(row["data"])
    except (TypeError, json.JSONDecodeError):
        return None
    if int(record.get("expiresAt") or 0) < _now():
        _delete_confirmation(user_id, token)
        return None
    return record


def _write_confirmation(user_id: str, token: str, record: dict) -> None:
    item_id = f"{user_id}:{token}"
    with database() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (CONFIRM_COLLECTION, item_id, json.dumps(record, ensure_ascii=False), int(time.time() * 1000)),
        )


def _delete_confirmation(user_id: str, token: str) -> None:
    item_id = f"{user_id}:{token.upper()}"
    with database() as connection:
        connection.execute("DELETE FROM docs WHERE col=? AND id=?", (CONFIRM_COLLECTION, item_id))


def _with_sender_line(body: str) -> str:
    sender = WHATSAPP_SENDER_NAME.strip()
    if not sender or body.casefold().startswith(sender.casefold()):
        return body
    return f"{sender}\n\n{body}"


def parse_request(message: str) -> dict | None:
    """Return a deterministic preview/confirm request; never infer one from prose."""
    text = re.sub(r"\s+", " ", str(message or "")).strip()
    confirm = _CONFIRM_PATTERN.match(text)
    if confirm:
        return {"kind": "confirm", "token": confirm.group(1).upper()}
    for pattern in _SEND_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        body = str(match.group("body") or "").strip().strip("\"'“”‘’")
        body = re.sub(r"\s+", " ", body)[:MAX_BODY_CHARS]
        if not body.strip(" .!?,:;-–—"):
            continue
        target = str(match.groupdict().get("target") or "students").strip()
        return {"kind": "preview", "body": body, "target": target}
    return None


def _student_groups() -> list:
    groups = []
    for contact in comm_contacts.list_contacts():
        if comm_contacts.contact_kind(contact) != "group":
            continue
        if str(contact.get("category") or "").strip().lower() != "student":
            continue
        allowed, _ = comm_contacts.contact_allowed(contact, "whatsapp")
        if allowed:
            groups.append(contact)
    return groups


def _pick_group(target: str) -> dict:
    groups = _student_groups()
    if not groups:
        raise SendError(
            "No saved student WhatsApp group is ready. Add a WhatsApp group contact with "
            "category 'Student' and WhatsApp consent, or ask an editor to do it."
        )
    hint = re.sub(r"^the\s+", "", str(target or ""), flags=re.I).strip()
    hint = re.sub(r"\s+group$", "", hint, flags=re.I).strip().casefold()
    generic = {"student", "students", "all students", "class", "cohort", "everyone",
               "ophunzira", "kalasi", "gulu"}
    if hint and hint not in generic:
        matches = [g for g in groups if hint in str(g.get("name") or "").casefold()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise SendError("More than one saved student group matches that name. Please name the group more precisely.")
        raise SendError(f"No saved student WhatsApp group is named '{hint}'.")
    if len(groups) == 1:
        return groups[0]
    names = ", ".join(str(g.get("name") or g.get("id")) for g in groups[:5])
    raise SendError(f"More than one student WhatsApp group is saved ({names}). Name the group in the request.")


def _preview(user_id: str, request: dict, language: str) -> dict:
    if memory.SECRET_PATTERN.search(request["body"]):
        raise SendError("I will not send a message containing a key, token, password or other credential.")
    group = _pick_group(request.get("target"))
    body = _with_sender_line(request["body"])
    token = secrets.token_hex(4).upper()
    record = {
        "userId": user_id,
        "token": token,
        "groupId": group["id"],
        "groupName": str(group.get("name") or "student group"),
        "body": body,
        "createdAt": _now(),
        "expiresAt": _now() + CONFIRM_SECONDS,
        "status": "pending",
    }
    _write_confirmation(user_id, token, record)
    comm_contacts.audit(user_id, "crara-wa-preview", group["id"], f"token {token}")
    reply = _text(
        language,
        "I have prepared this WhatsApp message for " + record["groupName"] + ":\n\n" + body +
        "\n\nReply `CONFIRM SEND " + token + "` to send it now. Nothing has been sent yet.",
        "Ndakonzekeretsa uthenga wa WhatsApp wa gulu la " + record["groupName"] + ":\n\n" + body +
        "\n\nYankhani `CONFIRM SEND " + token + "` kuti mutumize tsopano. Palibe chomwe chatumizidwa pano.",
    )
    return {"reply": reply, "provider": "CRARA WhatsApp send", "model": "pending-confirmation", "token": token}


def _confirm(user_id: str, request: dict, language: str) -> dict:
    record = _read_confirmation(user_id, request["token"])
    if not record or record.get("status") != "pending":
        raise SendError(_text(language,
            "That confirmation code has expired or was already used. Ask CRARA to prepare the message again.",
            "Khodi yotsimikizira yatha kapena yagwiritsidwa ntchito. Funsani CRARA kukonzekeretsanso uthengawo."))
    group = comm_contacts.get_contact(str(record.get("groupId") or ""))
    if not group:
        raise SendError("The saved student group no longer exists. Ask CRARA to prepare the message again.")
    allowed, reason = comm_contacts.contact_allowed(group, "whatsapp")
    if not allowed:
        raise SendError(f"The saved student group cannot be messaged: {reason}.")
    if comm_service.emergency_stop():
        raise SendError("All communications are paused by the emergency stop. Nothing was sent.")
    if not wa_bridge.configured():
        raise SendError(_text(language,
            "The WhatsApp bridge is not configured on this server yet. Nothing was sent.",
            "Bridge ya WhatsApp sinakonzedwe pa sevayo. Palibe chomwe chatumizidwa."))
    try:
        result = wa_bridge.send_text(group["phone"], str(record.get("body") or ""))
    except wa_bridge.BridgeError as error:
        raise SendError(f"The WhatsApp bridge could not send the message: {error}") from error
    _delete_confirmation(user_id, request["token"])
    log = {
        "userId": user_id,
        "groupId": group["id"],
        "groupName": str(group.get("name") or "student group"),
        "body": str(record.get("body") or ""),
        "bridgeResponse": result,
        "sentAt": _now(),
    }
    with database() as connection:
        connection.execute(
            "INSERT INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (LOG_COLLECTION, f"{user_id}:{_now()}:{request['token']}",
             json.dumps(log, ensure_ascii=False), int(time.time() * 1000)),
        )
    comm_contacts.audit(user_id, "crara-wa-send", group["id"], str(record.get("body") or "")[:120])
    reply = _text(language,
        "Sent via WhatsApp to " + log["groupName"] + ".",
        "Uthenga watumizidwa kudzera WhatsApp ku gulu la " + log["groupName"] + ".")
    return {"reply": reply, "provider": "CRARA WhatsApp send", "model": "WAHA bridge"}


def handle(user_id: str, message: str, language: str = "EN") -> dict | None:
    """Handle an explicit send/confirm turn, or return None for normal chat."""
    request = parse_request(message)
    if request is None:
        return None
    if request["kind"] == "confirm":
        return _confirm(user_id, request, language)
    return _preview(user_id, request, language)


def status() -> dict:
    """Non-sensitive readiness summary for CRARA status endpoints."""
    try:
        group_ready = bool(_student_groups())
    except Exception:
        group_ready = False
    missing = ["MNH_WA_BRIDGE_URL"] if not wa_bridge.configured() else []
    if not group_ready:
        missing.append("saved consented student WhatsApp group")
    return {
        "enabled": True,
        "approval": "two_step_confirmation",
        "bridgeConfigured": wa_bridge.configured(),
        "studentGroupReady": group_ready,
        "missing": missing,
    }
