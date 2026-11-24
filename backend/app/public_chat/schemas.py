from __future__ import annotations

from pydantic import BaseModel, Field


class JoinRequest(BaseModel):
    display_name: str = Field(default="", max_length=80)


class MessageCreateRequest(BaseModel):
    text: str = Field(default="", max_length=4000)
    reply_to_id: str | None = Field(default=None, max_length=80)
    private_recipient_code: str | None = Field(default=None, max_length=20)
    mention_codes: list[str] = Field(default_factory=list)


class MessageEditRequest(BaseModel):
    text: str = Field(default="", max_length=4000)


class VoiceMessageRequest(BaseModel):
    reply_to_id: str | None = Field(default=None, max_length=80)
    private_recipient_code: str | None = Field(default=None, max_length=20)
    mention_codes: list[str] = Field(default_factory=list, max_length=20)