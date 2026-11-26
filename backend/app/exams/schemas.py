"""Pydantic schemas for the EXAMS module."""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ExamStatus = Literal["draft", "published", "archived"]
QuestionType = Literal["mcq", "multiple_select", "short_text", "essay", "true_false"]
EnrollmentRole = Literal["candidate", "invigilator", "grader"]
ResultRelease = Literal["immediate", "on_return", "scheduled", "never"]
SessionEventType = Literal[
    "tab_hidden", "tab_visible", "focus_lost", "focus_gained",
    "offline", "reconnected", "save_conflict", "late_submit",
]
InvigilationAction = Literal["extend_time", "pause", "resume", "flag", "invalidate", "note"]

MAX_ANSWER_KEYS = 500
MAX_ANSWER_VALUE_CHARS = 4000
MAX_ANSWER_PAYLOAD_CHARS = 50000


def _normalise_answers(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("answers must be an object")
    if len(value) > MAX_ANSWER_KEYS:
        raise ValueError(f"answers may contain at most {MAX_ANSWER_KEYS} entries")
    out: dict[str, Any] = {}
    total = 0
    for key, answer in value.items():
        clean_key = str(key).strip()
        if not clean_key or len(clean_key) > 120:
            raise ValueError("answer keys must be non-empty and at most 120 characters")
        if isinstance(answer, list):
            if len(answer) > 200:
                raise ValueError("answer lists may contain at most 200 entries")
            clean: Any = [str(item)[:120] for item in answer]
        elif isinstance(answer, (str, int, float, bool)) or answer is None:
            clean = str(answer)[:MAX_ANSWER_VALUE_CHARS]
        else:
            clean = json.dumps(answer, ensure_ascii=False, default=str)[:MAX_ANSWER_VALUE_CHARS]
        total += len(str(clean))
        if total > MAX_ANSWER_PAYLOAD_CHARS:
            raise ValueError("answers payload is too large")
        out[clean_key] = clean
    return out


class AnswerPayloadMixin(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)

    @field_validator("answers")
    @classmethod
    def _validate_answers(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _normalise_answers(value)


class QuestionOption(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=1000)


class QuestionUpsert(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    type: QuestionType = "mcq"
    options: list[QuestionOption] = Field(default_factory=list, max_length=100)
    correct_option_ids: list[str] = Field(default_factory=list, max_length=100)
    correct_text: str = Field(default="", max_length=4000)
    points: float = Field(default=1.0, ge=0, le=1000)
    explanation: str = Field(default="", max_length=4000)
    rubric: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=40)
    active: bool = True

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, value: list[str]) -> list[str]:
        return [str(item).strip()[:80] for item in value if str(item).strip()]

    @field_validator("correct_option_ids")
    @classmethod
    def _validate_correct_ids(cls, value: list[str]) -> list[str]:
        return [str(item).strip()[:40] for item in value if str(item).strip()]


class ExamQuestionLink(BaseModel):
    question_id: str = Field(min_length=1, max_length=120)
    points: float | None = Field(default=None, ge=0, le=1000)
    order: int = Field(default=0, ge=0, le=10000)


class ExamUpsert(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    course_code: str = Field(default="", max_length=80)
    duration_minutes: int = Field(default=60, ge=1, le=600)
    status: ExamStatus = "draft"
    instructions: str = Field(default="", max_length=8000)
    pass_mark_percent: float = Field(default=50.0, ge=0, le=100)
    max_attempts: int = Field(default=1, ge=1, le=10)
    shuffle_questions: bool = False
    shuffle_options: bool = False
    questions: list[ExamQuestionLink] = Field(default_factory=list, max_length=500)
    require_enrollment: bool = False
    available_from: int | None = Field(default=None, ge=0)
    available_until: int | None = Field(default=None, ge=0)
    results_release: ResultRelease = "on_return"
    results_release_at: int | None = Field(default=None, ge=0)


class EnrollmentUpsert(BaseModel):
    exam_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    role: EnrollmentRole = "candidate"
    display_name: str = Field(default="", max_length=120)
    mnh_role: str = Field(default="", max_length=80)


class SessionStart(BaseModel):
    exam_id: str = Field(min_length=1, max_length=120)


class SessionAutosave(AnswerPayloadMixin):
    client_save_id: str = Field(default="", max_length=120)
    seq: int = Field(default=0, ge=0)
    expected_updated_at: int | None = Field(default=None, ge=0)


class SessionSubmit(AnswerPayloadMixin):
    client_submit_id: str = Field(default="", max_length=120)
    expected_updated_at: int | None = Field(default=None, ge=0)


class SessionEventUpsert(BaseModel):
    event_type: SessionEventType
    detail: str = Field(default="", max_length=300)
    client_event_id: str = Field(default="", max_length=120)
    expected_updated_at: int | None = Field(default=None, ge=0)


class SessionAction(BaseModel):
    action: InvigilationAction
    minutes: int | None = Field(default=None, ge=1, le=120)
    reason: str = Field(default="", max_length=1000)
    expected_updated_at: int | None = Field(default=None, ge=0)


class GradeQuestion(BaseModel):
    question_id: str = Field(min_length=1, max_length=120)
    earned_points: float = Field(ge=0, le=100000)
    feedback: str = Field(default="", max_length=4000)


class SubmissionGrade(BaseModel):
    earned_points: float | None = Field(default=None, ge=0, le=100000)
    percent: float | None = Field(default=None, ge=0, le=100)
    feedback: str = Field(default="", max_length=8000)
    status: Literal["submitted", "graded", "returned"] = "graded"
    expected_updated_at: int | None = Field(default=None, ge=0)
    question_scores: list[GradeQuestion] = Field(default_factory=list, max_length=500)
    release: bool = False


class ExamsBackupPayload(BaseModel):
    schema_version: str = Field(min_length=1, max_length=80)
    integrity: dict[str, Any] = Field(default_factory=dict)
    documents: list[dict[str, Any]] = Field(default_factory=list, max_length=20000)
    overwrite_conflicts: bool = False
