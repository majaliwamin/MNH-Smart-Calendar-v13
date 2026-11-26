"""Storage helpers for EXAMS namespaced collections.

EXAMS data is stored in the existing docs table but under `exams_*` collections,
separate from the legacy calendar `examinations` collection.

Critical flows (start/autosave/submit/grade/invigilation actions) use
`exam_transaction()` below. It takes the shared database write lock and opens an
explicit SQLite IMMEDIATE transaction, so the session, submission and audit
ledger writes commit together or roll back together. Optimistic CAS on
`updated_at` remains in place for clients that send a stale revision.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from app.database.connection import database

COL_EXAMS = "exams_exams"
COL_QUESTIONS = "exams_questions"
COL_SESSIONS = "exams_sessions"
COL_SUBMISSIONS = "exams_submissions"
COL_AUDIT = "exams_audit_events"
COL_ENROLLMENTS = "exams_enrollments"
COL_IDENTITIES = "exams_identities"

EXAMS_COLLECTIONS = {
    COL_EXAMS,
    COL_QUESTIONS,
    COL_SESSIONS,
    COL_SUBMISSIONS,
    COL_AUDIT,
    COL_ENROLLMENTS,
    COL_IDENTITIES,
}


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def _decode(row: Any) -> dict[str, Any] | None:
    try:
        data = json.loads(row["data"])
    except Exception:
        data = {"_raw": str(row["data"])}
    if not isinstance(data, dict):
        data = {"value": data}
    data.setdefault("id", row["id"])
    data.setdefault("updated_at", row["updated_at"])
    return data


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
    return _decode(row) if row else None


def list_docs(collection: str, limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 100), 5000))
    with database() as connection:
        rows = connection.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? ORDER BY updated_at DESC, id DESC LIMIT ?",
            (collection, limit),
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = _decode(row)
        if item:
            items.append(item)
    return items


def upsert_doc(collection: str, doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
    with exam_transaction() as tx:
        return tx.upsert(collection, doc_id, data)


def update_doc_if_updated_at(
    collection: str, doc_id: str, expected_updated_at: int, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Optimistic concurrency: update only when updated_at matches."""
    with exam_transaction() as tx:
        return tx.update_if(collection, doc_id, expected_updated_at, data)


def create_doc_if_absent(collection: str, doc_id: str, data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Insert doc only if absent. Returns (doc, created)."""
    with exam_transaction() as tx:
        return tx.create_if_absent(collection, doc_id, data)


def delete_doc(collection: str, doc_id: str) -> bool:
    with exam_transaction() as tx:
        return tx.delete(collection, doc_id)


class ExamTransaction:
    """Connection-scoped EXAMS helpers. Never share this object across threads."""

    def __init__(self, connection: Any):
        self.connection = connection

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? AND id=?",
            (collection, doc_id),
        ).fetchone()
        return _decode(row) if row else None

    def list(self, collection: str, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 100), 5000))
        rows = self.connection.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? ORDER BY updated_at DESC, id DESC LIMIT ?",
            (collection, limit),
        ).fetchall()
        out = []
        for row in rows:
            item = _decode(row)
            if item:
                out.append(item)
        return out

    def count(self, collection: str) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS c FROM docs WHERE col=?", (collection,)
        ).fetchone()
        return int(row["c"] if row else 0)

    def upsert(self, collection: str, doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
        stamp = now_ms()
        payload = dict(data)
        payload["id"] = doc_id
        payload["updated_at"] = stamp
        payload.setdefault("created_at", stamp)
        self.connection.execute(
            "INSERT INTO docs(col,id,data,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(col,id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
            (collection, doc_id, json.dumps(payload, ensure_ascii=False), stamp),
        )
        return payload

    def update_if(
        self, collection: str, doc_id: str, expected_updated_at: int, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        stamp = now_ms()
        payload = dict(data)
        payload["id"] = doc_id
        payload["updated_at"] = stamp
        payload.setdefault("created_at", stamp)
        cur = self.connection.execute(
            "UPDATE docs SET data=?, updated_at=? WHERE col=? AND id=? AND updated_at=?",
            (
                json.dumps(payload, ensure_ascii=False),
                stamp,
                collection,
                doc_id,
                int(expected_updated_at),
            ),
        )
        if not getattr(cur, "rowcount", 0):
            return None
        return payload

    def create_if_absent(
        self, collection: str, doc_id: str, data: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]:
        stamp = now_ms()
        payload = dict(data)
        payload["id"] = doc_id
        payload["updated_at"] = stamp
        payload.setdefault("created_at", stamp)
        cur = self.connection.execute(
            "INSERT INTO docs(col,id,data,updated_at) VALUES(?,?,?,?) ON CONFLICT(col,id) DO NOTHING",
            (collection, doc_id, json.dumps(payload, ensure_ascii=False), stamp),
        )
        created = bool(getattr(cur, "rowcount", 0))
        if created:
            return payload, True
        return (self.get(collection, doc_id) or payload), False

    def delete(self, collection: str, doc_id: str) -> bool:
        cur = self.connection.execute(
            "DELETE FROM docs WHERE col=? AND id=?", (collection, doc_id)
        )
        return bool(getattr(cur, "rowcount", 0))

    def find_sessions(self, actor_id: str, exam_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? ORDER BY updated_at DESC LIMIT 5000",
            (COL_SESSIONS,),
        ).fetchall()
        out = []
        for row in rows:
            item = _decode(row)
            if not item:
                continue
            if str(item.get("actor_id") or "") == str(actor_id) and str(item.get("exam_id") or "") == str(exam_id):
                out.append(item)
        return out

    def find_enrollment(
        self, exam_id: str, actor_id: str, *, actor_aliases: list[str] | None = None
    ) -> dict[str, Any] | None:
        candidates = {str(actor_id or "")}
        for alias in (actor_aliases or []):
            if alias:
                candidates.add(str(alias))
        rows = self.connection.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? ORDER BY updated_at DESC LIMIT 5000",
            (COL_ENROLLMENTS,),
        ).fetchall()
        for row in rows:
            item = _decode(row)
            if not item:
                continue
            if str(item.get("exam_id") or "") == str(exam_id) and str(item.get("actor_id") or "") in candidates:
                return item
        return None


@contextmanager
def exam_transaction() -> Iterator[ExamTransaction]:
    """Atomically write exam session/submission/audit state.

    SQLite: serialises writers with the shared DB_LOCK and starts BEGIN IMMEDIATE
    so a read-modify-write cycle cannot be interleaved by another worker thread
    or process. PostgreSQL: the connection's normal transaction plus the CAS
    UPDATE provides the same deterministic conflict behaviour.
    """
    with database() as connection:
        if isinstance(connection, sqlite3.Connection) and not connection.in_transaction:
            connection.execute("BEGIN IMMEDIATE")
        yield ExamTransaction(connection)


def find_sessions(actor_id: str, exam_id: str) -> list[dict[str, Any]]:
    with exam_transaction() as tx:
        return tx.find_sessions(actor_id, exam_id)


def find_enrollment(
    exam_id: str, actor_id: str, *, actor_aliases: list[str] | None = None
) -> dict[str, Any] | None:
    with exam_transaction() as tx:
        return tx.find_enrollment(exam_id, actor_id, actor_aliases=actor_aliases)
