"""Focused EXAMS workflow, concurrency, audit and backup tests."""
from __future__ import annotations

import copy
import importlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import app.config as config
    import app.database.connection as connection
    import app.main as main
    import app.exams.store as exam_store
    import app.exams.permissions as exam_permissions
    import app.exams.audit as exam_audit
    import app.exams.schemas as exam_schemas
    import app.exams.routes as exam_routes
    import app.api.routes as api_routes
    for module in (
        config, connection, exam_store, exam_permissions, exam_audit,
        exam_schemas, api_routes, exam_routes, main,
    ):
        importlib.reload(module)
    return TestClient(main.app)


def login(client, role="administrator"):
    from app.services import authentication
    token = authentication.create_session(role)
    client.cookies.set("mnh_session", token)
    return token


def seed_exam(client, *, questions=None, **settings):
    questions = questions or []
    created = []
    for question in questions:
        response = client.post("/api/exams/questions", json=question)
        assert response.status_code == 200, response.text
        created.append(response.json()["item"]["id"])
    payload = {
        "title": "Workflow exam",
        "duration_minutes": 10,
        "status": "published",
        "questions": [{"question_id": qid, "order": index} for index, qid in enumerate(created)],
    }
    payload.update(settings)
    response = client.post("/api/exams/exams", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["item"], created


MCQ = {
    "prompt": "2+2?",
    "type": "mcq",
    "options": [{"id": "a", "text": "4"}, {"id": "b", "text": "5"}],
    "correct_option_ids": ["a"],
    "points": 2,
}


def test_duplicate_and_concurrent_submit_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login(client)
    exam, question_ids = seed_exam(client, questions=[MCQ])
    started = client.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()
    session = started["item"]

    def submit(_):
        return client.post(
            f"/api/exams/sessions/{session['id']}/submit",
            json={
                "answers": {question_ids[0]: "a"},
                "client_submit_id": "same-client-submit",
                "expected_updated_at": session["updated_at"],
            },
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(submit, range(4)))
    assert all(response.status_code == 200 for response in responses)
    ids = {response.json()["submission"]["id"] for response in responses}
    assert len(ids) == 1
    from app.exams import store
    assert len(store.list_docs(store.COL_SUBMISSIONS, limit=100)) == 1
    session_doc = store.get_doc(store.COL_SESSIONS, session["id"])
    assert session_doc["state"] == "submitted"
    assert session_doc["submission_id"] in ids


def test_autosave_after_submit_is_ignored_and_keeps_submission(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login(client)
    exam, question_ids = seed_exam(client, questions=[MCQ])
    session = client.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    submitted = client.post(
        f"/api/exams/sessions/{session['id']}/submit",
        json={"answers": {question_ids[0]: "a"}, "client_submit_id": "sub-once"},
    ).json()
    original_answers = submitted["submission"]["answers"]
    later = client.post(
        f"/api/exams/sessions/{session['id']}/autosave",
        json={"answers": {question_ids[0]: "b"}, "client_save_id": "late-save", "seq": 99},
    )
    assert later.status_code == 200
    assert later.json().get("ignored") is True
    from app.exams import store
    assert len(store.list_docs(store.COL_SUBMISSIONS, limit=100)) == 1
    assert store.get_doc(store.COL_SUBMISSIONS, submitted["submission"]["id"])["answers"] == original_answers


def test_grade_conflict_manual_scores_and_release_rules(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login(client)
    essay = {
        "prompt": "Explain photosynthesis",
        "type": "essay",
        "correct_text": "plants make food from light",
        "points": 4,
        "rubric": "Award 1 point per correct concept.",
    }
    exam, question_ids = seed_exam(client, questions=[MCQ, essay])
    candidate = make_client(tmp_path, monkeypatch)
    # executive_dean maps to exam_reviewer: an authenticated candidate with no
    # global grading/management capability, like a real exam taker.
    login(candidate, "executive_dean")
    session = candidate.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    candidate.post(
        f"/api/exams/sessions/{session['id']}/submit",
        json={"answers": {question_ids[0]: "a", question_ids[1]: "a short answer"}, "client_submit_id": "grade-sub"},
    )
    submissions = client.get(f"/api/exams/submissions?exam_id={exam['id']}").json()["items"]
    assert len(submissions) == 1
    submission = submissions[0]
    stale = submission["updated_at"] - 1
    conflict = client.post(
        f"/api/exams/submissions/{submission['id']}/grade",
        json={"percent": 90, "status": "graded", "expected_updated_at": stale},
    )
    assert conflict.status_code == 200
    assert conflict.json()["conflict"] is True
    graded = client.post(
        f"/api/exams/submissions/{submission['id']}/grade",
        json={
            "status": "returned",
            "release": True,
            "question_scores": [
                {"question_id": question_ids[1], "earned_points": 3, "feedback": "Good effort"}
            ],
        },
    )
    assert graded.status_code == 200, graded.text
    score = graded.json()["item"]["score"]
    assert score["earned_points"] == pytest.approx(5)
    # 2 objective points + 3 manually awarded essay points out of 6 total.
    assert score["percent"] == pytest.approx(83.33)
    assert next(d for d in score["details"] if d["question_id"] == question_ids[1])["earned_points"] == 3
    candidate_view = candidate.get(f"/api/exams/submissions/{submission['id']}").json()["item"]
    assert candidate_view["results_released"] is True
    assert candidate_view["score"]["percent"] == pytest.approx(83.33)
    review = client.get(f"/api/exams/submissions/{submission['id']}/review")
    assert review.status_code == 200
    assert review.json()["rubric_notes"][question_ids[1]] == "Award 1 point per correct concept."
    assert candidate.get(f"/api/exams/submissions/{submission['id']}/review").status_code == 403


def test_enrollment_revocation_during_active_session_is_flagged(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login(client)
    exam, _ = seed_exam(client, require_enrollment=True)
    candidate = make_client(tmp_path, monkeypatch)
    login(candidate, "lecturer")
    identity = candidate.get("/api/exams/capabilities").json()["identity"]
    created = client.post(
        "/api/exams/enrollments",
        json={"exam_id": exam["id"], "actor_id": identity["actor_id"], "role": "candidate", "display_name": "Test Candidate"},
    )
    assert created.status_code == 200
    session = candidate.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    enrollments = client.get(f"/api/exams/enrollments?exam_id={exam['id']}").json()["items"]
    deleted = client.delete(f"/api/exams/enrollments/{enrollments[0]['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["active_sessions_flagged"] == [session["id"]]
    after = candidate.get(f"/api/exams/sessions/{session['id']}")
    assert after.status_code == 200
    assert "enrollment_revoked" in after.json()["item"]["flags"]
    events = client.get("/api/exams/audit?action=exams.session.enrollment_revoked").json()["items"]
    assert events and events[0]["session_id"] == session["id"]


def test_audit_chain_is_append_only_and_verifiable(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login(client)
    exam, _ = seed_exam(client)
    events = client.get("/api/exams/audit?limit=50").json()["items"]
    assert events
    assert events[0]["event_hash"]
    assert events[0]["action"]
    assert client.get("/api/exams/audit/verify").json()["ok"] is True
    from app.database.connection import database
    with database() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE exams_audit_ledger SET summary='tampered' WHERE seq=1")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM exams_audit_ledger WHERE seq=1")


def test_invigilation_signals_actions_and_permissions(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login(client)
    exam, _ = seed_exam(client)
    candidate = make_client(tmp_path, monkeypatch)
    login(candidate, "lecturer")
    session = candidate.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    event = candidate.post(
        f"/api/exams/sessions/{session['id']}/events",
        json={"event_type": "tab_hidden", "detail": "switched tab", "client_event_id": "evt-1"},
    )
    assert event.status_code == 200
    duplicate = candidate.post(
        f"/api/exams/sessions/{session['id']}/events",
        json={"event_type": "tab_hidden", "detail": "switched tab", "client_event_id": "evt-1"},
    )
    assert duplicate.json()["duplicate"] is True
    monitor = client.get(f"/api/exams/sessions/monitor?exam_id={exam['id']}").json()
    row = next(item for item in monitor["items"] if item["id"] == session["id"])
    assert "answers" not in row
    assert "suspicious:tab_hidden" in row["flags"]
    assert row["time_remaining_ms"] > 0
    assert monitor["mode"] == "activity_signals_only"
    assert candidate.post(
        f"/api/exams/sessions/{session['id']}/actions",
        json={"action": "extend_time", "minutes": 5},
    ).status_code == 403
    extended = client.post(
        f"/api/exams/sessions/{session['id']}/actions",
        json={"action": "extend_time", "minutes": 5, "reason": "connectivity"},
    )
    assert extended.status_code == 200
    assert extended.json()["item"]["extension_ms"] == 300_000
    paused = client.post(f"/api/exams/sessions/{session['id']}/actions", json={"action": "pause", "reason": "incident"})
    assert paused.status_code == 200
    resumed = client.post(f"/api/exams/sessions/{session['id']}/actions", json={"action": "resume"})
    assert resumed.status_code == 200
    noted = client.post(
        f"/api/exams/sessions/{session['id']}/actions",
        json={"action": "note", "reason": "follow up with candidate"},
    )
    assert noted.json()["item"]["notes"][-1]["note"] == "follow up with candidate"
    actions = client.get("/api/exams/audit?action=exams.session.action.extend_time").json()["items"]
    assert actions


def test_analytics_metrics_and_csv_export(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login(client)
    exam, question_ids = seed_exam(client, questions=[MCQ], pass_mark_percent=50)
    candidate = make_client(tmp_path, monkeypatch)
    login(candidate, "lecturer")
    session = candidate.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    candidate.post(
        f"/api/exams/sessions/{session['id']}/submit",
        json={"answers": {question_ids[0]: "a"}, "client_submit_id": "analytics-sub"},
    )
    report = client.get("/api/exams/analytics").json()
    row = next(item for item in report["by_exam"] if item["exam_id"] == exam["id"])
    assert row["completion_rate"] == 1.0
    assert row["average_score"] == pytest.approx(100)
    assert row["median_score"] == pytest.approx(100)
    assert row["pass_rate"] == 1.0
    assert report["attempt_timeline"]
    stats = {item["question_id"]: item for item in row["question_stats"]}
    assert stats[question_ids[0]]["difficulty"] == 1.0
    assert "discrimination" in stats[question_ids[0]]
    csv_response = client.get("/api/exams/analytics?format=csv")
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "completion_rate" in csv_response.text
    guest = make_client(tmp_path, monkeypatch)
    assert guest.get("/api/exams/analytics").status_code == 403


def test_exams_backup_integrity_and_conflicts(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login(client)
    exam, _ = seed_exam(client)
    backup = client.get("/api/exams/backup")
    assert backup.status_code == 200
    payload = backup.json()
    assert payload["schema_version"] == "mnh-exams-backup-v1"
    assert payload["integrity"]["sha256"]
    guest = make_client(tmp_path, monkeypatch)
    assert guest.get("/api/exams/backup").status_code == 403
    assert guest.post("/api/exams/restore", json=payload).status_code == 403

    tampered = copy.deepcopy(payload)
    tampered["documents"][0]["data"]["title"] = "Changed after export"
    assert client.post("/api/exams/restore", json=tampered).status_code == 400
    conflict = client.post("/api/exams/restore", json=payload)
    assert conflict.status_code == 409
    assert "conflicts" in conflict.json()["error"]
    overwrite = copy.deepcopy(payload)
    overwrite["overwrite_conflicts"] = True
    restored = client.post("/api/exams/restore", json=overwrite)
    assert restored.status_code == 200, restored.text
    assert restored.json()["restored"] == len(payload["documents"])


def test_randomisation_uses_presentation_without_leaking_answers(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login(client)
    questions = []
    for index, correct in enumerate(("a", "b", "a")):
        questions.append({
            "prompt": f"Question {index}",
            "type": "mcq",
            "options": [{"id": "a", "text": "yes"}, {"id": "b", "text": "no"}],
            "correct_option_ids": [correct],
            "points": 1,
        })
    exam, question_ids = seed_exam(client, questions=questions, shuffle_questions=True, shuffle_options=True)
    candidate = make_client(tmp_path, monkeypatch)
    login(candidate, "lecturer")
    session = candidate.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    presentation = session["presentation"]
    assert set(presentation["question_order"]) == set(question_ids)
    view = candidate.get(f"/api/exams/sessions/{session['id']}")
    assert view.status_code == 200
    questions_view = view.json()["exam"]["question_items"]
    assert [item["id"] for item in questions_view] == presentation["question_order"]
    assert all("correct_option_ids" not in item for item in questions_view)
    correct_map = dict(zip(question_ids, ("a", "b", "a")))
    submitted = candidate.post(
        f"/api/exams/sessions/{session['id']}/submit",
        json={"answers": correct_map, "client_submit_id": "randomised-sub"},
    )
    assert submitted.json()["submission"]["score"]["percent"] == pytest.approx(100)


def test_expired_session_records_late_submit_and_no_submission(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login(client)
    exam, question_ids = seed_exam(client, questions=[MCQ], duration_minutes=1)
    session = client.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    from app.exams import store
    monkeypatch.setattr(store, "now_ms", lambda: int(session["expires_at"]) + 1000)
    response = client.post(
        f"/api/exams/sessions/{session['id']}/submit",
        json={"answers": {question_ids[0]: "a"}, "client_submit_id": "late"},
    )
    assert response.status_code == 409
    assert len(store.list_docs(store.COL_SUBMISSIONS, limit=100)) == 0
    late_events = client.get("/api/exams/audit?action=exams.session.late_submit").json()["items"]
    assert late_events and late_events[0]["session_id"] == session["id"]
