"""EXAMS append-only, hash-chained audit ledger.

Events are written to the dedicated `exams_audit_ledger` table, never to a
mutable docs record. SQLite triggers abort UPDATE/DELETE attempts, and every
event links to the previous event hash so local deployments can verify that the
ledger has not been rewritten. Critical exam flows pass the active transaction
connection so session/submission/audit writes commit atomically.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from app.database.connection import database

EXAMS_AUDIT_COLLECTION = "exams_audit_events"
LEDGER_TABLE = "exams_audit_ledger"

_HASH_FIELDS = (
    "event_id", "at", "actor_id", "actor_label", "mnh_role", "exam_role",
    "action", "entity_type", "entity_id", "exam_id", "session_id",
    "submission_id", "request_id", "client_id", "summary", "before_summary",
    "after_summary", "payload", "prev_hash",
)
# event_hash is stored alongside the hashed fields but never fed back into the hash.
_STORED_FIELDS = (*_HASH_FIELDS, "event_hash")


def _text(value: Any, limit: int = 500) -> str:
    return str(value or "")[:limit]


def _canonical_hash(values: dict[str, Any]) -> str:
    material = json.dumps(
        {key: values.get(key, "") for key in _HASH_FIELDS},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def emit_event(
    *,
    actor: dict[str, Any],
    action: str,
    entity_type: str,
    entity_id: str = "",
    summary: str = "",
    details: dict[str, Any] | None = None,
    exam_id: str = "",
    session_id: str = "",
    submission_id: str = "",
    request_id: str = "",
    client_id: str = "",
    before_summary: str = "",
    after_summary: str = "",
    conn: Any | None = None,
) -> dict[str, Any]:
    """Append one audit event. If conn is supplied the write joins that transaction."""
    now = int(time.time() * 1000)
    event = {
        "event_id": f"exaevt_{uuid.uuid4().hex[:20]}",
        "at": now,
        "actor_id": _text(actor.get("actor_id") or "public", 160),
        "actor_label": _text(actor.get("actor_label") or "public", 160),
        "mnh_role": _text(actor.get("mnh_role") or "public", 80),
        "exam_role": _text(actor.get("exam_role") or "guest", 80),
        "action": _text(action, 120),
        "entity_type": _text(entity_type, 80),
        "entity_id": _text(entity_id, 160),
        "exam_id": _text(exam_id, 160),
        "session_id": _text(session_id, 160),
        "submission_id": _text(submission_id, 160),
        "request_id": _text(request_id or uuid.uuid4().hex, 120),
        "client_id": _text(client_id, 160),
        "summary": _text(summary, 500),
        "before_summary": _text(before_summary, 500),
        "after_summary": _text(after_summary, 500),
        "payload": json.dumps(details or {}, ensure_ascii=False, sort_keys=True, default=str)[:20000],
    }

    def write(connection: Any) -> dict[str, Any]:
        last = connection.execute(
            f"SELECT event_hash FROM {LEDGER_TABLE} ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev = str(last["event_hash"] if last and "event_hash" in last.keys() else "")
        event["prev_hash"] = prev
        event["event_hash"] = _canonical_hash(event)
        connection.execute(
            f"""INSERT INTO {LEDGER_TABLE}(
                event_id,at,actor_id,actor_label,mnh_role,exam_role,action,
                entity_type,entity_id,exam_id,session_id,submission_id,request_id,
                client_id,summary,before_summary,after_summary,payload,prev_hash,event_hash
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            tuple(event[key] for key in _STORED_FIELDS),
        )
        return dict(event)

    if conn is not None:
        return write(conn)
    with database() as connection:
        return write(connection)


def _row_to_event(row: Any) -> dict[str, Any]:
    item = {key: row[key] for key in ("seq", *_STORED_FIELDS)}
    try:
        item["details"] = json.loads(item.get("payload") or "{}")
    except Exception:
        item["details"] = {}
    return item


def list_events(limit: int = 200, *, action: str = "", actor_id: str = "") -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 200), 2000))
    clauses = []
    params: list[Any] = []
    if action:
        clauses.append("action=?")
        params.append(action)
    if actor_id:
        clauses.append("actor_id=?")
        params.append(actor_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with database() as connection:
        rows = connection.execute(
            f"SELECT seq,{','.join(_STORED_FIELDS)} FROM {LEDGER_TABLE}{where} ORDER BY seq DESC LIMIT ?",
            tuple([*params, limit]),
        ).fetchall()
    return [_row_to_event(row) for row in rows]


def verify_chain() -> dict[str, Any]:
    """Verify every link in the audit hash chain."""
    with database() as connection:
        rows = connection.execute(
            f"SELECT seq,{','.join(_STORED_FIELDS)} FROM {LEDGER_TABLE} ORDER BY seq ASC"
        ).fetchall()
    previous = ""
    checked = 0
    for row in rows:
        item = _row_to_event(row)
        expected_prev = str(item.get("prev_hash") or "")
        if expected_prev != previous:
            return {"ok": False, "verified": checked, "total": len(rows), "broken_at_seq": item.get("seq")}
        if _canonical_hash(item) != str(item.get("event_hash") or ""):
            return {"ok": False, "verified": checked, "total": len(rows), "broken_at_seq": item.get("seq")}
        previous = str(item.get("event_hash") or "")
        checked += 1
    return {"ok": True, "verified": checked, "total": len(rows), "broken_at_seq": None}
