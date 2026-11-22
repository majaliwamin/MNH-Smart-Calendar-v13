"""Durable correction memory built on the existing shared ``docs`` table.

Only corrections that pass the independent verifier are promoted to learning
examples. Unverified feedback is still retained for audit and recurrence
tracking, but it never becomes training or prompt data.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ai_intelligence import verification
from app.ai_intelligence.retrieval import retrieve_authoritative_context
from app.class_rep.memory import SECRET_PATTERN
from app.config import TIMEZONE
from app.database.connection import database

COL_FEEDBACK = "ai_feedback"
COL_EXAMPLES = "ai_learning_examples"

CATEGORIES = (
    "missed_sessions",
    "duplicate_sessions",
    "incorrect_date_interpretation",
    "incorrect_session_time",
    "fabricated_timetable_information",
    "incorrect_module_identification",
    "unsupported_verification_claim",
    "incomplete_answer",
    "retrieval_failure",
    "other",
)
_REDACTED = "[redacted: credential-like content was not retained]"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _stamp() -> str:
    return datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")


def _clean(value, limit: int) -> str:
    text = str(value or "").strip()[:limit]
    return _REDACTED if SECRET_PATTERN.search(text) else text


def _normal(value) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _read_all(collection: str, limit: int = 500) -> list[dict]:
    with database() as db:
        rows = db.execute(
            "SELECT id,data,updated_at FROM docs WHERE col=? ORDER BY updated_at DESC LIMIT ?",
            (collection, max(1, min(int(limit), 500))),
        ).fetchall()
    result = []
    for row in rows:
        try:
            item = json.loads(row["data"])
            if isinstance(item, dict):
                item["id"] = str(row["id"])
                item["updated_at"] = row["updated_at"]
                result.append(item)
        except (TypeError, json.JSONDecodeError):
            continue
    return result


def _write(collection: str, item_id: str, value: dict, insert_only: bool = False) -> bool:
    payload = {key: item for key, item in value.items() if key not in ("id", "updated_at")}
    with database() as db:
        verb = "INSERT OR IGNORE" if insert_only else "INSERT OR REPLACE"
        cursor = db.execute(
            f"{verb} INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (collection, item_id, json.dumps(payload, ensure_ascii=False), _now_ms()),
        )
    return cursor.rowcount > 0


def _read(collection: str, item_id: str) -> dict | None:
    with database() as db:
        row = db.execute("SELECT data FROM docs WHERE col=? AND id=?", (collection, item_id)).fetchone()
    if not row:
        return None
    try:
        value = json.loads(row["data"])
        return value if isinstance(value, dict) else None
    except (TypeError, json.JSONDecodeError):
        return None


def _bounded_facts(value, limit: int = 40) -> list[dict]:
    if not isinstance(value, list):
        return []
    facts = []
    for item in value[:limit]:
        if not isinstance(item, dict):
            continue
        facts.append({str(key)[:60]: _clean(val, 500) if not isinstance(val, (int, float, bool)) else val
                      for key, val in list(item.items())[:12]})
    return facts


def _authoritative_facts(ctx, query: str) -> dict:
    """Derive an auditable fact snapshot from the same records used for grading."""
    if not ctx.ok:
        return {"retrieval_ok": False, "sessions": [], "examinations": [], "recurring": []}
    focus = verification._focus_sessions(ctx)
    return {
        "retrieval_ok": True,
        "generated_at": ctx.generated_at,
        "filters": ctx.filters,
        "sessions": [
            {
                "date": item["date"], "weekday": item["weekday"],
                "start": item["start"], "end": item["end"],
                "code": item["code"], "title": item["title"],
                "facilitator": item["facilitator"],
            }
            for item in focus[:20]
        ],
        "examinations": [
            {key: exam.get(key, "") for key in ("title", "date", "time", "venue")}
            for exam in ctx.examinations[:10]
        ],
        "recurring": [
            {key: item.get(key, "") for key in ("title", "day", "time", "venue")}
            for item in ctx.recurring[:10]
        ],
        "query": str(query or "")[:500],
    }


def _category(category, verification_result) -> str:
    wanted = str(category or "").strip().casefold().replace(" ", "_")
    if wanted in CATEGORIES:
        return wanted
    for candidate in verification_result.categories:
        if candidate in CATEGORIES:
            return candidate
    return "other"


def _recurrence_count(category: str, entity: str) -> int:
    needle = _normal(entity)
    count = 0
    for item in _read_all(COL_FEEDBACK, 500):
        if str(item.get("category", "")) != category:
            continue
        if needle and _normal(item.get("date_or_entity", "")) != needle:
            continue
        count += 1
    return count


def submit_feedback(
    query: str,
    original_response: str,
    correction: str,
    user_id: str,
    category: str | None = None,
    date_or_entity: str | None = None,
    verified_facts=None,
    conversation_id: str | None = None,
    response_language: str = "EN",
) -> dict:
    """Store one correction and promote it to an example only when verified."""
    question = _clean(query, 4000)
    wrong = _clean(original_response, 6000)
    right = _clean(correction, 6000)
    if not question or not right:
        raise ValueError("A question and a corrected response are required.")

    ctx = retrieve_authoritative_context(question)
    result = verification.verify(right, question, ctx)
    chosen_category = _category(category, result)
    entity = _clean(date_or_entity, 200) or _normal(question)[:200]
    facts = _authoritative_facts(ctx, question)
    digest = hashlib.sha256(
        "\x1f".join([_normal(user_id), _normal(question), _normal(wrong), _normal(right)]).encode("utf-8")
    ).hexdigest()

    existing = _read(COL_FEEDBACK, digest)
    if existing:
        existing["submission_count"] = int(existing.get("submission_count", 1)) + 1
        existing["last_seen_at"] = _stamp()
        existing["updated_at"] = _now_ms()
        _write(COL_FEEDBACK, digest, existing)
        return {
            "id": digest,
            "duplicate": True,
            "submission_count": existing["submission_count"],
            "verification_status": existing.get("verification_status"),
            "learning_status": existing.get("learning_status"),
            "recurring": bool(existing.get("recurring")),
            "category": existing.get("category"),
        }

    recurrence = _recurrence_count(chosen_category, entity) + 1
    record = {
        "query": question,
        "original_response": wrong,
        "correction": right,
        "submitted_facts": _bounded_facts(verified_facts),
        "verified_facts": facts,
        "category": chosen_category,
        "date_or_entity": entity,
        "response_language": str(response_language or "EN")[:5],
        "conversation_id": re.sub(r"[^a-zA-Z0-9_-]", "", str(conversation_id or ""))[:80],
        "verification_status": "verified" if result.ok else "unverified",
        "learning_status": "accepted" if result.ok else "rejected_unverified",
        "verification_reasons": result.reasons[:12],
        "verification_categories": result.categories[:12],
        "retrieval_ok": bool(ctx.ok),
        "provider": result.provider[:80],
        "model": result.model[:80],
        "user_id": str(user_id or "anonymous")[:120],
        "created_at": _stamp(),
        "updated_at": _now_ms(),
        "last_seen_at": _stamp(),
        "submission_count": 1,
        "recurrence_count": recurrence,
        "recurring": recurrence >= 3,
    }
    _write(COL_FEEDBACK, digest, record, insert_only=True)

    if result.ok:
        example = {
            "question": question,
            "context": ctx.to_prompt_context()[:5000],
            "incorrect_behaviour": (chosen_category + ": " + wrong)[:1000],
            "expected_response": right,
            "category": chosen_category,
            "verification_status": "verified",
            "date_or_entity": entity,
            "verified_facts": facts,
            "source_feedback_id": digest,
            "created_at": _stamp(),
        }
        # Same digest keeps the example and feedback linked and prevents a
        # repeated report from creating a duplicate training record.
        _write(COL_EXAMPLES, digest, example, insert_only=True)

    return {
        "id": digest,
        "duplicate": False,
        "verification_status": record["verification_status"],
        "learning_status": record["learning_status"],
        "recurring": record["recurring"],
        "recurrence_count": recurrence,
        "category": chosen_category,
        "verification_reasons": record["verification_reasons"],
    }


def stats() -> dict:
    feedback = _read_all(COL_FEEDBACK, 500)
    examples = _read_all(COL_EXAMPLES, 500)
    categories = Counter(str(item.get("category", "other")) for item in feedback)
    return {
        "feedback_total": len(feedback),
        "verified_corrections": sum(1 for item in feedback if item.get("verification_status") == "verified"),
        "learning_examples": len(examples),
        "recurring_corrections": sum(1 for item in feedback if item.get("recurring")),
        "categories": dict(categories.most_common(12)),
    }
