"""End-to-end tests for the continuous-learning timetable intelligence."""
import json
from datetime import datetime as real_datetime

import pytest
from fastapi.testclient import TestClient

from app.ai_intelligence import corrections, dataset, evaluation, learning, routes, service
from app.ai_intelligence.retrieval import retrieve_authoritative_context
from app.database import connection
from app.database.connection import database
from app.main import app


class FrozenDatetime(real_datetime):
    @classmethod
    def now(cls, tz=None):
        return real_datetime(2026, 11, 20, 9, 0, tzinfo=tz)


GOOD_ANSWER = (
    "On 2026-11-20, PNIM-8100 runs from 08:00 to 10:00 and "
    "Library Session runs from 13:30 to 15:30."
)
BAD_ANSWER = "On 2026-11-20, PNIM-8100 runs from 08:00 to 10:00."


@pytest.fixture
def ai_db(monkeypatch, tmp_path):
    db_path = tmp_path / "database" / "calendar.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(connection, "DATABASE_PATH", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr(
        __import__("app.ai_intelligence.retrieval", fromlist=["datetime"]),
        "datetime", FrozenDatetime,
    )
    with database() as db:
        now = int(real_datetime.now().timestamp() * 1000)
        cells = [
            ("session-mon", 0, "08:00", "10:00", "PNIM-8100", "Pregnancy and Neonatal Immunology"),
            ("session-fri-am", 4, "08:00", "10:00", "PNIM-8100", "Pregnancy and Neonatal Immunology"),
            ("session-fri-pm", 4, "13:30", "15:30", "Library", "Library Session"),
        ]
        for item_id, day, start, end, code, title in cells:
            db.execute(
                "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
                ("cells", item_id, json.dumps({
                    "dayIndex": day, "weekStart": "2026-11-16", "startTime": start,
                    "endTime": end, "code": code, "title": title, "status": "scheduled",
                }), now),
            )
        db.execute(
            "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            ("modules", "Library", json.dumps({
                "title": "Library Session", "facilitator": "Not specified"
            }), now),
        )
    routes._RATE_BUCKETS.clear()
    return db_path


def _client():
    return TestClient(app)


def _admin_headers(monkeypatch):
    monkeypatch.setenv("MNH_AI_ADMIN_TOKEN", "test-admin-token")
    return {"X-MNH-AI-Admin-Token": "test-admin-token"}


# ---- retrieval, generation and independent verification --------------------

def test_grounded_service_reuses_provider_and_verifies_answer(ai_db):
    calls = []

    def completer(messages):
        calls.append(messages)
        return GOOD_ANSWER, "cloudflare", "test-model"

    result = service.answer_timetable_question(
        "What is on Friday 2026-11-20?", completer=completer
    )
    assert result["retrieval_ok"] is True
    assert result["verification"]["ok"] is True
    assert result["answer"] == GOOD_ANSWER
    assert result["provider"] == "cloudflare"
    assert calls and "AUTHORITATIVE TIMETABLE RECORDS" in calls[0][0]["content"]


def test_service_fails_transparently_when_database_is_unavailable(ai_db, monkeypatch):
    def broken():
        raise OSError("database unavailable")

    monkeypatch.setattr(
        __import__("app.ai_intelligence.retrieval", fromlist=["database"]),
        "database", broken,
    )
    result = service.answer_timetable_question("What classes are on Friday?")
    assert result["retrieval_ok"] is False
    assert "could not verify" in result["answer"].casefold()
    assert "retrieval_failure" in result["verification"]["categories"]


def test_service_fails_transparently_when_provider_is_unavailable(ai_db):
    def completer(messages):
        raise OSError("provider offline")

    result = service.answer_timetable_question(
        "What is on Friday 2026-11-20?", completer=completer
    )
    assert result["retrieval_ok"] is True
    assert "could not verify" in result["answer"].casefold()
    assert result["verification"]["categories"] == ["provider_failure"]


