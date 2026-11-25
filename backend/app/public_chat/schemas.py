from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class JoinRequest(BaseModel):
    display_name: str = Field(default="", max_length=80)
    code: str = Field(default="", max_length=20)
    request_new: bool = False


class MessageCreateRequest(BaseModel):
    text: str = Field(default="", max_length=4000)
    reply_to_id: str | None = Field(default=None, max_length=80)
    private_recipient_code: str | None = Field(default=None, max_length=20)
    mention_codes: list[str] = Field(default_factory=list, max_length=20)
    view_once: bool = False


class MessageEditRequest(BaseModel):
    text: str = Field(default="", max_length=4000)


class VoiceMessageRequest(BaseModel):
    reply_to_id: str | None = Field(default=None, max_length=80)
    private_recipient_code: str | None = Field(default=None, max_length=20)
    mention_codes: list[str] = Field(default_factory=list, max_length=20)
    duration_ms: int = Field(default=0, ge=0, le=60 * 60 * 1000)


class ReactionRequest(BaseModel):
    emoji: str = Field(default="", max_length=8)


class ReportRequest(BaseModel):
    message_id: str = Field(default="", max_length=80)
    category: str = Field(default="other", max_length=40)
    reason: str = Field(default="", max_length=1000)


class ModerationRequest(BaseModel):
    action: str = Field(default="dismiss", max_length=40)
    note: str = Field(default="", max_length=500)


class AccessDecisionRequest(BaseModel):
    approved: bool = False
    note: str = Field(default="", max_length=500)


class RestrictRequest(BaseModel):
    status: Literal["active", "suspended"]


class RoleRequest(BaseModel):
    role: Literal["member", "moderator", "administrator"]


class PreferencesRequest(BaseModel):
    values: dict[str, bool] = Field(default_factory=dict)


class ReadRequest(BaseModel):
    at: int = Field(default=0, ge=0)
