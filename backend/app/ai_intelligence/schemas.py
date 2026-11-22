"""Validated request contracts for the AI intelligence endpoints."""
from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    original_response: str = Field(min_length=1, max_length=6000)
    correction: str = Field(min_length=1, max_length=6000)
    category: str | None = Field(default=None, max_length=80)
    date_or_entity: str | None = Field(default=None, max_length=200)
    verified_facts: list[dict] = Field(default_factory=list, max_length=40)
    conversation_id: str | None = Field(default=None, max_length=80)
    response_language: str = Field(default="EN", pattern="^(EN|CH|en|ch)$")


class EvaluateRequest(BaseModel):
    force: bool = False