def test_controlled_regeneration_repairs_an_incomplete_answer(ai_db):
    answers = [BAD_ANSWER, GOOD_ANSWER]

    def completer(messages):
        return answers.pop(0), "cloudflare", "test-model"

    result = service.answer_timetable_question(
        "What is on Friday 2026-11-20?", completer=completer
    )
    assert result["verification"]["ok"] is True
    assert result["attempts"] == 2
    assert result["regenerated"] is True


# ---- correction memory, relevance, recurrence and dataset ------------------

def test_verified_correction_becomes_one_relevant_example(ai_db):
    first = corrections.submit_feedback(
        "What is on Friday 2026-11-20?", BAD_ANSWER, GOOD_ANSWER,
        user_id="student-1", category="missed_sessions", date_or_entity="2026-11-20",
    )
    assert first["verification_status"] == "verified"
    assert first["learning_status"] == "accepted"
    assert first["duplicate"] is False

    duplicate = corrections.submit_feedback(
        "What is on Friday 2026-11-20?", BAD_ANSWER, GOOD_ANSWER,
        user_id="student-1", category="missed_sessions", date_or_entity="2026-11-20",
    )
    assert duplicate["duplicate"] is True
    assert duplicate["submission_count"] == 2

    records = corrections._read_all(corrections.COL_FEEDBACK)
    examples = corrections._read_all(corrections.COL_EXAMPLES)
    assert len(records) == 1
    assert len(examples) == 1
    assert records[0]["verified_facts"]["retrieval_ok"] is True
    assert records[0]["created_at"]
    assert "query" in records[0] and "original_response" in records[0]

    relevant = learning.relevant_examples("What is on Friday 2026-11-20?")
    assert len(relevant) == 1
    assert relevant[0]["verification_status"] == "verified"
    assert learning.relevant_examples("Who won the football match?") == []


def test_unverified_correction_is_retained_but_never_used_as_an_example(ai_db):
    result = corrections.submit_feedback(
        "What is on Friday 2026-11-20?", BAD_ANSWER,
        "There are no sessions on 2026-11-20.",
        user_id="student-2", category="missed_sessions",
    )
    assert result["verification_status"] == "unverified"
    assert result["learning_status"] == "rejected_unverified"
    assert corrections._read_all(corrections.COL_EXAMPLES) == []
    assert "verified" not in dataset.export_jsonl()


def test_repeated_corrections_are_flagged_as_recurring(ai_db):
    for index in range(3):
        result = corrections.submit_feedback(
            "What is on Friday 2026-11-20?", f"Wrong answer number {index}.",
            GOOD_ANSWER, user_id=f"student-{index}",
            category="missed_sessions", date_or_entity="2026-11-20",
        )
    assert result["recurring"] is True
    assert result["recurrence_count"] == 3
    assert any("recurred" in rule for rule in learning.operational_rules())


def test_dataset_jsonl_contains_required_fields_only_for_verified_records(ai_db):
    corrections.submit_feedback(
        "What is on Friday 2026-11-20?", BAD_ANSWER, GOOD_ANSWER,
        user_id="student-3", category="missed_sessions",
    )
    lines = [line for line in dataset.export_jsonl().splitlines() if line.strip()]
    assert len(lines) == 1
    item = json.loads(lines[0])
    assert set(item) == {
        "question", "context", "incorrect_behaviour",
        "expected_response", "category", "verification_status",
    }
    assert item["verification_status"] == "verified"
    assert item["expected_response"] == GOOD_ANSWER


def test_sensitive_corrections_are_redacted(ai_db):
    corrections.submit_feedback(
        "What is on Friday 2026-11-20?",
        "api_key=super-secret-value",
        GOOD_ANSWER + " Bearer abcdefghijklmnop",
        user_id="student-4",
    )
    stored = json.dumps(corrections._read_all(corrections.COL_FEEDBACK))
    assert "super-secret-value" not in stored
    assert "abcdefghijklmnop" not in stored
    assert "redacted" in stored


# ---- daily evaluation -------------------------------------------------------

