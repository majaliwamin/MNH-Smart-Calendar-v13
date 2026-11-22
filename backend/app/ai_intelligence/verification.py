"""Independent, rule-based verification of timetable answers.

The external model never verifies its own answer. This module extracts factual
claims from the draft and compares them with the authoritative retrieval result.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.ai_intelligence.retrieval import RetrievalContext

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_TIME_RE = re.compile(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b")
_CODE_RE = re.compile(r"\b([A-Z]{2,6}[-\s]?\d{4})\b")
_NO_SESSION_RE = re.compile(
    r"\b(no|zero|nothing|without any)\s+(scheduled\s+)?(sessions?|classes?|lectures?)\b|"
    r"\b(nothing|no\s+activities?)\s+(is|are)?\s*scheduled\b",
    re.I,
)
_VERIFICATION_CLAIM_RE = re.compile(
    r"\b(verified|i checked|i confirmed|database confirms|i have confirmed)\b", re.I,
)
_NEGATION_RE = re.compile(
    r"\b(no|not|isn't|is not|aren't|are not|without|unrecorded|unscheduled|not found|"
    r"no record|not in the timetable)\b",
    re.I,
)


@dataclass
class VerificationResult:
    """Outcome of one independent verification pass."""

    ok: bool
    reasons: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    missing_sessions: list[str] = field(default_factory=list)
    duplicate_sessions: list[str] = field(default_factory=list)
    incorrect_dates: list[str] = field(default_factory=list)
    incorrect_times: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    retrieval_ok: bool = True
    attempts: int = 1
    provider: str = ""
    model: str = ""


@dataclass
class VerificationOutcome:
    """Final answer after zero or more controlled regeneration attempts."""

    answer: str
    verification: VerificationResult
    attempts: int
    regenerated: bool


def _normal(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _code(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _dates(text: str) -> set[str]:
    result = set()
    for year, month, day in _DATE_RE.findall(str(text or "")):
        try:
            result.add(date(int(year), int(month), int(day)).isoformat())
        except ValueError:
            continue
    return result


def _times(text: str) -> set[str]:
    return set(_TIME_RE.findall(str(text or "")))


def _codes(text: str) -> set[str]:
    return {_code(item) for item in _CODE_RE.findall(str(text or "")) if _code(item)}


def _focus_sessions(ctx: RetrievalContext) -> list[dict]:
    """Apply the question's date/week/module filters to retrieved sessions."""
    sessions = list(ctx.sessions)
    filters = ctx.filters or {}
    text = str(ctx.query or "").casefold()

    # An exam-only question is graded against examination records, not against
    # every unrelated teaching session in the same week.
    exam_only = bool(re.search(r"\b(exam|examination|exams)\b", text)) and not bool(re.search(
        r"\b(class|classes|session|sessions|lecture|lectures|timetable|schedule|module|week)\b", text,
    ))
    if exam_only:
        return []
    for recurring in ctx.recurring:
        title = str(recurring.get("title") or "").strip()
        if len(title) >= 4 and title.casefold() in text:
            return [
                item for item in sessions
                if str(item.get("code") or "").casefold() == title.casefold()
                or str(item.get("title") or "").casefold() == title.casefold()
            ]
    wanted_date = str(filters.get("date") or "")
    if wanted_date:
        sessions = [item for item in sessions if item["date"] == wanted_date]
    week_start = str(filters.get("week_start") or filters.get("default_week_start") or "")
    if week_start and not wanted_date:
        try:
            start = date.fromisoformat(week_start)
            end = start + timedelta(days=6)
            sessions = [item for item in sessions if start.isoformat() <= item["date"] <= end.isoformat()]
        except ValueError:
            pass
    weekday = str(filters.get("weekday") or "")
    if weekday and not wanted_date:
        sessions = [item for item in sessions if item["weekday"] == weekday]
    wanted_times = _times(ctx.query)
    if wanted_times:
        sessions = [
            item for item in sessions
            if str(item.get("start")) in wanted_times or str(item.get("end")) in wanted_times
        ]
    wanted_codes = {_code(item) for item in filters.get("codes", []) if _code(item)}
    if wanted_codes:
        sessions = [item for item in sessions if _code(item["code"]) in wanted_codes]
    return sessions


