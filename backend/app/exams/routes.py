"""FastAPI routes for the EXAMS module.

All state that affects assessment integrity (availability, attempts, timing,
autosave conflicts, submission idempotency, scores, grading and permissions) is
decided here. The browser is treated as an untrusted presentation client.

EXAMS lives only in `exams_*` collections plus the dedicated append-only
`exams_audit_ledger` table. Legacy calendar `examinations` is never touched.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import statistics
import uuid
from typing import Any

from fastapi import APIRouter, Body, Cookie, HTTPException, Response

from app.exams import audit, permissions, store
from app.exams.schemas import (
    EnrollmentUpsert,
    ExamUpsert,
    ExamsBackupPayload,
    QuestionUpsert,
    SessionAction,
    SessionAutosave,
    SessionEventUpsert,
    SessionStart,
    SessionSubmit,
    SubmissionGrade,
)

router = APIRouter(prefix="/api/exams", tags=["exams"])

MANUAL_TYPES = {"short_text", "essay"}
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
BACKUP_SCHEMA_VERSION = "mnh-exams-backup-v1"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _text(value: Any, limit: int = 4000) -> str:
    return CONTROL_CHARS.sub("", str(value if value is not None else ""))[:limit]


def _actor_aliases(identity: dict[str, Any]) -> list[str]:
    actor_id = str(identity.get("actor_id") or "")
    alias = f"mnh:{str(identity.get('mnh_role') or '').strip().lower()}"
    return [alias] if alias and alias != actor_id else []


def _enrollment(tx: Any, exam_id: str, identity: dict[str, Any]) -> dict[str, Any] | None:
    return tx.find_enrollment(
        exam_id,
        str(identity.get("actor_id") or ""),
        actor_aliases=_actor_aliases(identity),
    )


def _require_exam_capability(
    identity: dict[str, Any], capability: str, enrollment: dict[str, Any] | None
) -> None:
    permissions.require_exam_capability(identity, capability, enrollment)


def _log(
    actor: dict[str, Any],
    action: str,
    entity_type: str,
    entity_id: str = "",
    summary: str = "",
    details: dict[str, Any] | None = None,
    *,
    tx: Any | None = None,
    exam_id: str = "",
    session_id: str = "",
    submission_id: str = "",
    client_id: str = "",
    before_summary: str = "",
    after_summary: str = "",
) -> dict[str, Any]:
    return audit.emit_event(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        details=details or {},
        conn=getattr(tx, "connection", None) if tx is not None else None,
        exam_id=exam_id,
        session_id=session_id,
        submission_id=submission_id,
        client_id=client_id,
        before_summary=before_summary,
        after_summary=after_summary,
    )


def _clean_question(doc: dict[str, Any], *, include_answers: bool) -> dict[str, Any]:
    out = dict(doc)
    if not include_answers:
        for key in ("correct_option_ids", "correct_text", "explanation", "rubric", "grading_guide"):
            out.pop(key, None)
    return out


def _ordered_ids(seed: str, values: list[str]) -> list[str]:
    return sorted(
        values,
        key=lambda value: hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest(),
    )


def _presentation(exam: dict[str, Any], session_id: str, tx: Any | None = None) -> dict[str, Any]:
    """Deterministic per-session order for configured randomization."""
    seed = f"{session_id}:{exam.get('id', '')}"
    links = exam.get("questions") if isinstance(exam.get("questions"), list) else []
    question_ids = [str(link.get("question_id") or "") for link in links if isinstance(link, dict)]
    question_ids = [qid for qid in question_ids if qid]
    if exam.get("shuffle_questions"):
        question_ids = _ordered_ids(seed + ":q", question_ids)
    options: dict[str, list[str]] = {}
    if exam.get("shuffle_options"):
        getter = tx.get if tx is not None else store.get_doc
        for qid in question_ids:
            question = getter(store.COL_QUESTIONS, qid)
            if not question:
                continue
            option_ids = [
                str(option.get("id") or "") for option in (question.get("options") or [])
                if isinstance(option, dict) and option.get("id")
            ]
            options[qid] = _ordered_ids(seed + ":o:" + qid, option_ids)
    return {"question_order": question_ids, "options": options}


def _exam_questions(
    exam: dict[str, Any],
    *,
    include_answers: bool,
    presentation: dict[str, Any] | None = None,
    tx: Any | None = None,
) -> list[dict[str, Any]]:
    links = exam.get("questions") if isinstance(exam.get("questions"), list) else []
    link_map: dict[str, tuple[int, float | None]] = {}
    for index, link in enumerate(links):
        if not isinstance(link, dict):
            continue
        qid = str(link.get("question_id") or "").strip()
        if qid:
            points = link.get("points")
            link_map[qid] = (int(link.get("order") if link.get("order") is not None else index), points)
    ordered = list(link_map)
    if presentation and isinstance(presentation.get("question_order"), list):
        preferred = [str(qid) for qid in presentation["question_order"] if str(qid) in link_map]
        ordered = preferred + [qid for qid in ordered if qid not in preferred]
    else:
        ordered.sort(key=lambda qid: (link_map[qid][0], qid))
    result: list[dict[str, Any]] = []
    getter = tx.get if tx is not None else store.get_doc
    for qid in ordered:
        question = getter(store.COL_QUESTIONS, qid)
        if not question or not question.get("active", True):
            continue
        question = _clean_question(question, include_answers=include_answers)
        question["link_order"] = link_map[qid][0]
        if link_map[qid][1] is not None:
            try:
                question["points"] = float(link_map[qid][1])
            except (TypeError, ValueError):
                pass
        if presentation and isinstance(presentation.get("options"), dict):
            wanted = presentation["options"].get(qid)
            if isinstance(wanted, list) and isinstance(question.get("options"), list):
                by_id = {str(option.get("id")): option for option in question["options"] if isinstance(option, dict)}
                question["options"] = [by_id[oid] for oid in wanted if oid in by_id]
        result.append(question)
    return result


def _sanitise_answers(
    exam: dict[str, Any], answers: dict[str, Any], tx: Any | None = None
) -> dict[str, Any]:
    """Keep only exam questions and valid option IDs; never trust client keys."""
    allowed: dict[str, dict[str, Any]] = {}
    for question in _exam_questions(exam, include_answers=True, tx=tx):
        allowed[str(question.get("id") or "")] = question
    clean: dict[str, Any] = {}
    for key, value in (answers or {}).items():
        qid = str(key).strip()
        question = allowed.get(qid)
        if not question:
            continue
        qtype = str(question.get("type") or "mcq")
        option_ids = {str(option.get("id")) for option in (question.get("options") or []) if isinstance(option, dict)}
        if qtype in {"mcq", "true_false"}:
            candidate = str(value)
            if candidate in option_ids:
                clean[qid] = candidate
        elif qtype == "multiple_select":
            values = value if isinstance(value, list) else []
            clean[qid] = [str(item) for item in values if str(item) in option_ids][:200]
        else:
            clean[qid] = _text(value, 4000)
    return clean


def _score_submission(
    exam: dict[str, Any],
    answers: dict[str, Any],
    *,
    overrides: dict[str, dict[str, Any]] | None = None,
    tx: Any | None = None,
) -> dict[str, Any]:
    """Score objective answers; mark short_text/essay as requiring review.

    Existing exact-text matches are retained as provisional auto scores so older
    exams keep behaving, but a grader can override any per-question result.
    """
    overrides = overrides or {}
    total = 0.0
    earned = 0.0
    details: list[dict[str, Any]] = []
    for question in _exam_questions(exam, include_answers=True, tx=tx):
        qid = str(question.get("id") or "")
        points = float(question.get("points") or 0)
        qtype = str(question.get("type") or "mcq")
        answer = answers.get(qid)
        correct = False
        if qtype in {"mcq", "true_false"}:
            correct_ids = {str(item) for item in (question.get("correct_option_ids") or [])}
            correct = bool(correct_ids) and str(answer or "") in correct_ids
        elif qtype == "multiple_select":
            correct_ids = {str(item) for item in (question.get("correct_option_ids") or [])}
            given = {str(item) for item in (answer or [])} if isinstance(answer, list) else set()
            correct = bool(correct_ids) and given == correct_ids
        elif qtype in MANUAL_TYPES:
            expected = str(question.get("correct_text") or "").strip().lower()
            correct = bool(expected) and str(answer or "").strip().lower() == expected
        auto_earned = points if correct else 0.0
        override = overrides.get(qid) or {}
        final_earned = float(override.get("earned_points", auto_earned))
        earned += final_earned
        total += points
        detail = {
            "question_id": qid,
            "type": qtype,
            "correct": correct,
            "points": points,
            "auto_earned_points": auto_earned,
            "earned_points": final_earned,
            "needs_manual": qtype in MANUAL_TYPES and qid not in override,
        }
        if override.get("feedback"):
            detail["feedback"] = _text(override["feedback"], 4000)
        details.append(detail)
    percent = round((earned / total) * 100.0, 2) if total > 0 else 0.0
    return {
        "total_points": total,
        "earned_points": round(earned, 4),
        "percent": percent,
        "details": details,
        "requires_manual": any(item["needs_manual"] for item in details),
    }


def _effective_expiry(session: dict[str, Any], now: int | None = None) -> int:
    now = now if now is not None else store.now_ms()
    pause_ms = int(session.get("pause_total_ms") or 0)
    if session.get("paused_at"):
        pause_ms += max(0, now - int(session["paused_at"]))
    return int(session.get("expires_at") or 0) + int(session.get("extension_ms") or 0) + pause_ms


def _flags(session: dict[str, Any]) -> list[str]:
    flags = [str(item) for item in (session.get("flags") or []) if item]
    for event in (session.get("events") or [])[-50:]:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "")
        if event_type in {"tab_hidden", "focus_lost", "offline", "save_conflict", "late_submit"}:
            flag = f"suspicious:{event_type}"
            if flag not in flags:
                flags.append(flag)
    if int(session.get("conflict_count") or 0) >= 3 and "repeated_save_conflicts" not in flags:
        flags.append("repeated_save_conflicts")
    return flags


def _session_view(session: dict[str, Any], *, include_answers: bool) -> dict[str, Any]:
    out = dict(session)
    if not include_answers:
        out.pop("answers", None)
    out["effective_expires_at"] = _effective_expiry(session)
    out["time_remaining_ms"] = max(0, _effective_expiry(session) - store.now_ms())
    out["flags"] = _flags(session)
    return out


def _results_released(exam: dict[str, Any], submission: dict[str, Any], now: int) -> bool:
    # Legacy exams without a release policy keep their original immediate behavior.
    mode = str(exam.get("results_release") or "immediate")
    if mode == "never":
        return False
    if mode == "immediate":
        return True
    if mode == "on_return":
        return str(submission.get("status") or "") == "returned"
    if mode == "scheduled":
        scheduled = exam.get("results_release_at")
        return bool(scheduled) and now >= int(scheduled)
    return False


def _submission_view(
    submission: dict[str, Any], exam: dict[str, Any], identity: dict[str, Any]
) -> dict[str, Any]:
    out = dict(submission)
    privileged = permissions.has_capability(identity, "exams.manage") or permissions.has_capability(identity, "exams.grade")
    if privileged:
        return out
    if str(out.get("actor_id") or "") != str(identity.get("actor_id") or ""):
        raise HTTPException(403, "Not allowed")
    released = _results_released(exam, out, store.now_ms())
    out["results_released"] = released
    if not released:
        for key in ("answers", "score", "feedback", "question_scores", "graded_by", "graded_at"):
            out.pop(key, None)
    return out


def _snapshot(session: dict[str, Any]) -> str:
    return json.dumps(
        {
            "state": session.get("state"),
            "expires_at": session.get("expires_at"),
            "extension_ms": session.get("extension_ms", 0),
            "paused_at": session.get("paused_at"),
            "flags": _flags(session),
        },
        ensure_ascii=False,
        sort_keys=True,
    )[:500]


def _available(exam: dict[str, Any], now: int) -> tuple[bool, str]:
    start = exam.get("available_from")
    end = exam.get("available_until")
    if start and now < int(start):
        return False, "This exam is not available yet."
    if end and now > int(end):
        return False, "The exam availability window has closed."
    return True, ""


# ---------------------------------------------------------------------------
# Module identity and overview
# ---------------------------------------------------------------------------
@router.get("/health")
def exams_health(mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    return {
        "ok": True,
        "module": "exams",
        "status": "production-foundation",
        "isolated_from_legacy_examinations": True,
        "legacy_examinations_collection": "examinations",
        "collections": {name: store.count_docs(name) for name in sorted(store.EXAMS_COLLECTIONS)},
        "audit_ledger": "exams_audit_ledger",
        "identity": identity,
        "capabilities": sorted(permissions.CAPABILITIES.get(identity["exam_role"], set())),
        "limitations": ["Activity signals are logged; full remote proctoring/lockdown is not implemented."],
    }


@router.get("/capabilities")
def exams_capabilities(mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    caps = sorted(permissions.CAPABILITIES.get(identity["exam_role"], set()))
    return {
        "ok": True,
        "identity": identity,
        "capabilities": caps,
        "can_manage": "exams.manage" in caps,
        "can_take": "exams.take" in caps,
    }


@router.get("/overview")
def exams_overview(mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    counts = {name: store.count_docs(name) for name in sorted(store.EXAMS_COLLECTIONS)}
    exams = store.list_docs(store.COL_EXAMS, limit=5000)
    sessions = store.list_docs(store.COL_SESSIONS, limit=5000)
    submissions = store.list_docs(store.COL_SUBMISSIONS, limit=5000)
    enrollments = store.list_docs(store.COL_ENROLLMENTS, limit=5000)
    by_exam: dict[str, dict[str, Any]] = {}
    for exam in exams:
        eid = str(exam.get("id") or "")
        by_exam[eid] = {
            "exam_id": eid,
            "title": exam.get("title") or eid,
            "status": exam.get("status") or "draft",
            "sessions": 0,
            "submitted": 0,
            "enrolled": 0,
            "avg_percent": None,
        }
    for session in sessions:
        eid = str(session.get("exam_id") or "")
        if eid in by_exam:
            by_exam[eid]["sessions"] += 1
            if str(session.get("state") or "") == "submitted":
                by_exam[eid]["submitted"] += 1
    for enrollment in enrollments:
        eid = str(enrollment.get("exam_id") or "")
        if eid in by_exam and str(enrollment.get("role") or "") == "candidate":
            by_exam[eid]["enrolled"] += 1
    sums: dict[str, float] = {}
    counts_by_exam: dict[str, int] = {}
    for submission in submissions:
        eid = str(submission.get("exam_id") or "")
        value = (submission.get("score") or {}).get("percent")
        try:
            percent = float(value)
        except (TypeError, ValueError):
            continue
        sums[eid] = sums.get(eid, 0.0) + percent
        counts_by_exam[eid] = counts_by_exam.get(eid, 0) + 1
    for eid, row in by_exam.items():
        if counts_by_exam.get(eid):
            row["avg_percent"] = round(sums[eid] / counts_by_exam[eid], 2)
    active_sessions = len([s for s in sessions if str(s.get("state") or "") == "active"])
    _log(
        identity,
        "exams.overview.viewed",
        "exams_module",
        "overview",
        "EXAMS overview viewed",
        {"counts": counts},
    )
    return {
        "ok": True,
        "module": "exams",
        "phase": "production-foundation",
        "counts": counts,
        "collections": sorted(store.EXAMS_COLLECTIONS),
        "summary": {
            "active_sessions": active_sessions,
            "submitted_sessions": len([s for s in sessions if str(s.get("state") or "") == "submitted"]),
            "submissions": len(submissions),
            "enrollments": len(enrollments),
        },
        "by_exam": list(by_exam.values()),
    }


@router.get("/my")
def my_exams(mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    actor_ids = {str(identity.get("actor_id") or ""), *_actor_aliases(identity)}
    sessions = [x for x in store.list_docs(store.COL_SESSIONS, limit=1000) if str(x.get("actor_id") or "") in actor_ids]
    submissions = [x for x in store.list_docs(store.COL_SUBMISSIONS, limit=1000) if str(x.get("actor_id") or "") in actor_ids]
    enrollments = [x for x in store.list_docs(store.COL_ENROLLMENTS, limit=1000) if str(x.get("actor_id") or "") in actor_ids]
    exams = {str(exam.get("id") or ""): exam for exam in store.list_docs(store.COL_EXAMS, limit=5000)}
    public_submissions = []
    for submission in submissions:
        exam = exams.get(str(submission.get("exam_id") or ""), {})
        public_submissions.append(_submission_view(submission, exam, identity))
    return {
        "ok": True,
        "identity": identity,
        "sessions": [_session_view(s, include_answers=False) for s in sessions],
        "submissions": public_submissions,
        "enrollments": enrollments,
    }


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------
def _clean_question_doc(doc: dict[str, Any]) -> dict[str, Any]:
    doc = dict(doc)
    for key in ("prompt", "correct_text", "explanation", "rubric"):
        doc[key] = _text(doc.get(key, ""), 8000 if key == "prompt" else 4000)
    options = doc.get("options") or []
    doc["options"] = [
        {"id": _text(option.get("id"), 40), "text": _text(option.get("text"), 1000)}
        for option in options if isinstance(option, dict)
    ]
    return doc


@router.get("/questions")
def list_questions(limit: int = 100, mnh_session: str | None = Cookie(default=None)):
    permissions.require_capability(mnh_session, "exams.question.manage")
    return {"ok": True, "items": store.list_docs(store.COL_QUESTIONS, limit=limit)}


@router.post("/questions")
def create_question(payload: QuestionUpsert = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.question.manage")
    doc = _clean_question_doc(payload.model_dump())
    doc["created_by"] = identity.get("actor_id")
    item = store.upsert_doc(store.COL_QUESTIONS, store.new_id("q"), doc)
    _log(identity, "exams.question.created", "question", item["id"], "Question created")
    return {"ok": True, "item": item}


@router.put("/questions/{question_id}")
def update_question(question_id: str, payload: QuestionUpsert = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.question.manage")
    existing = store.get_doc(store.COL_QUESTIONS, question_id)
    if not existing:
        raise HTTPException(404, "Question not found")
    before = existing.copy()
    data = existing.copy()
    data.update(_clean_question_doc(payload.model_dump()))
    data["updated_by"] = identity.get("actor_id")
    item = store.upsert_doc(store.COL_QUESTIONS, question_id, data)
    _log(
        identity,
        "exams.question.updated",
        "question",
        question_id,
        "Question updated",
        {"active": item.get("active"), "points": item.get("points")},
        before_summary=f"active={before.get('active')}, points={before.get('points')}",
        after_summary=f"active={item.get('active')}, points={item.get('points')}",
    )
    return {"ok": True, "item": item}


@router.delete("/questions/{question_id}")
def delete_question(question_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.question.manage")
    existing = store.get_doc(store.COL_QUESTIONS, question_id)
    if not existing:
        raise HTTPException(404, "Question not found")
    # Soft delete preserves exam composition and historical submissions.
    data = dict(existing)
    data["active"] = False
    data["deleted_at"] = store.now_ms()
    store.upsert_doc(store.COL_QUESTIONS, question_id, data)
    _log(identity, "exams.question.deactivated", "question", question_id, "Question deactivated")
    return {"ok": True, "deleted": question_id}


# ---------------------------------------------------------------------------
# Enrollments and persistent exam identities
# ---------------------------------------------------------------------------
@router.get("/enrollments")
def list_enrollments(exam_id: str = "", limit: int = 200, mnh_session: str | None = Cookie(default=None)):
    permissions.require_capability(mnh_session, "exams.manage")
    items = store.list_docs(store.COL_ENROLLMENTS, limit=limit)
    if exam_id:
        items = [x for x in items if str(x.get("exam_id") or "") == exam_id]
    return {"ok": True, "items": items}


@router.post("/enrollments")
def upsert_enrollment(payload: EnrollmentUpsert = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.manage")
    with store.exam_transaction() as tx:
        exam = tx.get(store.COL_EXAMS, payload.exam_id)
        if not exam:
            raise HTTPException(404, "Exam not found")
        key = f"enr_{payload.exam_id}_{payload.actor_id}".replace(":", "_")
        doc = {
            "exam_id": payload.exam_id,
            "actor_id": _text(payload.actor_id, 120),
            "role": payload.role,
            "display_name": _text(payload.display_name, 120),
            "mnh_role": _text(payload.mnh_role or identity.get("mnh_role", ""), 80),
            "identity_source": "mnh_session",
            "created_by": identity.get("actor_id"),
        }
        item = tx.upsert(store.COL_ENROLLMENTS, key, doc)
        identity_doc = {
            "actor_id": doc["actor_id"],
            "display_name": doc["display_name"],
            "mnh_role": doc["mnh_role"],
            "exam_role": payload.role,
            "exam_id": payload.exam_id,
        }
        tx.upsert(store.COL_IDENTITIES, f"ident_{payload.exam_id}_{payload.actor_id}".replace(":", "_"), identity_doc)
        _log(
            identity,
            "exams.enrollment.upserted",
            "enrollment",
            item["id"],
            "Enrollment upserted",
            {"exam_id": payload.exam_id, "actor_id": payload.actor_id, "role": payload.role},
            tx=tx,
            exam_id=payload.exam_id,
        )
    return {"ok": True, "item": item}


@router.delete("/enrollments/{enrollment_id}")
def delete_enrollment(enrollment_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.manage")
    with store.exam_transaction() as tx:
        existing = tx.get(store.COL_ENROLLMENTS, enrollment_id)
        if not existing:
            raise HTTPException(404, "Enrollment not found")
        exam_id = str(existing.get("exam_id") or "")
        actor_id = str(existing.get("actor_id") or "")
        affected: list[str] = []
        for session in tx.find_sessions(actor_id, exam_id):
            if str(session.get("state") or "") != "active":
                continue
            flags = _flags(session)
            if "enrollment_revoked" not in flags:
                flags.append("enrollment_revoked")
            session["flags"] = flags
            session["enrollment_revoked_at"] = store.now_ms()
            tx.upsert(store.COL_SESSIONS, str(session["id"]), session)
            affected.append(str(session["id"]))
            _log(
                identity,
                "exams.session.enrollment_revoked",
                "session",
                str(session["id"]),
                "Enrollment removed during an active attempt",
                {"exam_id": exam_id, "actor_id": actor_id},
                tx=tx,
                exam_id=exam_id,
                session_id=str(session["id"]),
            )
        tx.delete(store.COL_ENROLLMENTS, enrollment_id)
        _log(
            identity,
            "exams.enrollment.deleted",
            "enrollment",
            enrollment_id,
            "Enrollment deleted",
            {"exam_id": exam_id, "actor_id": actor_id, "active_sessions_flagged": affected},
            tx=tx,
            exam_id=exam_id,
        )
    return {"ok": True, "deleted": enrollment_id, "active_sessions_flagged": affected}


# ---------------------------------------------------------------------------
# Exam definitions and settings
# ---------------------------------------------------------------------------
def _clean_exam_doc(doc: dict[str, Any]) -> dict[str, Any]:
    doc = dict(doc)
    for key in ("title", "description", "course_code", "instructions"):
        doc[key] = _text(doc.get(key, ""), 200 if key == "title" else 8000)
    return doc


@router.get("/exams")
def list_exams(limit: int = 100, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    items = store.list_docs(store.COL_EXAMS, limit=limit)
    if not permissions.has_capability(identity, "exams.manage"):
        now = store.now_ms()
        items = [
            item for item in items
            if str(item.get("status") or "draft") == "published" and _available(item, now)[0]
        ]
    return {"ok": True, "items": items, "count": len(items)}


@router.post("/exams")
def create_exam(payload: ExamUpsert = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.manage")
    data = _clean_exam_doc(payload.model_dump())
    data["created_by"] = identity.get("actor_id")
    data["created_by_role"] = identity.get("exam_role")
    item = store.upsert_doc(store.COL_EXAMS, store.new_id("exam"), data)
    _log(identity, "exams.exam.created", "exam", item["id"], f"Created exam: {item.get('title', '')}", tx=None, exam_id=item["id"])
    return {"ok": True, "item": item}


@router.get("/exams/{exam_id}")
def get_exam(exam_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    doc = store.get_doc(store.COL_EXAMS, exam_id)
    if not doc:
        raise HTTPException(404, "Exam not found")
    can_manage = permissions.has_capability(identity, "exams.manage")
    if not can_manage and str(doc.get("status") or "") != "published":
        raise HTTPException(404, "Exam not found")
    out = dict(doc)
    out["question_items"] = _exam_questions(doc, include_answers=can_manage)
    out["availability"] = {
        "available": _available(doc, store.now_ms())[0] if not can_manage else True,
        "message": "" if can_manage else _available(doc, store.now_ms())[1],
    }
    return {"ok": True, "item": out}


@router.put("/exams/{exam_id}")
def update_exam(exam_id: str, payload: ExamUpsert = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.manage")
    with store.exam_transaction() as tx:
        existing = tx.get(store.COL_EXAMS, exam_id)
        if not existing:
            raise HTTPException(404, "Exam not found")
        before_status = str(existing.get("status") or "draft")
        data = existing.copy()
        data.update(_clean_exam_doc(payload.model_dump()))
        data["updated_by"] = identity.get("actor_id")
        item = tx.upsert(store.COL_EXAMS, exam_id, data)
        _log(
            identity,
            "exams.exam.updated",
            "exam",
            exam_id,
            f"Updated exam: {item.get('title', '')}",
            {"status": item.get("status"), "before_status": before_status},
            tx=tx,
            exam_id=exam_id,
            before_summary=f"status={before_status}",
            after_summary=f"status={item.get('status')}",
        )
        if before_status != item.get("status"):
            _log(
                identity,
                f"exams.exam.{item.get('status')}",
                "exam",
                exam_id,
                f"Exam status changed to {item.get('status')}",
                tx=tx,
                exam_id=exam_id,
            )
    return {"ok": True, "item": item}


@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.manage")
    with store.exam_transaction() as tx:
        existing = tx.get(store.COL_EXAMS, exam_id)
        if not existing:
            raise HTTPException(404, "Exam not found")
        # Archive instead of erasing history and submissions.
        data = dict(existing)
        data["status"] = "archived"
        data["archived_at"] = store.now_ms()
        item = tx.upsert(store.COL_EXAMS, exam_id, data)
        _log(identity, "exams.exam.archived", "exam", exam_id, f"Archived exam: {existing.get('title', '')}", tx=tx, exam_id=exam_id)
    return {"ok": True, "deleted": exam_id, "item": item}


# ---------------------------------------------------------------------------
# Sessions / attempts
# ---------------------------------------------------------------------------
@router.post("/sessions/start")
def start_session(payload: SessionStart = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    if not identity.get("authenticated"):
        raise HTTPException(401, "Authentication required to start an exam session")
    with store.exam_transaction() as tx:
        exam = tx.get(store.COL_EXAMS, payload.exam_id)
        if not exam or str(exam.get("status") or "") != "published":
            raise HTTPException(404, "Published exam not found")
        now = store.now_ms()
        available, message = _available(exam, now)
        if not available and not permissions.has_capability(identity, "exams.manage"):
            raise HTTPException(403, message or "Exam is not available")
        actor_id = str(identity.get("actor_id") or "")
        aliases = _actor_aliases(identity)
        enrollment = _enrollment(tx, payload.exam_id, identity)
        if bool(exam.get("require_enrollment")) and not permissions.has_capability(identity, "exams.manage"):
            if not enrollment or str(enrollment.get("role") or "") != "candidate":
                raise HTTPException(403, "Enrollment required for this exam")
        sessions = tx.find_sessions(actor_id, payload.exam_id)
        for alias in aliases:
            sessions.extend(tx.find_sessions(alias, payload.exam_id))
        unique = {str(item.get("id")): item for item in sessions if item.get("id")}
        for session in unique.values():
            if str(session.get("state") or "") in {"active", "submitted"}:
                return {"ok": True, "item": _session_view(session, include_answers=True), "resumed": True}
        attempts_used = len([
            item for item in unique.values()
            if str(item.get("state") or "") in {"submitted", "expired", "invalidated"}
        ])
        max_attempts = int(exam.get("max_attempts") or 1)
        if attempts_used >= max_attempts and not permissions.has_capability(identity, "exams.manage"):
            raise HTTPException(403, "Maximum attempts reached")
        session_id = store.new_id("sess")
        duration_ms = int(exam.get("duration_minutes") or 60) * 60 * 1000
        session = {
            "exam_id": payload.exam_id,
            "actor_id": actor_id,
            "actor_role": identity.get("exam_role"),
            "enrollment_role": (enrollment or {}).get("role"),
            "state": "active",
            "started_at": now,
            "expires_at": now + duration_ms,
            "extension_ms": 0,
            "pause_total_ms": 0,
            "paused_at": None,
            "last_saved_at": now,
            "heartbeat_at": now,
            "submitted_at": None,
            "answers": {},
            "save_seq": 0,
            "client_save_ids": [],
            "client_submit_id": "",
            "attempt_no": attempts_used + 1,
            "presentation": _presentation(exam, session_id, tx=tx),
            "events": [],
            "flags": [],
            "conflict_count": 0,
            "notes": [],
        }
        item = tx.upsert(store.COL_SESSIONS, session_id, session)
        _log(
            identity,
            "exams.session.started",
            "session",
            session_id,
            "Exam session started",
            {"exam_id": payload.exam_id, "attempt_no": item["attempt_no"]},
            tx=tx,
            exam_id=payload.exam_id,
            session_id=session_id,
        )
    return {"ok": True, "item": _session_view(item, include_answers=True), "resumed": False}


@router.get("/sessions")
@router.get("/sessions/monitor")
def monitor_sessions(
    limit: int = 200,
    exam_id: str = "",
    state: str = "",
    mnh_session: str | None = Cookie(default=None),
):
    identity = permissions.resolve_identity(mnh_session)
    if not (
        permissions.has_capability(identity, "exams.session.manage")
        or permissions.has_capability(identity, "exams.invigilate")
        or permissions.has_capability(identity, "exams.grade")
    ):
        raise HTTPException(403, "Not allowed")
    items = store.list_docs(store.COL_SESSIONS, limit=limit)
    if exam_id:
        items = [item for item in items if str(item.get("exam_id") or "") == exam_id]
    if state:
        items = [item for item in items if str(item.get("state") or "") == state]
    roster = []
    for item in items:
        view = _session_view(item, include_answers=False)
        view["last_activity_at"] = max(
            int(item.get("heartbeat_at") or 0),
            int(item.get("last_saved_at") or 0),
            int(item.get("updated_at") or 0),
        )
        view["events"] = (item.get("events") or [])[-20:]
        view["notes"] = (item.get("notes") or [])[-20:]
        roster.append(view)
    roster.sort(key=lambda row: int(row.get("last_activity_at") or 0), reverse=True)
    _log(identity, "exams.sessions.monitored", "exams_module", "monitor", "Invigilation roster viewed", {"exam_id": exam_id, "state": state})
    return {
        "ok": True,
        "items": roster,
        "count": len(roster),
        "server_now": store.now_ms(),
        "mode": "activity_signals_only",
        "limitations": ["Browser visibility/focus/offline signals can be spoofed; this is not remote proctoring."],
    }


@router.get("/sessions/{session_id}")
def get_session(session_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    session = store.get_doc(store.COL_SESSIONS, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    owner = str(session.get("actor_id") or "") == str(identity.get("actor_id") or "")
    with store.exam_transaction() as tx:
        enrollment = _enrollment(tx, str(session.get("exam_id") or ""), identity)
    privileged = permissions.has_capability(identity, "exams.session.manage") or permissions.enrollment_allows(enrollment, "exams.invigilate")
    if not owner and not privileged:
        raise HTTPException(403, "Not allowed")
    exam = store.get_doc(store.COL_EXAMS, str(session.get("exam_id") or "")) or {}
    presentation = session.get("presentation") if isinstance(session.get("presentation"), dict) else None
    can_see_answers = permissions.has_capability(identity, "exams.session.manage")
    exam_view = dict(exam)
    exam_view["question_items"] = _exam_questions(exam, include_answers=can_see_answers, presentation=presentation)
    exam_view.pop("questions", None)
    return {
        "ok": True,
        "item": _session_view(session, include_answers=owner),
        "exam": exam_view,
        "server_now": store.now_ms(),
        "mode": "activity_signals_only",
    }


@router.post("/sessions/{session_id}/autosave")
def autosave_session(session_id: str, payload: SessionAutosave = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    with store.exam_transaction() as tx:
        session = tx.get(store.COL_SESSIONS, session_id)
        if not session:
            raise HTTPException(404, "Session not found")
        if str(session.get("actor_id") or "") != str(identity.get("actor_id") or ""):
            raise HTTPException(403, "Not allowed")
        current = int(session.get("updated_at") or 0)
        expected = int(payload.expected_updated_at) if payload.expected_updated_at is not None else current
        if expected != current:
            session["conflict_count"] = int(session.get("conflict_count") or 0) + 1
            flags = _flags(session)
            if session["conflict_count"] >= 3 and "repeated_save_conflicts" not in flags:
                flags.append("repeated_save_conflicts")
            session["flags"] = flags
            tx.upsert(store.COL_SESSIONS, session_id, session)
            _log(
                identity,
                "exams.session.save_conflict",
                "session",
                session_id,
                "Autosave conflict",
                {"expected": expected, "current": current},
                tx=tx,
                exam_id=str(session.get("exam_id") or ""),
                session_id=session_id,
                client_id=payload.client_save_id,
            )
            return {"ok": False, "conflict": True, "item": _session_view(session, include_answers=True), "reason": "stale_session"}
        if str(session.get("state") or "") != "active":
            return {"ok": True, "item": _session_view(session, include_answers=True), "ignored": True, "reason": "session_not_active"}
        now = store.now_ms()
        if session.get("paused_at"):
            return {"ok": True, "item": _session_view(session, include_answers=True), "ignored": True, "reason": "session_paused"}
        if now > _effective_expiry(session, now):
            session["state"] = "expired"
            session["expired_at"] = now
            tx.upsert(store.COL_SESSIONS, session_id, session)
            _log(identity, "exams.session.expired", "session", session_id, "Session expired", tx=tx, session_id=session_id)
            return {"ok": True, "item": _session_view(session, include_answers=True), "expired": True}
        seen = {str(item) for item in (session.get("client_save_ids") or [])}
        if payload.client_save_id and payload.client_save_id in seen:
            return {"ok": True, "item": _session_view(session, include_answers=True), "duplicate": True}
        exam = tx.get(store.COL_EXAMS, str(session.get("exam_id") or "")) or {}
        incoming = _sanitise_answers(exam, payload.answers, tx=tx)
        answers = dict(session.get("answers") or {})
        answers.update(incoming)
        session["answers"] = answers
        session["last_saved_at"] = now
        session["heartbeat_at"] = now
        session["save_seq"] = int(session.get("save_seq") or 0) + 1
        if payload.client_save_id:
            seen.add(payload.client_save_id)
            session["client_save_ids"] = list(seen)[-200:]
        item = tx.update_if(store.COL_SESSIONS, session_id, expected, session)
        if item is None:
            latest = tx.get(store.COL_SESSIONS, session_id) or session
            _log(
                identity,
                "exams.session.save_conflict",
                "session",
                session_id,
                "Concurrent autosave conflict",
                tx=tx,
                session_id=session_id,
                client_id=payload.client_save_id,
            )
            return {"ok": False, "conflict": True, "item": _session_view(latest, include_answers=True), "reason": "concurrent_update"}
        _log(
            identity,
            "exams.session.autosaved",
            "session",
            session_id,
            "Session autosaved",
            {"seq": item.get("save_seq")},
            tx=tx,
            exam_id=str(session.get("exam_id") or ""),
            session_id=session_id,
            client_id=payload.client_save_id,
        )
    return {"ok": True, "item": _session_view(item, include_answers=True)}


@router.post("/sessions/{session_id}/submit")
def submit_session(session_id: str, payload: SessionSubmit = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    late_error: str | None = None
    saved: dict[str, Any] | None = None
    submission: dict[str, Any] | None = None
    with store.exam_transaction() as tx:
        session = tx.get(store.COL_SESSIONS, session_id)
        if not session:
            raise HTTPException(404, "Session not found")
        if str(session.get("actor_id") or "") != str(identity.get("actor_id") or ""):
            raise HTTPException(403, "Not allowed")
        submission_id = str(session.get("submission_id") or f"sub_{session_id}")
        existing_submission = tx.get(store.COL_SUBMISSIONS, submission_id)
        if str(session.get("state") or "") == "submitted":
            return {
                "ok": True,
                "item": _session_view(session, include_answers=True),
                "submission": existing_submission,
                "already_submitted": True,
            }
        if payload.client_submit_id and payload.client_submit_id == str(session.get("client_submit_id") or ""):
            return {
                "ok": True,
                "item": _session_view(session, include_answers=True),
                "submission": existing_submission,
                "duplicate": True,
            }
        if existing_submission:
            # A submission without a submitted session is never exposed as new work.
            session["state"] = "submitted"
            session["submission_id"] = submission_id
            tx.upsert(store.COL_SESSIONS, session_id, session)
            return {
                "ok": True,
                "item": _session_view(session, include_answers=True),
                "submission": existing_submission,
                "already_submitted": True,
            }
        current = int(session.get("updated_at") or 0)
        expected = int(payload.expected_updated_at) if payload.expected_updated_at is not None else current
        if expected != current:
            return {"ok": False, "conflict": True, "item": _session_view(session, include_answers=True), "reason": "stale_session"}
        if str(session.get("state") or "") == "invalidated":
            raise HTTPException(409, "This attempt was invalidated by an invigilator")
        now = store.now_ms()
        if now > _effective_expiry(session, now):
            events = list(session.get("events") or [])
            events.append({
                "type": "late_submit",
                "at": now,
                "detail": "Submission attempted after the deadline",
                "client_event_id": payload.client_submit_id,
            })
            session["events"] = events[-200:]
            session["state"] = "expired"
            session["expired_at"] = now
            tx.upsert(store.COL_SESSIONS, session_id, session)
            _log(
                identity,
                "exams.session.late_submit",
                "session",
                session_id,
                "Late submission attempt blocked",
                tx=tx,
                exam_id=str(session.get("exam_id") or ""),
                session_id=session_id,
                client_id=payload.client_submit_id,
            )
            # Commit the expiry event and audit record before returning the error.
            late_error = "Session expired; submission window closed"
        else:
            exam = tx.get(store.COL_EXAMS, str(session.get("exam_id") or "")) or {}
            incoming = _sanitise_answers(exam, payload.answers, tx=tx)
            answers = dict(session.get("answers") or {})
            answers.update(incoming)
            score = _score_submission(exam, answers, tx=tx)
            submission = {
                "id": submission_id,
                "session_id": session_id,
                "exam_id": exam.get("id"),
                "actor_id": session.get("actor_id"),
                "submitted_at": now,
                "answers": answers,
                "score": score,
                "status": "submitted",
                "attempt_no": session.get("attempt_no", 1),
                "results_release": exam.get("results_release", "immediate"),
            }
            created = tx.create_if_absent(store.COL_SUBMISSIONS, submission_id, submission)
            submission = created[0]
            session["answers"] = answers
            session["state"] = "submitted"
            session["submitted_at"] = now
            session["submission_id"] = submission_id
            session["client_submit_id"] = payload.client_submit_id
            saved = tx.update_if(store.COL_SESSIONS, session_id, expected, session)
            if saved is None:
                # Rolls back the submission as well because both writes share this transaction.
                raise HTTPException(409, "Concurrent session update; retry with fresh state")
            _log(
                identity,
                "exams.session.submitted",
                "session",
                session_id,
                "Exam submitted",
                {"submission_id": submission_id, "percent": score.get("percent")},
                tx=tx,
                exam_id=str(session.get("exam_id") or ""),
                session_id=session_id,
                submission_id=submission_id,
                client_id=payload.client_submit_id,
            )
    if late_error:
        raise HTTPException(409, late_error)
    return {"ok": True, "item": _session_view(saved, include_answers=True), "submission": submission}


@router.post("/sessions/{session_id}/events")
def record_session_event(session_id: str, payload: SessionEventUpsert = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    with store.exam_transaction() as tx:
        session = tx.get(store.COL_SESSIONS, session_id)
        if not session:
            raise HTTPException(404, "Session not found")
        if str(session.get("actor_id") or "") != str(identity.get("actor_id") or ""):
            raise HTTPException(403, "Not allowed")
        if str(session.get("state") or "") != "active":
            return {"ok": True, "item": _session_view(session, include_answers=True), "ignored": True, "reason": "session_not_active"}
        events = list(session.get("events") or [])
        if payload.client_event_id and any(str(item.get("client_event_id")) == payload.client_event_id for item in events if isinstance(item, dict)):
            return {"ok": True, "item": _session_view(session, include_answers=True), "duplicate": True}
        if len(events) >= 200:
            return {"ok": True, "item": _session_view(session, include_answers=True), "ignored": True, "reason": "event_limit_reached"}
        events.append({
            "type": payload.event_type,
            "detail": _text(payload.detail, 300),
            "at": store.now_ms(),
            "client_event_id": _text(payload.client_event_id, 120),
        })
        session["events"] = events[-200:]
        session["heartbeat_at"] = store.now_ms()
        session["flags"] = _flags(session)
        item = tx.upsert(store.COL_SESSIONS, session_id, session)
        _log(
            identity,
            f"exams.session.event.{payload.event_type}",
            "session",
            session_id,
            "Candidate activity signal recorded",
            {"type": payload.event_type},
            tx=tx,
            exam_id=str(session.get("exam_id") or ""),
            session_id=session_id,
            client_id=payload.client_event_id,
        )
    return {"ok": True, "item": _session_view(item, include_answers=True)}


@router.post("/sessions/{session_id}/heartbeat")
def session_heartbeat(session_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    with store.exam_transaction() as tx:
        session = tx.get(store.COL_SESSIONS, session_id)
        if not session:
            raise HTTPException(404, "Session not found")
        if str(session.get("actor_id") or "") != str(identity.get("actor_id") or ""):
            raise HTTPException(403, "Not allowed")
        if str(session.get("state") or "") != "active":
            return {"ok": True, "item": _session_view(session, include_answers=True), "ignored": True}
        session["heartbeat_at"] = store.now_ms()
        item = tx.upsert(store.COL_SESSIONS, session_id, session)
    return {"ok": True, "item": _session_view(item, include_answers=True), "server_now": store.now_ms()}


@router.post("/sessions/{session_id}/actions")
def invigilation_action(session_id: str, payload: SessionAction = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    with store.exam_transaction() as tx:
        session = tx.get(store.COL_SESSIONS, session_id)
        if not session:
            raise HTTPException(404, "Session not found")
        exam_id = str(session.get("exam_id") or "")
        enrollment = _enrollment(tx, exam_id, identity)
        _require_exam_capability(identity, "exams.invigilate", enrollment)
        expected = int(payload.expected_updated_at) if payload.expected_updated_at is not None else int(session.get("updated_at") or 0)
        if expected != int(session.get("updated_at") or 0):
            return {"ok": False, "conflict": True, "item": _session_view(session, include_answers=False), "reason": "stale_session"}
        before = _snapshot(session)
        now = store.now_ms()
        reason = _text(payload.reason, 1000)
        if payload.action == "extend_time":
            minutes = int(payload.minutes or 0)
            if not 1 <= minutes <= 120:
                raise HTTPException(400, "minutes must be between 1 and 120")
            session["extension_ms"] = int(session.get("extension_ms") or 0) + minutes * 60_000
        elif payload.action == "pause":
            if str(session.get("state") or "") != "active" or session.get("paused_at"):
                raise HTTPException(409, "Only an active, unpaused session can be paused")
            session["paused_at"] = now
        elif payload.action == "resume":
            if not session.get("paused_at"):
                raise HTTPException(409, "Session is not paused")
            session["pause_total_ms"] = int(session.get("pause_total_ms") or 0) + max(0, now - int(session["paused_at"]))
            session["paused_at"] = None
        elif payload.action == "flag":
            flags = _flags(session)
            if reason not in flags:
                flags.append(reason or "invigilator_flagged")
            session["flags"] = flags
        elif payload.action == "invalidate":
            session["state"] = "invalidated"
            session["invalidated_at"] = now
        elif payload.action == "note":
            notes = list(session.get("notes") or [])
            notes.append({"at": now, "actor_id": identity.get("actor_id"), "note": reason})
            session["notes"] = notes[-200:]
        item = tx.upsert(store.COL_SESSIONS, session_id, session)
        _log(
            identity,
            f"exams.session.action.{payload.action}",
            "session",
            session_id,
            f"Invigilation action: {payload.action}",
            {"reason": reason, "minutes": payload.minutes},
            tx=tx,
            exam_id=exam_id,
            session_id=session_id,
            before_summary=before,
            after_summary=_snapshot(session),
        )
    return {"ok": True, "item": _session_view(item, include_answers=False)}


# ---------------------------------------------------------------------------
# Submissions, grading and candidate result release
# ---------------------------------------------------------------------------
@router.get("/submissions")
def list_submissions(exam_id: str = "", limit: int = 200, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    privileged = permissions.has_capability(identity, "exams.manage") or permissions.has_capability(identity, "exams.grade")
    exams = {str(exam.get("id") or ""): exam for exam in store.list_docs(store.COL_EXAMS, limit=5000)}
    items = store.list_docs(store.COL_SUBMISSIONS, limit=limit)
    if exam_id:
        items = [item for item in items if str(item.get("exam_id") or "") == exam_id]
    if not privileged:
        items = [item for item in items if str(item.get("actor_id") or "") == str(identity.get("actor_id") or "")]
    return {
        "ok": True,
        "items": [_submission_view(item, exams.get(str(item.get("exam_id") or ""), {}), identity) for item in items],
        "count": len(items),
    }


@router.get("/submissions/{submission_id}")
def get_submission(submission_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    item = store.get_doc(store.COL_SUBMISSIONS, submission_id)
    if not item:
        raise HTTPException(404, "Submission not found")
    exam = store.get_doc(store.COL_EXAMS, str(item.get("exam_id") or "")) or {}
    with store.exam_transaction() as tx:
        enrollment = _enrollment(tx, str(item.get("exam_id") or ""), identity)
    privileged = permissions.has_capability(identity, "exams.manage") or permissions.has_capability(identity, "exams.grade") or permissions.enrollment_allows(enrollment, "exams.grade")
    if not privileged and str(item.get("actor_id") or "") != str(identity.get("actor_id") or ""):
        raise HTTPException(403, "Not allowed")
    return {"ok": True, "item": item if privileged else _submission_view(item, exam, identity), "exam": exam}


@router.get("/submissions/{submission_id}/review")
def review_submission(submission_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    item = store.get_doc(store.COL_SUBMISSIONS, submission_id)
    if not item:
        raise HTTPException(404, "Submission not found")
    with store.exam_transaction() as tx:
        enrollment = _enrollment(tx, str(item.get("exam_id") or ""), identity)
    _require_exam_capability(identity, "exams.grade", enrollment)
    exam = store.get_doc(store.COL_EXAMS, str(item.get("exam_id") or "")) or {}
    return {
        "ok": True,
        "item": item,
        "questions": _exam_questions(exam, include_answers=True),
        "rubric_notes": {
            str(q.get("id")): q.get("rubric", "") for q in _exam_questions(exam, include_answers=True)
        },
    }


@router.post("/submissions/{submission_id}/grade")
def grade_submission(submission_id: str, payload: SubmissionGrade = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    with store.exam_transaction() as tx:
        item = tx.get(store.COL_SUBMISSIONS, submission_id)
        if not item:
            raise HTTPException(404, "Submission not found")
        exam_id = str(item.get("exam_id") or "")
        enrollment = _enrollment(tx, exam_id, identity)
        _require_exam_capability(identity, "exams.grade", enrollment)
        current = int(item.get("updated_at") or 0)
        expected = int(payload.expected_updated_at) if payload.expected_updated_at is not None else current
        before = json.dumps(item.get("score") or {}, ensure_ascii=False, sort_keys=True)[:500]
        if expected != current:
            _log(
                identity,
                "exams.submission.grade_conflict",
                "submission",
                submission_id,
                "Grade conflict",
                {"expected": expected, "current": current},
                tx=tx,
                exam_id=exam_id,
                submission_id=submission_id,
            )
            return {"ok": False, "conflict": True, "item": item, "reason": "stale_submission"}
        exam = tx.get(store.COL_EXAMS, exam_id) or {}
        overrides = {
            str(row.question_id): {"earned_points": row.earned_points, "feedback": row.feedback}
            for row in payload.question_scores
        }
        score = _score_submission(exam, item.get("answers") or {}, overrides=overrides, tx=tx)
        if payload.earned_points is not None:
            score["earned_points"] = float(payload.earned_points)
            total = float(score.get("total_points") or 0)
            if total > 0:
                score["percent"] = round(float(payload.earned_points) / total * 100.0, 2)
        if payload.percent is not None:
            score["percent"] = float(payload.percent)
            score["percent_override"] = True
        data = dict(item)
        data["score"] = score
        data["feedback"] = _text(payload.feedback, 8000)
        data["status"] = payload.status
        data["graded_by"] = identity.get("actor_id")
        data["graded_at"] = store.now_ms()
        data["question_scores"] = [
            {"question_id": row.question_id, "earned_points": row.earned_points, "feedback": _text(row.feedback, 4000)}
            for row in payload.question_scores
        ]
        if payload.release and payload.status == "returned":
            data["released_at"] = store.now_ms()
        saved = tx.update_if(store.COL_SUBMISSIONS, submission_id, expected, data)
        if saved is None:
            raise HTTPException(409, "Concurrent grade update; retry with fresh state")
        _log(
            identity,
            "exams.submission.graded",
            "submission",
            submission_id,
            "Submission graded",
            {"status": payload.status, "percent": score.get("percent"), "questions": len(payload.question_scores)},
            tx=tx,
            exam_id=exam_id,
            submission_id=submission_id,
            before_summary=before,
            after_summary=json.dumps(score, ensure_ascii=False, sort_keys=True)[:500],
        )
    return {"ok": True, "item": saved}


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
def _compute_analytics() -> dict[str, Any]:
    exams = store.list_docs(store.COL_EXAMS, limit=5000)
    sessions = store.list_docs(store.COL_SESSIONS, limit=5000)
    submissions = store.list_docs(store.COL_SUBMISSIONS, limit=5000)
    enrollments = store.list_docs(store.COL_ENROLLMENTS, limit=5000)
    by_exam: list[dict[str, Any]] = []
    timeline: dict[str, int] = {}
    for exam in exams:
        eid = str(exam.get("id") or "")
        exam_sessions = [s for s in sessions if str(s.get("exam_id") or "") == eid]
        exam_subs = [s for s in submissions if str(s.get("exam_id") or "") == eid]
        candidates = {str(e.get("actor_id")) for e in enrollments if str(e.get("exam_id") or "") == eid and str(e.get("role")) == "candidate"}
        completed = [s for s in exam_subs if str(s.get("status") or "") in {"graded", "returned", "submitted"}]
        percents = []
        for submission in exam_subs:
            try:
                percents.append(float((submission.get("score") or {}).get("percent")))
            except (TypeError, ValueError):
                continue
        pass_mark = float(exam.get("pass_mark_percent") or 50)
        item_stats: dict[str, dict[str, Any]] = {}
        for submission in exam_subs:
            submitted_at = int(submission.get("submitted_at") or 0)
            if submitted_at:
                bucket = f"{submitted_at // 3_600_000:013d}"
                timeline[bucket] = timeline.get(bucket, 0) + 1
            for detail in (submission.get("score") or {}).get("details") or []:
                if not isinstance(detail, dict):
                    continue
                qid = str(detail.get("question_id") or "")
                if not qid:
                    continue
                row = item_stats.setdefault(qid, {"question_id": qid, "attempts": 0, "correct": 0, "upper": 0, "upper_n": 0, "lower": 0, "lower_n": 0})
                row["attempts"] += 1
                if detail.get("correct"):
                    row["correct"] += 1
        ordered = sorted(exam_subs, key=lambda s: float((s.get("score") or {}).get("percent") or 0))
        cutoff = max(1, len(ordered) // 3)
        lower = ordered[:cutoff]
        upper = ordered[-cutoff:]
        for group, key in ((lower, "lower"), (upper, "upper")):
            for submission in group:
                for detail in (submission.get("score") or {}).get("details") or []:
                    if not isinstance(detail, dict):
                        continue
                    row = item_stats.get(str(detail.get("question_id") or ""))
                    if row:
                        row[f"{key}_n"] += 1
                        if detail.get("correct"):
                            row[f"{key}"] += 1
        questions = []
        for qid, row in item_stats.items():
            attempts = row["attempts"] or 1
            upper_rate = row["upper"] / (row["upper_n"] or 1)
            lower_rate = row["lower"] / (row["lower_n"] or 1)
            questions.append({
                "question_id": qid,
                "attempts": row["attempts"],
                "difficulty": round(row["correct"] / attempts, 3),
                "discrimination": round(upper_rate - lower_rate, 3),
            })
        questions.sort(key=lambda item: item["question_id"])
        by_exam.append({
            "exam_id": eid,
            "title": exam.get("title") or eid,
            "status": exam.get("status") or "draft",
            "enrolled_candidates": len(candidates),
            "attempts": len(exam_sessions),
            "submissions": len(exam_subs),
            "completion_rate": round(len(completed) / len(exam_sessions), 3) if exam_sessions else 0.0,
            "average_score": round(statistics.fmean(percents), 2) if percents else None,
            "median_score": round(statistics.median(percents), 2) if percents else None,
            "pass_rate": round(sum(1 for value in percents if value >= pass_mark) / len(percents), 3) if percents else None,
            "requires_manual_grading": sum(1 for s in exam_subs if (s.get("score") or {}).get("requires_manual")),
            "question_stats": questions,
        })
    return {
        "by_exam": by_exam,
        "attempt_timeline": [
            {"hour_bucket": key, "submissions": value} for key, value in sorted(timeline.items())
        ],
        "counts": {collection: store.count_docs(collection) for collection in sorted(store.EXAMS_COLLECTIONS)},
    }


@router.get("/analytics")
def exams_analytics(format: str = "json", mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    if not (
        permissions.has_capability(identity, "exams.manage")
        or permissions.has_capability(identity, "exams.grade")
        or permissions.has_capability(identity, "exams.analytics")
    ):
        raise HTTPException(403, "Not allowed")
    report = _compute_analytics()
    summary = {
        "submissions": sum(row["submissions"] for row in report["by_exam"]),
        "attempts": sum(row["attempts"] for row in report["by_exam"]),
        "exams": len(report["by_exam"]),
    }
    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "exam_id", "title", "status", "enrolled_candidates", "attempts", "submissions",
            "completion_rate", "average_score", "median_score", "pass_rate", "requires_manual_grading",
        ])
        for row in report["by_exam"]:
            writer.writerow([row[key] for key in (
                "exam_id", "title", "status", "enrolled_candidates", "attempts", "submissions",
                "completion_rate", "average_score", "median_score", "pass_rate", "requires_manual_grading",
            )])
        _log(identity, "exams.analytics.exported", "exams_module", "analytics", "Analytics exported as CSV", {"format": "csv"})
        return Response(content=output.getvalue(), media_type="text/csv")
    _log(identity, "exams.analytics.viewed", "exams_module", "analytics", "Analytics viewed", {"format": "json"})
    return {"ok": True, "analytics": summary, "by_exam": report["by_exam"], "counts": report["counts"], "attempt_timeline": report["attempt_timeline"]}


@router.get("/analytics/export")
def exams_analytics_export(format: str = "csv", mnh_session: str | None = Cookie(default=None)):
    return exams_analytics(format=format, mnh_session=mnh_session)


# ---------------------------------------------------------------------------
# Audit access and integrity verification
# ---------------------------------------------------------------------------
@router.get("/audit")
def exams_audit(limit: int = 200, action: str = "", actor_id: str = "", mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.audit.view")
    events = audit.list_events(limit=limit, action=action, actor_id=actor_id)
    _log(identity, "exams.audit.viewed", "exams_module", "audit", "Audit ledger viewed", {"limit": limit})
    return {"ok": True, "items": events, "count": len(events), "append_only": True}


@router.get("/audit/verify")
def exams_audit_verify(mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.audit.view")
    result = audit.verify_chain()
    _log(identity, "exams.audit.verified", "exams_module", "audit", "Audit chain verification run", result)
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# Explicit EXAMS backup/export and restore.
# Generic /api/export and /api/restore deliberately exclude exams_* data.
# ---------------------------------------------------------------------------
def _backup_hash(schema_version: str, documents: list[dict[str, Any]]) -> str:
    material = json.dumps(
        {"schema_version": schema_version, "documents": documents},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@router.get("/backup")
def exams_backup(mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.backup")
    documents: list[dict[str, Any]] = []
    for collection in sorted(store.EXAMS_COLLECTIONS):
        for item in store.list_docs(collection, limit=5000):
            documents.append({"col": collection, "id": item["id"], "data": item})
    payload = {"schema_version": BACKUP_SCHEMA_VERSION, "documents": documents}
    checksum = _backup_hash(BACKUP_SCHEMA_VERSION, documents)
    _log(identity, "exams.backup.exported", "exams_module", "backup", "EXAMS backup exported", {"documents": len(documents), "sha256": checksum})
    return {
        "ok": True,
        "schema_version": BACKUP_SCHEMA_VERSION,
        "integrity": {"algorithm": "sha256", "sha256": checksum},
        "documents": documents,
        "audit_note": "Audit ledger events are append-only and are not restored by this endpoint.",
    }


@router.post("/restore")
def exams_restore(payload: ExamsBackupPayload = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.backup")
    if payload.schema_version != BACKUP_SCHEMA_VERSION:
        raise HTTPException(400, f"Unsupported EXAMS backup schema: {payload.schema_version}")
    expected = str((payload.integrity or {}).get("sha256") or "")
    if not expected or expected != _backup_hash(payload.schema_version, payload.documents):
        raise HTTPException(400, "EXAMS backup integrity check failed")
    if payload.overwrite_conflicts and not permissions.is_admin(identity):
        raise HTTPException(403, "Only an EXAMS administrator may overwrite live exam data")
    normalised: list[tuple[str, str, dict[str, Any]]] = []
    for item in payload.documents:
        collection = str(item.get("col") or "")
        doc_id = str(item.get("id") or "")
        data = item.get("data")
        if collection not in store.EXAMS_COLLECTIONS or not doc_id or not isinstance(data, dict):
            raise HTTPException(400, "EXAMS backup contains an invalid document")
        normalised.append((collection, doc_id, data))
    written = 0
    conflicts: list[str] = []
    with store.exam_transaction() as tx:
        for collection, doc_id, data in normalised:
            if tx.get(collection, doc_id) is not None:
                conflicts.append(f"{collection}/{doc_id}")
        if conflicts and not payload.overwrite_conflicts:
            raise HTTPException(409, {"message": "EXAMS restore would overwrite live data", "conflicts": conflicts[:100]})
        for collection, doc_id, data in normalised:
            tx.upsert(collection, doc_id, data)
            written += 1
        _log(
            identity,
            "exams.backup.restored",
            "exams_module",
            "backup",
            "EXAMS backup restored",
            {"documents": written, "overwrite_conflicts": payload.overwrite_conflicts, "schema_version": payload.schema_version},
            tx=tx,
        )
    return {"ok": True, "restored": written, "conflicts": conflicts, "schema_version": payload.schema_version}
