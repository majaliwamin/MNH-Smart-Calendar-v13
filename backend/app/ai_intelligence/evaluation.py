"""Daily, database-grounded evaluation with independently computed answers."""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ai_intelligence import service
from app.ai_intelligence.retrieval import retrieve_authoritative_context
from app.ai_intelligence.verification import _codes, _dates, _times
from app.config import TIMEZONE
from app.database.connection import database

logger = logging.getLogger(__name__)

COL_EVALUATIONS = "ai_evaluations"
META_KEY = "ai_last_daily_evaluation"
MAX_QUESTIONS = 5


def _today() -> str:
    return datetime.now(ZoneInfo(TIMEZONE)).date().isoformat()


def _stamp() -> str:
    return datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")


def _questions_from_records(ctx) -> list[dict]:
    """Build questions and expected answers directly from authoritative records."""
    if not ctx.ok:
        return []
    default_week = str((ctx.filters or {}).get("default_week_start") or "")
    sessions = [item for item in ctx.sessions if not default_week or item.get("week_start") == default_week]
    questions = []
    for item in sessions[:MAX_QUESTIONS]:
        label = str(item.get("code") or item.get("title") or "session")
        questions.append({
            "question": f"What is scheduled on {item['weekday']} {item['date']} at {item['start']}?",
            "expected": f"{label} ({item['title']}) runs from {item['start']} to {item['end']} on {item['date']}.",
            "category": "timetable_session",
            "entity": f"{item['date']} {label}",
        })
    for item in ctx.recurring[:2]:
        if not item.get("time") or item.get("enabled") is False:
            continue
        questions.append({
            "question": f"When does {item['title']} take place each week?",
            "expected": f"{item['title']} is scheduled for {item['day']} at {item['time']}.",
            "category": "recurring_activity",
            "entity": item["title"],
        })
    for item in ctx.examinations[:1]:
        if not item.get("date"):
            continue
        questions.append({
            "question": f"When is the {item['title']} scheduled?",
            "expected": (
                f"{item['title']} is scheduled for {item['date']}"
                + (f" at {item['time']}" if item.get("time") else "") + "."
            ),
            "category": "examination",
            "entity": item["date"],
        })
    return questions[:MAX_QUESTIONS]


def _expected_matched(answer: str, expected: str) -> bool:
    """Compare factual tokens without requiring identical wording."""
    actual = str(answer or "").casefold()
    wanted = str(expected or "")
    checks = []
    checks.extend(_dates(wanted))
    checks.extend(_times(wanted))
    checks.extend(_codes(wanted))
    for token in ("journal club", "seminar in mnh", "examination"):
        if token in wanted.casefold():
            checks.append(token)
    if not checks:
        return bool(actual.strip())
    compact_actual = re.sub(r"[^a-z0-9]", "", actual)
    missing = []
    for item in checks:
        token = str(item).casefold()
        if token in actual:
            continue
        compact = re.sub(r"[^a-z0-9]", "", token)
        if compact and compact in compact_actual:
            continue
        missing.append(item)
    return not missing


def _save_trend(trend: dict) -> None:
    with database() as db:
        db.execute(
            "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            (COL_EVALUATIONS, trend["date"], json.dumps(trend, ensure_ascii=False), int(datetime.now().timestamp() * 1000)),
        )
        db.execute("INSERT OR REPLACE INTO app_meta(key,value) VALUES(?,?)", (META_KEY, trend["date"]))


def run_evaluation(responder=None) -> dict:
    """Run one evaluation pass against the real retrieval/generation pipeline."""
    answer_fn = responder or service.answer_timetable_question
    ctx = retrieve_authoritative_context("timetable evaluation")
    questions = _questions_from_records(ctx)
    results = []
    for item in questions:
        try:
            outcome = answer_fn(item["question"], response_language="EN")
        except Exception as exc:
            logger.warning("AI evaluation turn failed category=responder_error detail=%s", type(exc).__name__)
            outcome = {
                "answer": "", "provider": "error", "model": "none",
                "verification": {"ok": False, "categories": ["responder_failure"]},
            }
        verification = outcome.get("verification", {}) if isinstance(outcome, dict) else {}
        matched = _expected_matched(outcome.get("answer", ""), item["expected"])
        passed = bool(verification.get("ok") and matched)
        results.append({
            "question": item["question"],
            "expected": item["expected"],
            "actual": str(outcome.get("answer", ""))[:1200],
            "category": item["category"],
            "entity": item["entity"][:200],
            "provider": str(outcome.get("provider", ""))[:80],
            "verification_ok": bool(verification.get("ok")),
            "expected_matched": matched,
            "passed": passed,
            "attempts": int(outcome.get("attempts", verification.get("attempts", 1)) or 1),
        })

    passed = sum(1 for item in results if item["passed"])
    trend = {
        "date": _today(),
        "generated_at": _stamp(),
        "retrieval_ok": bool(ctx.ok),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 4) if results else 0.0,
        "average_attempts": round(
            sum(item["attempts"] for item in results) / len(results), 2
        ) if results else 0.0,
        "categories": dict(Counter(item["category"] for item in results)),
        "failures": dict(Counter(
            item["category"] for item in results if not item["passed"]
        )),
        "questions": results[:MAX_QUESTIONS],
    }
    _save_trend(trend)
    logger.info(
        "AI daily evaluation completed category=evaluation date=%s passed=%s total=%s",
        trend["date"], passed, len(results),
    )
    return trend


def maybe_run_daily(responder=None) -> dict | None:
    """Run at most one evaluation per calendar day."""
    today = _today()
    with database() as db:
        row = db.execute("SELECT value FROM app_meta WHERE key=?", (META_KEY,)).fetchone()
    if row and str(row["value"]) == today:
        return None
    return run_evaluation(responder=responder)


def recent_trends(limit: int = 30) -> list[dict]:
    with database() as db:
        rows = db.execute(
            "SELECT data FROM docs WHERE col=? ORDER BY updated_at DESC LIMIT ?",
            (COL_EVALUATIONS, max(1, min(int(limit), 90))),
        ).fetchall()
    result = []
    for row in rows:
        try:
            value = json.loads(row["data"])
            if isinstance(value, dict):
                result.append(value)
        except (TypeError, json.JSONDecodeError):
            continue
    return result
