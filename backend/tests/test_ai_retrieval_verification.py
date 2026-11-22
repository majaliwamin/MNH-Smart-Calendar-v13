"""Stage 1: authoritative retrieval and independent timetable verification."""
import json
from datetime import datetime as real_datetime

import pytest

from app.ai_intelligence import retrieval, verification


class Row(dict):
    pass


class FrozenDatetime(real_datetime):
    @classmethod
    def now(cls, tz=None):
        return real_datetime(2026, 11, 20, 9, 0, tzinfo=tz)


def _rows():
    return [
        Row(col="cells", id="session-mon-am", data=json.dumps({
            "dayIndex": 0, "weekStart": "2026-11-16", "startTime": "08:00",
            "endTime": "10:00", "code": "PNIM-8100",
            "title": "Pregnancy and Neonatal Immunology", "status": "scheduled",
        }), updated_at=1795000000000),
        Row(col="cells", id="session-fri-am", data=json.dumps({
            "dayIndex": 4, "weekStart": "2026-11-16", "startTime": "08:00",
            "endTime": "10:00", "code": "PNIM-8100",
            "title": "Pregnancy and Neonatal Immunology", "status": "scheduled",
        }), updated_at=1795000000000),
        Row(col="cells", id="session-fri-pm", data=json.dumps({
            "dayIndex": 4, "weekStart": "2026-11-16", "startTime": "13:30",
            "endTime": "15:30", "code": "Library", "title": "Library Session",
            "status": "scheduled",
        }), updated_at=1795000000000),
        Row(col="modules", id="PNIM-8100", data=json.dumps({
            "title": "Pregnancy and Neonatal Immunology", "facilitator": "D Mzinza",
        }), updated_at=1795000000000),
        Row(col="modules", id="Library", data=json.dumps({
            "title": "Library Session", "facilitator": "Not specified",
        }), updated_at=1795000000000),
        Row(col="facilitators", id="fac-mzinza", data=json.dumps({
            "name": "D Mzinza", "title": "Dr", "department": "MNH",
            "email": "private@example.test", "phone": "265999000000",
        }), updated_at=1795000000000),
        Row(col="examinations", id="exam-2026-11-23", data=json.dumps({
            "title": "Examination", "date": "2026-11-23", "time": "09:00",
            "venue": "Exam Hall", "notes": "Bring pens",
        }), updated_at=1795000000000),
        Row(col="recurring", id="journal-club", data=json.dumps({
            "title": "Journal Club", "day": "Tuesday", "time": "13:00–14:00",
            "venue": "Seminar Room", "enabled": True,
        }), updated_at=1795000000000),
    ]


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=()):
        captured = list(self.rows)
        return type("Rows", (), {"fetchall": lambda self, captured=captured: captured})()


@pytest.fixture
def context(monkeypatch):
    monkeypatch.setattr(retrieval, "datetime", FrozenDatetime)
    monkeypatch.setattr(retrieval, "database", lambda: FakeConnection(_rows()))
    return retrieval.retrieve_authoritative_context("What is on Friday 2026-11-20?")


def test_question_routing_triggers_retrieval():
    assert retrieval.is_timetable_question("What classes are on Friday?")
    assert retrieval.is_timetable_question("When is the exam?")
    assert not retrieval.is_timetable_question("Who won the match?")


def test_retrieval_returns_multiple_sessions_for_one_day(context):
    assert context.ok
    friday = [item for item in context.sessions if item["date"] == "2026-11-20"]
    assert len(friday) == 2
    assert {item["code"] for item in friday} == {"PNIM-8100", "Library"}
    assert any(item["start"] == "13:30" and item["end"] == "15:30" for item in friday)
    assert any(person["name"] == "D Mzinza" for person in context.facilitators)
    assert "Exam Hall" in context.venues
    assert "Journal Club" in [item["title"] for item in context.recurring]
    assert "private@example.test" not in context.to_prompt_context()


def test_retrieval_confirms_empty_day_without_inventing_sessions(monkeypatch):
    monkeypatch.setattr(retrieval, "datetime", FrozenDatetime)
    monkeypatch.setattr(retrieval, "database", lambda: FakeConnection(_rows()))
    ctx = retrieval.retrieve_authoritative_context("What is on 2026-11-22?")
    assert ctx.ok
    assert not [item for item in ctx.sessions if item["date"] == "2026-11-22"]
    answer = "There are no sessions on 2026-11-22."
    result = verification.verify(answer, "What is on 2026-11-22?", ctx)
    assert result.ok, result.reasons


