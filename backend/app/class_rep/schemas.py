"""Validated request and response contracts for the Class Rep Assistant."""
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    conversation_id: str | None = Field(default=None, max_length=80)
    response_language: str = Field(default="EN", pattern="^(EN|CH|en|ch)$")


class ChatResponse(BaseModel):
    reply: str
    provider: str
    model: str
    context_updated_at: str | None = None
    conversation_id: str | None = None


class TranslationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    source_language: str = Field(default="AUTO", pattern="^(EN|CH|AUTO|en|ch|auto)$")
    target_language: str = Field(default="AUTO", pattern="^(EN|CH|AUTO|en|ch|auto)$")
    register: str = Field(default="neutral", pattern="^(casual|neutral|professional|clinical|academic)$")
    domain: str = Field(default="general", max_length=80)
    mode: str = Field(default="translate", pattern="^(translate|interpret)$")


class TranslationResponse(BaseModel):
    translation: str
    source_language: str
    target_language: str
    provider: str
    model: str