def _identity(session: dict) -> str:
    return str(session.get("code") or session.get("title") or "").strip()


def _mentions(haystack: str, session: dict) -> bool:
    """True when the answer names a retrieved session by code or exact title."""
    folded = haystack.casefold()
    for value in (session.get("code"), session.get("title"), session.get("module_title")):
        text = str(value or "").strip()
        if len(text) >= 3 and text.casefold() in folded:
            return True
    return False


def _count(haystack: str, value: str) -> int:
    text = str(value or "").strip()
    if len(text) < 3:
        return 0
    return len(re.findall(r"(?<!\w)" + re.escape(text) + r"(?!\w)", haystack, flags=re.I))


def _allowed_facts(ctx: RetrievalContext, focus: list[dict]) -> dict:
    dates = _dates(ctx.query) | {item["date"] for item in focus if item.get("date")}
    for exam in ctx.examinations:
        if exam.get("date"):
            dates |= _dates(exam["date"])
    for recurring in ctx.recurring:
        if recurring.get("date"):
            dates |= _dates(recurring["date"])

    times = _times(ctx.query)
    for item in focus:
        times |= _times(item.get("start")) | _times(item.get("end"))
    for exam in ctx.examinations:
        times |= _times(exam.get("time"))
    for recurring in ctx.recurring:
        # Stored recurring times use an en dash; extract both clock values.
        times |= set(re.findall(r"(?:[01]\d|2[0-3]):[0-5]\d", str(recurring.get("time") or "")))

    codes = _codes(ctx.query)
    for item in focus:
        codes.add(_code(item["code"]))
    for module in ctx.modules:
        codes.add(_code(module.get("code")))

    names = set()
    for item in focus:
        if item.get("facilitator"):
            names.add(str(item["facilitator"]).strip().casefold())
    for person in ctx.facilitators:
        if person.get("name"):
            names.add(str(person["name"]).strip().casefold())

    venues = {str(item or "").strip().casefold() for item in ctx.venues if str(item or "").strip()}
    return {"dates": dates, "times": times, "codes": codes, "names": names, "venues": venues}


def verify(answer: str, query: str, ctx: RetrievalContext, attempts: int = 1) -> VerificationResult:
    """Compare a draft with retrieved records using deterministic rules only."""
    text = str(answer or "").strip()
    result = VerificationResult(ok=False, retrieval_ok=bool(ctx.ok), attempts=max(1, int(attempts)))
    if not ctx.ok:
        result.reasons.append("authoritative timetable retrieval did not succeed")
        result.categories.append("retrieval_failure")
        return result
    if not text:
        result.reasons.append("the answer is empty")
        result.categories.append("incomplete_answer")
        return result

    focus = _focus_sessions(ctx)
    allowed = _allowed_facts(ctx, focus)
    folded = text.casefold()
    negating = bool(_NEGATION_RE.search(text))

    # Missing sessions: every session in scope must be represented in the answer.
    for session in focus:
        if not _mentions(text, session):
            label = _identity(session) or session.get("id", "unnamed session")
            result.missing_sessions.append(f"{label} on {session['date']} at {session['start']}")
    if result.missing_sessions:
        result.reasons.append("the answer omitted retrieved scheduled session(s)")
        result.categories.extend(["missed_sessions", "incomplete_answers"])

    # Duplicate sessions: the same retrieved identity appearing more than once.
    for session in focus:
        label = _identity(session)
        if _count(text, label) > 1:
            result.duplicate_sessions.append(f"{label} on {session['date']}")
    if result.duplicate_sessions:
        result.reasons.append("the answer repeats a retrieved session more than once")
        result.categories.append("duplicate_sessions")

    # Dates and times that are neither retrieved nor present in the question.
    for value in sorted(_dates(text) - allowed["dates"]):
        result.incorrect_dates.append(value)
    if result.incorrect_dates:
        result.reasons.append("the answer contains date(s) absent from the retrieved records")
        result.categories.append("incorrect_date_interpretation")

    for value in sorted(_times(text) - allowed["times"]):
        result.incorrect_times.append(value)
    if result.incorrect_times:
        result.reasons.append("the answer contains time(s) absent from the retrieved records")
        result.categories.append("incorrect_session_time")

    # Unsupported entities.
    for value in sorted(_codes(text) - allowed["codes"]):
        if not (negating and value in _codes(ctx.query)):
            result.unsupported.append(f"module code {value}")
    for person in ctx.facilitators:
        name = str(person.get("name") or "").strip()
        if len(name) >= 4 and name.casefold() in folded and name.casefold() not in allowed["names"]:
            result.unsupported.append(f"facilitator {name}")
    for venue in ctx.venues:
        name = str(venue or "").strip()
        if len(name) >= 4 and name.casefold() in folded and name.casefold() not in allowed["venues"]:
            result.unsupported.append(f"venue {name}")
    if result.unsupported:
        result.reasons.append("the answer contains unsupported timetable information")
        result.categories.extend(["fabricated_timetable_information", "incorrect_module_identification"])

    if _NO_SESSION_RE.search(text) and focus:
        result.reasons.append("the answer claims there are no sessions although retrieved sessions exist")
        result.categories.extend(["missed_sessions", "fabricated_timetable_information"])

    if _VERIFICATION_CLAIM_RE.search(text):
        result.reasons.append("the answer claims its own verification")
        result.categories.append("unsupported_verification_claim")

    # Preserve order while removing duplicates.
    result.categories = list(dict.fromkeys(result.categories))
    result.ok = not result.reasons
    return result