def test_database_failure_never_becomes_an_empty_timetable_claim(monkeypatch):
    def broken_database():
        raise OSError("database unavailable")

    monkeypatch.setattr(retrieval, "datetime", FrozenDatetime)
    monkeypatch.setattr(retrieval, "database", broken_database)
    ctx = retrieval.retrieve_authoritative_context("What classes are on Friday?")
    assert not ctx.ok
    result = verification.verify("There are no classes on Friday.", "What classes are on Friday?", ctx)
    assert not result.ok
    assert "retrieval_failure" in result.categories
    assert "did not succeed" in verification.transparent_response(result.reasons[0])


def test_recurring_activity_is_retrieved_as_authoritative_record(context):
    club = next(item for item in context.recurring if item["id"] == "journal-club")
    assert club["day"] == "Tuesday"
    assert club["time"] == "13:00–14:00"
    assert club["enabled"] is True


def test_verification_accepts_grounded_answer(context):
    answer = (
        "On 2026-11-20, PNIM-8100 runs from 08:00 to 10:00 and "
        "Library Session runs from 13:30 to 15:30."
    )
    result = verification.verify(answer, context.query, context)
    assert result.ok, result.reasons


def test_verification_detects_omitted_session(context):
    answer = "On 2026-11-20, PNIM-8100 runs from 08:00 to 10:00."
    result = verification.verify(answer, context.query, context)
    assert not result.ok
    assert "missed_sessions" in result.categories
    assert any("Library" in item for item in result.missing_sessions)


def test_verification_detects_incorrect_date(context):
    answer = (
        "On 2026-11-21, PNIM-8100 runs from 08:00 to 10:00 and "
        "Library Session runs from 13:30 to 15:30."
    )
    result = verification.verify(answer, context.query, context)
    assert not result.ok
    assert result.incorrect_dates == ["2026-11-21"]
    assert "incorrect_date_interpretation" in result.categories


def test_verification_detects_invented_session(context):
    answer = (
        "On 2026-11-20, PNIM-8100 runs from 08:00 to 10:00, "
        "Library Session runs from 13:30 to 15:30 and STAT 9999 runs at 16:00."
    )
    result = verification.verify(answer, context.query, context)
    assert not result.ok
    assert any("stat9999" in item.casefold() for item in result.unsupported)
    assert "fabricated_timetable_information" in result.categories


def test_verification_detects_duplicate_session(context):
    answer = (
        "On 2026-11-20, PNIM-8100 runs from 08:00 to 10:00. "
        "PNIM-8100 is also listed at 08:00. Library Session runs at 13:30 to 15:30."
    )
    result = verification.verify(answer, context.query, context)
    assert not result.ok
    assert result.duplicate_sessions
    assert "duplicate_sessions" in result.categories


def test_controlled_regeneration_uses_independent_verification(context):
    bad = "On 2026-11-20, PNIM-8100 runs from 08:00 to 10:00."
    good = (
        "On 2026-11-20, PNIM-8100 runs from 08:00 to 10:00 and "
        "Library Session runs from 13:30 to 15:30."
    )
    calls = []

    def generator(messages):
        calls.append(messages[-1]["content"])
        return good, "test-provider", "test-model"

    outcome = verification.verify_with_regeneration(
        context.query, context, bad,
        [{"role": "user", "content": context.query}], generator,
    )
    assert outcome.ok if hasattr(outcome, "ok") else outcome.verification.ok
    assert outcome.attempts == 2
    assert outcome.regenerated
    assert "Fix these verification failures" in calls[0]


def test_regeneration_failure_returns_transparent_response(context):
    def generator(messages):
        raise OSError("provider offline")

    outcome = verification.verify_with_regeneration(
        context.query, context, "Bad answer",
        [{"role": "user", "content": context.query}], generator,
    )
    assert not outcome.verification.ok
    assert "could not verify" in outcome.answer
    assert "regeneration_failure" in outcome.verification.categories
