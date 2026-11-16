"""Persistent CARA identity, conversation, memory, task and reminder store.

Records are scoped to an authenticated account and stored in the existing
application database. Passwords are PBKDF2 hashes; session tokens are never
stored in plaintext.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.database.connection import database

COL_USERS = "cara_users"
COL_SESSIONS = "cara_sessions"
COL_CONVERSATIONS = "cara_conversations"
COL_MEMORIES = "cara_memories"
COL_TASKS = "cara_tasks"
COL_REMINDERS = "cara_reminders"
SESSION_SECONDS = 60 * 60 * 24 * 30
PBKDF2_ROUNDS = 310_000
SECRET_PATTERN = re.compile(r"(api[_ -]?key|password|passwd|token|secret|authorization)\s*[:=]|\bbearer\s+\S+|\bsk-[A-Za-z0-9_-]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I)
WORD_PATTERN = re.compile(r"[a-z0-9]{3,}", re.I)


class MemoryError(ValueError):
    pass


def _now() -> int:
    return int(time.time() * 1000)


def _email_id(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def _doc_id(user_id: str, item_id: str) -> str:
    return user_id + ":" + item_id


def _read(collection: str, item_id: str):
    with database() as db:
        row = db.execute("SELECT data FROM docs WHERE col=? AND id=?", (collection, item_id)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["data"])
    except (TypeError, json.JSONDecodeError):
        return None


def _write(collection: str, item_id: str, value: dict):
    with database() as db:
        db.execute(
            "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (collection, item_id, json.dumps(value, ensure_ascii=False), _now()),
        )


def _list(collection: str, user_id: str, limit: int = 100) -> list[dict]:
    with database() as db:
        rows = db.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? AND id LIKE ? ORDER BY updated_at DESC LIMIT ?",
            (collection, user_id + ":%", max(1, min(int(limit), 500))),
        ).fetchall()
    result = []
    for row in rows:
        try:
            item = json.loads(row["data"])
            item["id"] = str(row["id"]).split(":", 1)[1]
            item["updated_at"] = row["updated_at"]
            result.append(item)
        except (TypeError, json.JSONDecodeError):
            continue
    return result


def _delete(collection: str, user_id: str, item_id: str) -> bool:
    with database() as db:
        cursor = db.execute("DELETE FROM docs WHERE col=? AND id=?", (collection, _doc_id(user_id, item_id)))
        return cursor.rowcount > 0


def create_account(name: str, email: str, password: str) -> dict:
    name = str(name or "").strip()[:100]
    email = str(email or "").strip().lower()[:254]
    password = str(password or "")
    if not name or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise MemoryError("Enter your name and a valid email address.")
    if len(password) < 12 or len(password) > 256:
        raise MemoryError("Use a password between 12 and 256 characters.")
    user_id = _email_id(email)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    user = {"name": name, "email": email, "salt": salt.hex(), "password_hash": digest.hex(),
            "created_at": _now(), "updated_at": _now()}
    with database() as db:
        cursor = db.execute("INSERT OR IGNORE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
                            (COL_USERS, user_id, json.dumps(user, ensure_ascii=False), _now()))
        if cursor.rowcount == 0:
            raise MemoryError("An account with this email already exists.")
    return {"id": user_id, "name": name, "email": email}


def verify_account(email: str, password: str):
    user_id = _email_id(email)
    user = _read(COL_USERS, user_id)
    if not user:
        # Perform a dummy hash to reduce account-enumeration timing differences.
        hashlib.pbkdf2_hmac("sha256", str(password).encode(), b"cara-dummy-salt", PBKDF2_ROUNDS)
        return None
    try:
        expected = bytes.fromhex(user["password_hash"])
        salt = bytes.fromhex(user["salt"])
    except (KeyError, ValueError):
        return None
    actual = hashlib.pbkdf2_hmac("sha256", str(password).encode(), salt, PBKDF2_ROUNDS)
    return {"id": user_id, "name": user["name"], "email": user["email"]} if hmac.compare_digest(actual, expected) else None


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    digest = hashlib.sha256(token.encode()).hexdigest()
    _write(COL_SESSIONS, digest, {"user_id": user_id, "expires_at": int(time.time()) + SESSION_SECONDS})
    return token


def resolve_session(token: str | None):
    if not token:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    session = _read(COL_SESSIONS, digest)
    if not session or int(session.get("expires_at", 0)) < int(time.time()):
        if session:
            with database() as db:
                db.execute("DELETE FROM docs WHERE col=? AND id=?", (COL_SESSIONS, digest))
        return None
    user = _read(COL_USERS, session.get("user_id", ""))
    if not user:
        return None
    session["expires_at"] = int(time.time()) + SESSION_SECONDS
    _write(COL_SESSIONS, digest, session)
    return {"id": session["user_id"], "name": user["name"], "email": user["email"]}


def revoke_session(token: str | None):
    if token:
        digest = hashlib.sha256(token.encode()).hexdigest()
        with database() as db:
            db.execute("DELETE FROM docs WHERE col=? AND id=?", (COL_SESSIONS, digest))


def save_turn(user_id: str, conversation_id: str, user_message: str, assistant_message: str):
    conversation_id = re.sub(r"[^a-zA-Z0-9_-]", "", conversation_id or "")[:80] or uuid.uuid4().hex
    key = _doc_id(user_id, conversation_id)
    current = _read(COL_CONVERSATIONS, key) or {"messages": [], "created_at": _now()}
    messages = current.get("messages", [])
    user_text = str(user_message)[:4000]
    assistant_text = str(assistant_message)[:6000]
    if SECRET_PATTERN.search(user_text):
        user_text = "[redacted: credential-like content was not retained]"
    if SECRET_PATTERN.search(assistant_text):
        assistant_text = "[redacted: credential-like content was not retained]"
    messages.extend([
        {"role": "user", "content": user_text, "at": _now()},
        {"role": "assistant", "content": assistant_text, "at": _now()},
    ])
    current.update({"messages": messages[-100:], "updated_at": _now()})
    _write(COL_CONVERSATIONS, key, current)
    extract_durable_memory(user_id, user_message, conversation_id)
    return conversation_id


def extract_durable_memory(user_id: str, text: str, conversation_id: str):
    clean = str(text or "").strip()[:2000]
    if not clean or SECRET_PATTERN.search(clean):
        return
    # Save only explicitly durable user statements, not every chat sentence.
    patterns = (
        (r"^(?:please )?remember (?:that )?(.+)$", "user_note"),
        (r"^(?:we decided|the decision is|our decision is) (?:that )?(.+)$", "decision"),
        (r"^(?:my project is|this project is) (.+)$", "project"),
        (r"^(?:my preference is|i prefer) (.+)$", "preference"),
    )
    lower = clean.lower()
    for pattern, kind in patterns:
        match = re.match(pattern, lower, re.I)
        if not match:
            continue
        value = match.group(1).strip()[:1000]
        existing = _list(COL_MEMORIES, user_id, 200)
        if any(m.get("content", "").lower() == value.lower() and not m.get("superseded_by") for m in existing):
            return
        item_id = uuid.uuid4().hex
        if kind == "decision":
            new_terms = set(WORD_PATTERN.findall(value.lower()))
            for previous in existing:
                if previous.get("kind") != "decision" or previous.get("superseded_by"):
                    continue
                old_terms = set(WORD_PATTERN.findall(previous.get("content", "").lower()))
                if len(new_terms & old_terms) >= 2:
                    previous["superseded_by"] = item_id
                    previous["updated_at"] = _now()
                    _write(COL_MEMORIES, _doc_id(user_id, previous["id"]), {
                        k: v for k, v in previous.items() if k not in ("id", "updated_at")
                    })
        _write(COL_MEMORIES, _doc_id(user_id, item_id), {
            "kind": kind, "content": value, "source_conversation": conversation_id,
            "created_at": _now(), "updated_at": _now(), "superseded_by": None,
        })
        return


def upsert_task(user_id: str, data: dict) -> dict:
    title = str(data.get("title", "")).strip()[:180]
    if not title:
        raise MemoryError("A task title is required.")
    if SECRET_PATTERN.search(title) or SECRET_PATTERN.search(str(data.get("description", ""))):
        raise MemoryError("Task content appears to contain a secret and was not saved.")
    task_id = str(data.get("id") or uuid.uuid4().hex)[:80]
    allowed = {"not_started", "in_progress", "waiting", "blocked", "completed", "cancelled"}
    status = str(data.get("status", "not_started"))
    if status not in allowed:
        raise MemoryError("Invalid task status.")
    old = _read(COL_TASKS, _doc_id(user_id, task_id)) or {}
    item = {**old, "title": title, "description": str(data.get("description", old.get("description", "")))[:4000],
            "project": str(data.get("project", old.get("project", "")))[:180],
            "status": status, "priority": str(data.get("priority", old.get("priority", "normal")))[:20],
            "due_at": data.get("due_at", old.get("due_at")), "timezone": str(data.get("timezone", old.get("timezone", "Africa/Blantyre"))),
            "next_action": str(data.get("next_action", old.get("next_action", "")))[:1000],
            "related_conversation": str(data.get("related_conversation", old.get("related_conversation", "")))[:80],
            "dependencies": data.get("dependencies", old.get("dependencies", []))[:20],
            "decisions": data.get("decisions", old.get("decisions", []))[:20],
            "created_at": old.get("created_at", _now()), "updated_at": _now(),
            "history": (old.get("history", []) + [{"status": status, "at": _now()}])[-50:]}
    _write(COL_TASKS, _doc_id(user_id, task_id), item)
    return {"id": task_id, **item}


def create_reminder(user_id: str, data: dict) -> dict:
    message = str(data.get("message", "")).strip()[:500]
    when = data.get("scheduled_at")
    if not message or not isinstance(when, int) or when <= int(time.time()):
        raise MemoryError("A reminder needs a message and a future scheduled_at timestamp in seconds.")
    if SECRET_PATTERN.search(message):
        raise MemoryError("Reminder text appears to contain a secret and was not saved.")
    timezone = str(data.get("timezone", "Africa/Blantyre"))[:80]
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise MemoryError("The reminder timezone is not recognised.") from exc
    for existing in list_reminders(user_id):
        if (existing.get("message", "").strip().casefold() == message.casefold()
                and int(existing.get("scheduled_at", 0)) == when
                and existing.get("status") in ("scheduled", "due")):
            return existing
    reminder_id = uuid.uuid4().hex
    item = {"message": message, "task_id": str(data.get("task_id", ""))[:80],
            "project": str(data.get("project", ""))[:180], "scheduled_at": when,
            "timezone": timezone, "status": "scheduled", "delivery_method": "in_app",
            "created_at": _now(), "delivered_at": None, "attempts": 0}
    _write(COL_REMINDERS, _doc_id(user_id, reminder_id), item)
    return {"id": reminder_id, **item}


def list_reminders(user_id: str) -> list[dict]:
    now = int(time.time())
    items = _list(COL_REMINDERS, user_id, 200)
    for item in items:
        if item.get("status") == "scheduled" and int(item.get("scheduled_at", 0)) <= now:
            item["status"] = "due"
            _write(COL_REMINDERS, _doc_id(user_id, item["id"]), {k:v for k,v in item.items() if k not in ("id","updated_at")})
    return sorted(items, key=lambda x: x.get("scheduled_at", 0))


def retrieve_context(user_id: str, query: str, conversation_id: str = "") -> str:
    terms = set(WORD_PATTERN.findall(str(query or "").lower()))
    blocks = []
    if conversation_id:
        conv = _read(COL_CONVERSATIONS, _doc_id(user_id, conversation_id))
        if conv:
            blocks.append("ACTIVE CONVERSATION HISTORY:\\n" + json.dumps(conv.get("messages", [])[-12:], ensure_ascii=False))
    conversations = _list(COL_CONVERSATIONS, user_id, 20)
    if conversations:
        ranked = []
        for conv in conversations:
            messages = conv.get("messages", [])
            text = " ".join(m.get("content", "") for m in messages[-20:])
            words = set(WORD_PATTERN.findall(text.lower()))
            score = len(terms & words)
            if score:
                ranked.append((score, conv.get("updated_at", 0), messages[-8:]))
        ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
        if ranked:
            blocks.append("RELEVANT PREVIOUS CONVERSATIONS:\\n" + json.dumps([x[2] for x in ranked[:2]], ensure_ascii=False))
    memories = _list(COL_MEMORIES, user_id, 100)
    relevant_memories = []
    for item in memories:
        if item.get("superseded_by"):
            continue
        score = len(terms & set(WORD_PATTERN.findall(item.get("content", "").lower())))
        if score or item.get("kind") in ("preference", "project"):
            relevant_memories.append((score, item.get("updated_at", 0), item))
    relevant_memories.sort(key=lambda x: (x[0], x[1]), reverse=True)
    if relevant_memories:
        blocks.append("PERSISTENT USER MEMORIES:\\n" + json.dumps([x[2] for x in relevant_memories[:8]], ensure_ascii=False))
    tasks = _list(COL_TASKS, user_id, 100)
    task_matches = []
    for task in tasks:
        score = len(terms & set(WORD_PATTERN.findall((task.get("title", "") + " " + task.get("description", "") + " " + task.get("project", "")).lower())))
        if score or task.get("status") in ("in_progress", "waiting", "blocked"):
            task_matches.append((score, task.get("updated_at", 0), task))
    task_matches.sort(key=lambda x: (x[0], x[1]), reverse=True)
    if task_matches:
        blocks.append("PROJECT AND TASK STATE:\\n" + json.dumps([x[2] for x in task_matches[:8]], ensure_ascii=False))
    reminders = [r for r in list_reminders(user_id) if r.get("status") in ("scheduled", "due")]
    if reminders:
        blocks.append("UPCOMING OR DUE REMINDERS:\\n" + json.dumps(reminders[:8], ensure_ascii=False))
    return "\\n\\n".join(blocks)[:14000] if blocks else "No relevant saved user memory or task history was found."

def list_memories(user_id: str) -> list[dict]:
    return _list(COL_MEMORIES, user_id, 200)


def save_memory(user_id: str, data: dict) -> dict:
    content = str(data.get("content", "")).strip()[:1500]
    if not content or SECRET_PATTERN.search(content):
        raise MemoryError("Memory text is empty or appears to contain a secret.")
    memory_id = str(data.get("id") or uuid.uuid4().hex)[:80]
    old = _read(COL_MEMORIES, _doc_id(user_id, memory_id)) or {}
    item = {**old, "kind": str(data.get("kind", old.get("kind", "user_note")))[:40],
            "content": content, "project": str(data.get("project", old.get("project", "")))[:180],
            "updated_at": _now(), "created_at": old.get("created_at", _now()),
            "superseded_by": data.get("superseded_by", old.get("superseded_by"))}
    _write(COL_MEMORIES, _doc_id(user_id, memory_id), item)
    return {"id": memory_id, **item}


def delete_memory(user_id: str, memory_id: str) -> bool:
    return _delete(COL_MEMORIES, user_id, memory_id)


def list_tasks(user_id: str) -> list[dict]:
    return _list(COL_TASKS, user_id, 200)


def list_conversations(user_id: str) -> list[dict]:
    return _list(COL_CONVERSATIONS, user_id, 100)


def tick_reminders():
    """Move scheduled in-app reminders to due; no external delivery is claimed."""
    now = int(time.time())
    with database() as db:
        rows = db.execute("SELECT id,data FROM docs WHERE col=?", (COL_REMINDERS,)).fetchall()
        for row in rows:
            try:
                item = json.loads(row["data"])
            except (TypeError, json.JSONDecodeError):
                continue
            if item.get("status") == "scheduled" and int(item.get("scheduled_at", 0)) <= now:
                item["status"] = "due"
                item["due_marked_at"] = _now()
                db.execute("UPDATE docs SET data=?,updated_at=? WHERE col=? AND id=?",
                           (json.dumps(item, ensure_ascii=False), _now(), COL_REMINDERS, row["id"]))
