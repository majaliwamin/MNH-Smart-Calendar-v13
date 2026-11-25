"""Storage helpers for EXAMS namespaced collections.

EXAMS data is stored in the existing docs table but under `exams_*` collections,
separate from the legacy calendar `examinations` collection.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from app.database.connection import database

COL_EXAMS = "exams_exams"
COL_QUESTIONS = "exams_questions"
COL_SESSIONS = "exams_sessions"
COL_SUBMISSIONS = "exams_submissions"
COL_AUDIT = "exams_audit_events"
COL_ENROLLMENTS = "exams_enrollments"

EXAMS_COLLECTIONS = {
    COL_EXAMS,
    COL_QUESTIONS,
    COL_SESSIONS,
    COL_SUBMISSIONS,
    COL_AUDIT,
    COL_ENROLLMENTS,
}


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def count_docs(collection: str) -> int:
    with database() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS c FROM docs WHERE col=?",
            (collection,),
        ).fetchone()
    return int(row["c"] if row else 0)


def get_doc(collection: str, doc_id: str) -> dict[str, Any] | None:
    with database() as connection:
        row = connection.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? AND id=?",
            (collection, doc_id),
        ).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["data"])
    except Exception:
        data = {"_raw": str(row["data"])}
    if not isinstance(data, dict):
        data = {"value": data}
    data.setdefault("id", row["id"])
    data.setdefault("updated_at", row["updated_at"])
    return data


def list_docs(collection: str, limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 100), 500))
    with database() as connection:
        rows = connection.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? ORDER BY updated_at DESC, id DESC LIMIT ?",
            (collection, limit),
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        try:
            data = json.loads(row["data"])
        except Exception:
            data = {"_raw": str(row["data"])}
        if isinstance(data, dict):
            data.setdefault("id", row["id"])
            data.setdefault("updated_at", row["updated_at"])
            items.append(data)
    return items


def upsert_doc(collection: str, doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
    now = now_ms()
    payload = dict(data)
    payload["id"] = doc_id
    payload["updated_at"] = now
    payload.setdefault("created_at", now)
    with database() as connection:
        connection.execute(
            "INSERT INTO docs(col,id,data,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(col,id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
            (collection, doc_id, json.dumps(payload, ensure_ascii=False), now),
        )
    return payload


def update_doc_if_updated_at(collection: str, doc_id: str, expected_updated_at: int, data: dict[str, Any]) -> dict[str, Any] | None:
    """Optimistic concurrency: update only when updated_at matches. Returns new doc or None on conflict."""
    now = now_ms()
    payload = dict(data)
    payload["id"] = doc_id
    payload["updated_at"] = now
    payload.setdefault("created_at", now)
    with database() as connection:
        cur = connection.execute(
            "UPDATE docs SET data=?, updated_at=? WHERE col=? AND id=? AND updated_at=?",
            (json.dumps(payload, ensure_ascii=False), now, collection, doc_id, int(expected_updated_at)),
        )
        if not getattr(cur, "rowcount", 0):
            return None
    return payload


def create_doc_if_absent(collection: str, doc_id: str, data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Insert doc only if absent. Returns (doc, created)."""
    now = now_ms()
    payload = dict(data)
    payload["id"] = doc_id
    payload["updated_at"] = now
    payload.setdefault("created_at", now)
    with database() as connection:
        cur = connection.execute(
            "INSERT INTO docs(col,id,data,updated_at) VALUES(?,?,?,?) ON CONFLICT(col,id) DO NOTHING",
            (collection, doc_id, json.dumps(payload, ensure_ascii=False), now),
        )
        created = bool(getattr(cur, "rowcount", 0))
    if created:
        return payload, True
    existing = get_doc(collection, doc_id)
    return (existing or payload), False


def delete_doc(collection: str, doc_id: str) -> bool:
    with database() as connection:
        cur = connection.execute(
            "DELETE FROM docs WHERE col=? AND id=?",
            (collection, doc_id),
        )
        return bool(getattr(cur, "rowcount", 0))


def find_sessions(actor_id: str, exam_id: str) -> list[dict[str, Any]]:
    with database() as connection:
        rows = connection.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? ORDER BY updated_at DESC LIMIT 1000",
            (COL_SESSIONS,),
        ).fetchall()
    out = []
    for row in rows:
        try:
            data = json.loads(row["data"])
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if str(data.get("actor_id") or "") == str(actor_id) and str(data.get("exam_id") or "") == str(exam_id):
            data.setdefault("id", row["id"])
            data.setdefault("updated_at", row["updated_at"])
            out.append(data)
    return out


def find_enrollment(exam_id: str, actor_id: str, *, actor_aliases: list[str] | None = None) -> dict[str, Any] | None:
    candidates = {str(actor_id or "")}
    for a in (actor_aliases or []):
        if a:
            candidates.add(str(a))
    with database() as connection:
        rows = connection.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? ORDER BY updated_at DESC LIMIT 1000",
            (COL_ENROLLMENTS,),
        ).fetchall()
    for row in rows:
        try:
            data = json.loads(row["data"])
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if str(data.get("exam_id") or "") == str(exam_id) and str(data.get("actor_id") or "") in candidates:
            data.setdefault("id", row["id"])
            data.setdefault("updated_at", row["updated_at"])
            return data
    return None
