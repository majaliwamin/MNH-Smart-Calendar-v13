"""Pydantic schemas for EXAMS foundation."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ExamStatus = Literal["draft", "published", "archived"]
QuestionType = Literal["mcq", "multiple_select", "short_text", "essay", "true_false"]
EnrollmentRole = Literal["candidate", "invigilator", "grader"]


class QuestionOption(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=1000)


class QuestionUpsert(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    type: QuestionType = "mcq"
    options: list[QuestionOption] = Field(default_factory=list)
    correct_option_ids: list[str] = Field(default_factory=list)
    correct_text: str = Field(default="", max_length=4000)
    points: float = Field(default=1.0, ge=0, le=1000)
    explanation: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list)
    active: bool = True


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
    questions: list[ExamQuestionLink] = Field(default_factory=list)
    require_enrollment: bool = False


class EnrollmentUpsert(BaseModel):
    exam_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    role: EnrollmentRole = "candidate"


class SessionStart(BaseModel):
    exam_id: str = Field(min_length=1, max_length=120)


class SessionAutosave(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    client_save_id: str = Field(default="", max_length=120)
    seq: int = Field(default=0, ge=0)
    expected_updated_at: int | None = Field(default=None, ge=0)


class SessionSubmit(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    client_submit_id: str = Field(default="", max_length=120)
    expected_updated_at: int | None = Field(default=None, ge=0)


class SubmissionGrade(BaseModel):
    earned_points: float | None = Field(default=None, ge=0, le=100000)
    percent: float | None = Field(default=None, ge=0, le=100)
    feedback: str = Field(default="", max_length=8000)
    status: Literal["submitted", "graded", "returned"] = "graded"
