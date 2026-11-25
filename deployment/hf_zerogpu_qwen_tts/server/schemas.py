from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SpeechRequest(BaseModel):
    model: str | None = None
    input: str = Field(..., min_length=1, max_length=8000)
    voice: str | None = None
    response_format: Literal["wav", "mp3", "pcm"] = "wav"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    language: str | None = None
    instructions: str | None = Field(default=None, max_length=500)
    # Non-standard extension; only honored when model/service supports it.
    ref_audio_base64: str | None = None
    ref_text: str | None = None


class HealthResponse(BaseModel):
    status: str
    model_id: str
    gpu_available: bool
    gpu_name: str | None = None
    vram_gb: float | None = None
    model_loaded: bool
    ready: bool
    detail: str | None = None


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "qwen"
    capabilities: dict


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo]
