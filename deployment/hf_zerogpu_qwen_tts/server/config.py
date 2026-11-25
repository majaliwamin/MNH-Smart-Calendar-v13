from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except Exception:
        return default


@dataclass(slots=True)
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("QWEN_TTS_API_KEY", "").strip())
    model_id: str = field(default_factory=lambda: os.getenv("QWEN_TTS_MODEL_ID", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice").strip())
    device: str = field(default_factory=lambda: os.getenv("QWEN_TTS_DEVICE", "auto").strip() or "auto")
    dtype: str = field(default_factory=lambda: os.getenv("QWEN_TTS_DTYPE", "auto").strip() or "auto")
    attn_impl: str = field(default_factory=lambda: os.getenv("QWEN_TTS_ATTN_IMPL", "auto").strip() or "auto")
    max_text_length: int = field(default_factory=lambda: _env_int("QWEN_TTS_MAX_TEXT_LENGTH", 1800))
    max_new_tokens: int = field(default_factory=lambda: _env_int("QWEN_TTS_MAX_NEW_TOKENS", 1024))
    default_voice: str = field(default_factory=lambda: os.getenv("QWEN_TTS_DEFAULT_VOICE", "Ryan").strip() or "Ryan")
    default_language: str = field(default_factory=lambda: os.getenv("QWEN_TTS_DEFAULT_LANGUAGE", "English").strip() or "English")
    default_format: str = field(default_factory=lambda: os.getenv("QWEN_TTS_DEFAULT_FORMAT", "wav").strip().lower() or "wav")
    allow_voice_clone: bool = field(default_factory=lambda: _env_bool("QWEN_TTS_ALLOW_VOICE_CLONE", False))
    require_auth: bool = field(default_factory=lambda: _env_bool("QWEN_TTS_REQUIRE_AUTH", True))
    cors_origins: str = field(default_factory=lambda: os.getenv("QWEN_TTS_CORS_ORIGINS", "").strip())
    startup_load: bool = field(default_factory=lambda: _env_bool("QWEN_TTS_STARTUP_LOAD", False))
    zerogpu_duration: int = field(default_factory=lambda: _env_int("QWEN_TTS_ZEROGPU_DURATION", 120))
    log_level: str = field(default_factory=lambda: os.getenv("QWEN_TTS_LOG_LEVEL", "INFO").strip().upper() or "INFO")

    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