def transparent_response(reason: str | None = None) -> str:
    """Return a truthful response that never presents an unverified answer as checked."""
    detail = str(reason or "the independent verification checks did not pass").strip()
    return (
        "I could not verify this timetable answer against the live records. "
        "The check failed because " + detail[:220] +
        ". Please check the timetable directly or rephrase the question."
    )


def _repair_instruction(verification: VerificationResult, ctx: RetrievalContext) -> str:
    reasons = "; ".join(verification.reasons[:6]) or "the answer did not match the records"
    context = ctx.to_prompt_context()[:6000]
    return (
        "Rewrite the previous timetable answer using only the authoritative records below. "
        "Fix these verification failures: " + reasons + ". "
        "Do not invent sessions or claim that you verified the answer. "
        "AUTHORITATIVE RECORDS: " + context
    )


def verify_with_regeneration(
    query: str,
    ctx: RetrievalContext,
    answer: str,
    messages: list[dict],
    generator,
    max_attempts: int = 2,
) -> VerificationOutcome:
    """Verify, then make at most one controlled regeneration per failed pass.

    ``generator`` must be an independent callable taking a message list and
    returning ``(answer, provider, model)`` or a plain answer string.
    """
    verification = verify(answer, query, ctx, attempts=1)
    attempts = 1
    provider, model = "", ""
    while not verification.ok and attempts < max(1, int(max_attempts)):
        repair_messages = list(messages) + [{"role": "user", "content": _repair_instruction(verification, ctx)}]
        try:
            generated = generator(repair_messages)
        except Exception as exc:
            logger.warning("AI timetable regeneration failed category=generator_error detail=%s", type(exc).__name__)
            verification.reasons.append("controlled regeneration could not be completed")
            verification.categories.append("regeneration_failure")
            verification.ok = False
            break
        if isinstance(generated, tuple) and len(generated) >= 2:
            answer = str(generated[0] or "")
            provider = str(generated[1] or "")
            model = str(generated[2] or "") if len(generated) > 2 else ""
        else:
            answer = str(generated or "")
        attempts += 1
        verification = verify(answer, query, ctx, attempts=attempts)
        verification.provider, verification.model = provider, model

    verification.attempts = attempts
    return VerificationOutcome(
        answer=answer if verification.ok else transparent_response(
            verification.reasons[0] if verification.reasons else None
        ),
        verification=verification,
        attempts=attempts,
        regenerated=attempts > 1,
    )
