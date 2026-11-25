"""FastAPI routes for EXAMS module.

Phase 3 foundation: namespaced exam definitions, question bank, composition,
enrollment, backend-authoritative session/autosave/submit, and basic integrity.
Legacy calendar `examinations` remains unchanged.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Cookie, HTTPException

from app.exams import audit, permissions, store
from app.exams.schemas import EnrollmentUpsert, ExamUpsert, QuestionUpsert, SessionAutosave, SessionStart, SessionSubmit

router = APIRouter(prefix="/api/exams", tags=["exams"])


def _clean_question(doc: dict[str, Any], *, include_answers: bool) -> dict[str, Any]:
    out = dict(doc)
    if not include_answers:
        out.pop("correct_option_ids", None)
        out.pop("correct_text", None)
        out.pop("explanation", None)
    return out


def _exam_questions(exam: dict[str, Any], *, include_answers: bool) -> list[dict[str, Any]]:
    links = exam.get("questions") if isinstance(exam.get("questions"), list) else []
    result = []
    for i, link in enumerate(links):
        if not isinstance(link, dict):
            continue
        qid = str(link.get("question_id") or "").strip()
        if not qid:
            continue
        q = store.get_doc(store.COL_QUESTIONS, qid)
        if not q or not q.get("active", True):
            continue
        q = _clean_question(q, include_answers=include_answers)
        q["link_order"] = int(link.get("order") if link.get("order") is not None else i)
        if link.get("points") is not None:
            try:
                q["points"] = float(link.get("points"))
            except Exception:
                pass
        result.append(q)
    result.sort(key=lambda x: (int(x.get("link_order", 0)), str(x.get("id", ""))))
    return result


def _score_submission(exam: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    questions = _exam_questions(exam, include_answers=True)
    total = 0.0
    earned = 0.0
    details = []
    for q in questions:
        pts = float(q.get("points") or 0)
        total += pts
        qid = str(q.get("id") or "")
        qtype = str(q.get("type") or "mcq")
        ans = answers.get(qid)
        correct = False
        if qtype in {"mcq", "true_false"}:
            correct_ids = {str(x) for x in (q.get("correct_option_ids") or [])}
            correct = str(ans or "") in correct_ids if correct_ids else False
        elif qtype == "multiple_select":
            correct_ids = {str(x) for x in (q.get("correct_option_ids") or [])}
            given = {str(x) for x in (ans or [])} if isinstance(ans, list) else set()
            correct = given == correct_ids and bool(correct_ids)
        elif qtype in {"short_text", "essay"}:
            expected = str(q.get("correct_text") or "").strip().lower()
            given = str(ans or "").strip().lower()
            correct = bool(expected) and given == expected
        got = pts if correct else 0.0
        earned += got
        details.append({"question_id": qid, "correct": correct, "points": pts, "earned": got})
    percent = (earned / total * 100.0) if total > 0 else 0.0
    return {"total_points": total, "earned_points": earned, "percent": round(percent, 2), "details": details}


def _can_manage(identity): return permissions.has_capability(identity, "exams.manage")
def _can_q(identity): return permissions.has_capability(identity, "exams.question.manage")


@router.get("/health")
def exams_health(mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    return {
        "ok": True, "module": "exams", "status": "phase4-foundation",
        "isolated_from_legacy_examinations": True,
        "legacy_examinations_collection": "examinations",
        "collections": {name: store.count_docs(name) for name in sorted(store.EXAMS_COLLECTIONS)},
        "identity": identity,
        "capabilities": sorted(permissions.CAPABILITIES.get(identity["exam_role"], set())),
    }


@router.get("/capabilities")
def exams_capabilities(mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    caps = sorted(permissions.CAPABILITIES.get(identity["exam_role"], set()))
    return {"ok": True, "identity": identity, "capabilities": caps, "can_manage": "exams.manage" in caps, "can_take": "exams.take" in caps}


@router.get("/overview")
def exams_overview(mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    counts = {name: store.count_docs(name) for name in sorted(store.EXAMS_COLLECTIONS)}
    audit.emit_event(actor=identity, action="exams.overview.viewed", entity_type="exams_module", entity_id="overview", summary="EXAMS overview viewed", details={"counts": counts})
    return {"ok": True, "module": "exams", "phase": "4-foundation", "counts": counts, "collections": sorted(store.EXAMS_COLLECTIONS)}


@router.get("/my")
def my_exams(mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    actor_id = str(identity.get("actor_id") or "")
    aliases = []
    role_id = f"mnh:{str(identity.get('mnh_role') or '').strip().lower()}"
    if role_id and role_id != actor_id:
        aliases.append(role_id)
    actor_ids = {actor_id, *aliases}
    sessions = [x for x in store.list_docs(store.COL_SESSIONS, limit=500) if str(x.get("actor_id") or "") in actor_ids]
    submissions = [x for x in store.list_docs(store.COL_SUBMISSIONS, limit=500) if str(x.get("actor_id") or "") in actor_ids]
    enrollments = [x for x in store.list_docs(store.COL_ENROLLMENTS, limit=500) if str(x.get("actor_id") or "") in actor_ids]
    return {"ok": True, "identity": identity, "sessions": sessions, "submissions": submissions, "enrollments": enrollments}


# ----- Questions -----
@router.get("/questions")
def list_questions(limit: int = 100, mnh_session: str | None = Cookie(default=None)):
    permissions.require_capability(mnh_session, "exams.question.manage")
    return {"ok": True, "items": store.list_docs(store.COL_QUESTIONS, limit=limit)}


@router.post("/questions")
def create_question(payload: QuestionUpsert = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.question.manage")
    doc = payload.model_dump(); doc["created_by"] = identity.get("actor_id")
    item = store.upsert_doc(store.COL_QUESTIONS, store.new_id("q"), doc)
    audit.emit_event(actor=identity, action="exams.question.created", entity_type="question", entity_id=item["id"], summary="Question created")
    return {"ok": True, "item": item}


@router.put("/questions/{question_id}")
def update_question(question_id: str, payload: QuestionUpsert = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.question.manage")
    existing = store.get_doc(store.COL_QUESTIONS, question_id)
    if not existing: raise HTTPException(404, "Question not found")
    data = existing.copy(); data.update(payload.model_dump()); data["updated_by"] = identity.get("actor_id")
    item = store.upsert_doc(store.COL_QUESTIONS, question_id, data)
    audit.emit_event(actor=identity, action="exams.question.updated", entity_type="question", entity_id=question_id, summary="Question updated")
    return {"ok": True, "item": item}


@router.delete("/questions/{question_id}")
def delete_question(question_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.question.manage")
    existing = store.get_doc(store.COL_QUESTIONS, question_id)
    if not existing: raise HTTPException(404, "Question not found")
    store.delete_doc(store.COL_QUESTIONS, question_id)
    audit.emit_event(actor=identity, action="exams.question.deleted", entity_type="question", entity_id=question_id, summary="Question deleted")
    return {"ok": True, "deleted": question_id}


# ----- Enrollments -----
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
    exam = store.get_doc(store.COL_EXAMS, payload.exam_id)
    if not exam: raise HTTPException(404, "Exam not found")
    key = f"enr_{payload.exam_id}_{payload.actor_id}".replace(":", "_")
    doc = {"exam_id": payload.exam_id, "actor_id": payload.actor_id, "role": payload.role, "created_by": identity.get("actor_id")}
    item = store.upsert_doc(store.COL_ENROLLMENTS, key, doc)
    audit.emit_event(actor=identity, action="exams.enrollment.upserted", entity_type="enrollment", entity_id=item["id"], summary="Enrollment upserted", details={"exam_id": payload.exam_id, "actor_id": payload.actor_id, "role": payload.role})
    return {"ok": True, "item": item}


# ----- Exams -----
@router.get("/exams")
def list_exams(limit: int = 100, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    items = store.list_docs(store.COL_EXAMS, limit=limit)
    if not _can_manage(identity):
        items = [x for x in items if str(x.get("status") or "draft") == "published"]
    return {"ok": True, "items": items, "count": len(items)}


@router.post("/exams")
def create_exam(payload: ExamUpsert = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.manage")
    data = payload.model_dump(); data["created_by"] = identity.get("actor_id"); data["created_by_role"] = identity.get("exam_role")
    item = store.upsert_doc(store.COL_EXAMS, store.new_id("exam"), data)
    audit.emit_event(actor=identity, action="exams.exam.created", entity_type="exam", entity_id=item["id"], summary=f"Created exam: {item.get('title','')}")
    return {"ok": True, "item": item}


@router.get("/exams/{exam_id}")
def get_exam(exam_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    doc = store.get_doc(store.COL_EXAMS, exam_id)
    if not doc: raise HTTPException(404, "Exam not found")
    can_manage = _can_manage(identity)
    if not can_manage and str(doc.get("status") or "") != "published":
        raise HTTPException(404, "Exam not found")
    doc = dict(doc); doc["question_items"] = _exam_questions(doc, include_answers=can_manage)
    return {"ok": True, "item": doc}


@router.put("/exams/{exam_id}")
def update_exam(exam_id: str, payload: ExamUpsert = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.manage")
    existing = store.get_doc(store.COL_EXAMS, exam_id)
    if not existing: raise HTTPException(404, "Exam not found")
    data = existing.copy(); data.update(payload.model_dump()); data["updated_by"] = identity.get("actor_id")
    item = store.upsert_doc(store.COL_EXAMS, exam_id, data)
    audit.emit_event(actor=identity, action="exams.exam.updated", entity_type="exam", entity_id=exam_id, summary=f"Updated exam: {item.get('title','')}")
    return {"ok": True, "item": item}


@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.require_capability(mnh_session, "exams.manage")
    existing = store.get_doc(store.COL_EXAMS, exam_id)
    if not existing: raise HTTPException(404, "Exam not found")
    store.delete_doc(store.COL_EXAMS, exam_id)
    audit.emit_event(actor=identity, action="exams.exam.deleted", entity_type="exam", entity_id=exam_id, summary=f"Deleted exam: {existing.get('title','')}")
    return {"ok": True, "deleted": exam_id}


# ----- Sessions / attempts (backend-authoritative) -----
@router.post("/sessions/start")
def start_session(payload: SessionStart = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    if not identity.get("authenticated"):
        raise HTTPException(401, "Authentication required to start an exam session")
    exam = store.get_doc(store.COL_EXAMS, payload.exam_id)
    if not exam or str(exam.get("status") or "") != "published":
        raise HTTPException(404, "Published exam not found")
    actor_id = str(identity.get("actor_id") or "")
    actor_aliases = []
    role_id = f"mnh:{str(identity.get('mnh_role') or '').strip().lower()}"
    if role_id != actor_id:
        actor_aliases.append(role_id)
    if bool(exam.get("require_enrollment")) and not _can_manage(identity):
        enr = store.find_enrollment(payload.exam_id, actor_id, actor_aliases=actor_aliases)
        if not enr or str(enr.get("role") or "") != "candidate":
            raise HTTPException(403, "Enrollment required for this exam")
    sessions = store.find_sessions(actor_id, payload.exam_id)
    for alias in actor_aliases:
        sessions.extend(store.find_sessions(alias, payload.exam_id))
    # dedupe by id
    uniq = {}
    for s in sessions:
        sid = str(s.get("id") or "")
        if sid:
            uniq[sid] = s
    sessions = list(uniq.values())
    now = store.now_ms()
    for s in sessions:
        if str(s.get("state") or "") in {"active", "submitted"}:
            return {"ok": True, "item": s, "resumed": True}
    attempts_used = len([s for s in sessions if str(s.get("state") or "") in {"submitted", "expired"}])
    max_attempts = int(exam.get("max_attempts") or 1)
    if attempts_used >= max_attempts and not _can_manage(identity):
        raise HTTPException(403, "Maximum attempts reached")
    duration_ms = int(exam.get("duration_minutes") or 60) * 60 * 1000
    session = {
        "exam_id": payload.exam_id, "actor_id": actor_id, "actor_role": identity.get("exam_role"),
        "state": "active", "started_at": now, "expires_at": now + duration_ms, "last_saved_at": now,
        "submitted_at": None, "answers": {}, "save_seq": 0, "client_save_ids": [], "client_submit_id": "",
        "attempt_no": attempts_used + 1,
    }
    item = store.upsert_doc(store.COL_SESSIONS, store.new_id("sess"), session)
    audit.emit_event(actor=identity, action="exams.session.started", entity_type="session", entity_id=item["id"], summary="Exam session started", details={"exam_id": payload.exam_id, "attempt_no": item["attempt_no"]})
    return {"ok": True, "item": item, "resumed": False}


@router.get("/sessions/{session_id}")
def get_session(session_id: str, mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    sess = store.get_doc(store.COL_SESSIONS, session_id)
    if not sess: raise HTTPException(404, "Session not found")
    if str(sess.get("actor_id") or "") != str(identity.get("actor_id") or "") and not permissions.has_capability(identity, "exams.session.manage"):
        raise HTTPException(403, "Not allowed")
    exam = store.get_doc(store.COL_EXAMS, str(sess.get("exam_id") or ""))
    return {"ok": True, "item": sess, "exam": exam, "server_now": store.now_ms()}


@router.post("/sessions/{session_id}/autosave")
def autosave_session(session_id: str, payload: SessionAutosave = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    sess = store.get_doc(store.COL_SESSIONS, session_id)
    if not sess: raise HTTPException(404, "Session not found")
    if str(sess.get("actor_id") or "") != str(identity.get("actor_id") or ""):
        raise HTTPException(403, "Not allowed")
    if payload.expected_updated_at is not None and int(sess.get("updated_at") or 0) != int(payload.expected_updated_at):
        return {"ok": False, "conflict": True, "item": sess, "reason": "stale_session"}
    if str(sess.get("state") or "") != "active":
        return {"ok": True, "item": sess, "ignored": True, "reason": "session_not_active"}
    now = store.now_ms()
    if now > int(sess.get("expires_at") or 0):
        sess["state"] = "expired"; sess["expired_at"] = now
        store.upsert_doc(store.COL_SESSIONS, session_id, sess)
        audit.emit_event(actor=identity, action="exams.session.expired", entity_type="session", entity_id=session_id, summary="Session expired")
        return {"ok": True, "item": sess, "expired": True}
    seen = set(str(x) for x in (sess.get("client_save_ids") or []))
    if payload.client_save_id and payload.client_save_id in seen:
        return {"ok": True, "item": sess, "duplicate": True}
    answers = sess.get("answers") if isinstance(sess.get("answers"), dict) else {}
    answers.update(payload.answers or {})
    sess["answers"] = answers; sess["last_saved_at"] = now; sess["save_seq"] = int(sess.get("save_seq") or 0) + 1
    if payload.client_save_id:
        seen.add(payload.client_save_id); sess["client_save_ids"] = list(seen)[-200:]
    expected = payload.expected_updated_at if payload.expected_updated_at is not None else sess.get("updated_at")
    item = store.update_doc_if_updated_at(store.COL_SESSIONS, session_id, int(expected or 0), sess)
    if item is None:
        latest = store.get_doc(store.COL_SESSIONS, session_id)
        return {"ok": False, "conflict": True, "item": latest, "reason": "concurrent_update"}
    audit.emit_event(actor=identity, action="exams.session.autosaved", entity_type="session", entity_id=session_id, summary="Session autosaved", details={"seq": item.get("save_seq")})
    return {"ok": True, "item": item}


@router.post("/sessions/{session_id}/submit")
def submit_session(session_id: str, payload: SessionSubmit = Body(...), mnh_session: str | None = Cookie(default=None)):
    identity = permissions.resolve_identity(mnh_session)
    sess = store.get_doc(store.COL_SESSIONS, session_id)
    if not sess: raise HTTPException(404, "Session not found")
    if str(sess.get("actor_id") or "") != str(identity.get("actor_id") or ""):
        raise HTTPException(403, "Not allowed")
    if str(sess.get("state") or "") == "submitted":
        sub_id = str(sess.get("submission_id") or "")
        sub = store.get_doc(store.COL_SUBMISSIONS, sub_id) if sub_id else None
        return {"ok": True, "item": sess, "submission": sub, "already_submitted": True}
    if payload.expected_updated_at is not None and int(sess.get("updated_at") or 0) != int(payload.expected_updated_at):
        return {"ok": False, "conflict": True, "item": sess, "reason": "stale_session"}
    now = store.now_ms()
    if now > int(sess.get("expires_at") or 0):
        sess["state"] = "expired"; sess["expired_at"] = now
        store.upsert_doc(store.COL_SESSIONS, session_id, sess)
        raise HTTPException(409, "Session expired; submission window closed")
    if payload.client_submit_id and payload.client_submit_id == str(sess.get("client_submit_id") or ""):
        sub_id = str(sess.get("submission_id") or "")
        sub = store.get_doc(store.COL_SUBMISSIONS, sub_id) if sub_id else None
        return {"ok": True, "item": sess, "submission": sub, "duplicate": True}
    exam = store.get_doc(store.COL_EXAMS, str(sess.get("exam_id") or ""))
    if not exam: raise HTTPException(404, "Exam not found")
    answers = sess.get("answers") if isinstance(sess.get("answers"), dict) else {}
    answers.update(payload.answers or {})
    score = _score_submission(exam, answers)
    submission_id = f"sub_{session_id}"
    submission = {"id": submission_id, "session_id": session_id, "exam_id": exam.get("id"), "actor_id": sess.get("actor_id"), "submitted_at": now, "answers": answers, "score": score, "status": "submitted", "attempt_no": sess.get("attempt_no", 1)}
    sub_item, sub_created = store.create_doc_if_absent(store.COL_SUBMISSIONS, submission_id, submission)
    if not sub_created:
        sess["state"] = "submitted"; sess["submission_id"] = sub_item.get("id", submission_id)
        store.upsert_doc(store.COL_SESSIONS, session_id, sess)
        return {"ok": True, "item": store.get_doc(store.COL_SESSIONS, session_id) or sess, "submission": sub_item, "already_submitted": True}
    sess["answers"] = answers; sess["state"] = "submitted"; sess["submitted_at"] = now; sess["submission_id"] = sub_item["id"]; sess["client_submit_id"] = payload.client_submit_id
    expected = payload.expected_updated_at if payload.expected_updated_at is not None else sess.get("updated_at")
    sess_item = store.update_doc_if_updated_at(store.COL_SESSIONS, session_id, int(expected or 0), sess)
    if sess_item is None:
        latest = store.get_doc(store.COL_SESSIONS, session_id)
        if latest and str(latest.get("state") or "") == "submitted":
            sub_id = str(latest.get("submission_id") or submission_id)
            sub = store.get_doc(store.COL_SUBMISSIONS, sub_id) if sub_id else sub_item
            return {"ok": True, "item": latest, "submission": sub, "already_submitted": True}
        return {"ok": False, "conflict": True, "item": latest, "submission": sub_item, "reason": "concurrent_update"}
    audit.emit_event(actor=identity, action="exams.session.submitted", entity_type="session", entity_id=session_id, summary="Exam submitted", details={"submission_id": sub_item["id"], "percent": score.get("percent")})
    return {"ok": True, "item": sess_item, "submission": sub_item}
