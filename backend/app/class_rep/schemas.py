"""Validated request and response contracts for the Class Rep Assistant."""
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    conversation_id: str | None = Field(default=None, max_length=80)


class ChatResponse(BaseModel):
    reply: str
    provider: str
    model: str
    context_updated_at: str | None = None
    conversation_id: str | None = None