def test_daily_evaluation_generates_questions_and_stores_trends(ai_db, monkeypatch):
    ctx = retrieve_authoritative_context("timetable evaluation")
    questions = evaluation._questions_from_records(ctx)
    assert questions
    expected_by_question = {item["question"]: item["expected"] for item in questions}

    def responder(question, response_language="EN"):
        return {
            "answer": expected_by_question[question],
            "provider": "test-provider", "model": "test-model",
            "verification": {"ok": True, "attempts": 1}, "attempts": 1,
        }

    trend = evaluation.run_evaluation(responder=responder)
    assert trend["retrieval_ok"] is True
    assert trend["total"] == len(questions)
    assert trend["passed"] == len(questions)
    assert trend["pass_rate"] == 1.0
    assert all(item["passed"] for item in trend["questions"])

    stored = evaluation.recent_trends(1)
    assert stored and stored[0]["date"] == trend["date"]
    assert evaluation.maybe_run_daily(responder=responder) is None

    def failing_responder(question, response_language="EN"):
        return {
            "answer": "There are no sessions.", "provider": "test", "model": "test",
            "verification": {"ok": False, "attempts": 1}, "attempts": 1,
        }

    forced = evaluation.run_evaluation(responder=failing_responder)
    assert forced["failed"] == forced["total"]
    assert forced["pass_rate"] == 0.0


def test_evaluation_handles_provider_outage_without_raising(ai_db):
    def failing(question, response_language="EN"):
        return {
            "answer": "I could not verify this timetable answer.",
            "provider": "provider-error", "model": "none",
            "verification": {"ok": False, "categories": ["provider_failure"], "attempts": 0},
            "attempts": 0,
        }

    trend = evaluation.run_evaluation(responder=failing)
    assert trend["retrieval_ok"] is True
    assert trend["failed"] == trend["total"]
    assert trend["total"] > 0


# ---- API surface ------------------------------------------------------------

def test_ai_health_reports_status_without_credentials(ai_db):
    response = _client().get("/ai/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["build"] == "2026.11.26-exams-hardening-v1"
    assert "provider_count" in body
    assert "api_key" not in response.text


def test_feedback_endpoint_requires_crara_identity(ai_db):
    response = _client().post("/ai/feedback", json={
        "query": "What is on Friday 2026-11-20?",
        "original_response": BAD_ANSWER,
        "correction": GOOD_ANSWER,
    })
    assert response.status_code == 401


def test_management_endpoints_require_authorisation(ai_db):
    client = _client()
    assert client.get("/api/ai/performance").status_code == 403
    assert client.post("/api/ai/evaluate", json={}).status_code == 403
    assert client.get("/ai/retrain-dataset").status_code == 403


def test_feedback_performance_evaluate_and_dataset_endpoints(ai_db, monkeypatch):
    client = _client()
    client.cookies.set("cara_guest", "guest_test1234")
    headers = _admin_headers(monkeypatch)

    feedback = client.post("/api/ai/feedback", headers={"Content-Type": "application/json"}, json={
        "query": "What is on Friday 2026-11-20?",
        "original_response": BAD_ANSWER,
        "correction": GOOD_ANSWER,
        "category": "missed_sessions",
        "date_or_entity": "2026-11-20",
    })
    assert feedback.status_code == 200, feedback.text
    assert feedback.json()["learning_status"] == "accepted"

    performance = client.get("/ai/performance", headers=headers)
    assert performance.status_code == 200
    assert performance.json()["corrections"]["learning_examples"] == 1

    dummy_trend = {"date": "2026-11-23", "total": 2, "passed": 2, "pass_rate": 1.0}
    monkeypatch.setattr(evaluation, "run_evaluation", lambda: dummy_trend)
    evaluated = client.post("/api/ai/evaluate", headers=headers, json={"force": True})
    assert evaluated.status_code == 200
    assert evaluated.json()["trend"] == dummy_trend

    exported = client.get("/api/ai/retrain-dataset", headers=headers)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/x-ndjson")
    assert json.loads(exported.text.splitlines()[0])["expected_response"] == GOOD_ANSWER
