"""Detect and remove transient service-error text from CRARA chat context.

Provider outages must never become part of the conversation as if CRARA had
authored them. This module centralises the patterns for those transient errors
so the API, the reply pipeline, memory retrieval and output validation all use
the same definition.
"""
from __future__ import annotations

import re
from typing import Any

_TRANSIENT_PATTERNS = (
    r"crara service error",
    r"crara (?:is|was) temporarily unavailable",
    r"all configured (?:crara )?ai (?:service )?providers? (?:are|were)?\s*temporarily unavailable",
    r"ai service providers? (?:are|were)\s*temporarily unavailable",
    r"service providers? (?:are|were)\s*temporarily unavailable",
    r"automated system error",
    r"not a response to your question",
    r"providererror",
    r"all_providers_failed",
    r"the connection to crara was interrupted",
    r"crara took too long to respond",
    r"connections? to .{0,30}providers? (?:failed|could not be established)",
)

_TRANSIENT_ERROR = re.compile("|".join(f"(?:{pattern})" for pattern in _TRANSIENT_PATTERNS), re.I)

# Split on sentence-ish boundaries so one error sentence can be removed from a
# longer generated reply without discarding otherwise useful content.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def is_transient_error_text(value: Any) -> bool:
    """Return True when text is only/probably a transient provider error."""
    text = str(value or "").strip()
    return bool(text) and bool(_TRANSIENT_ERROR.search(text))


def clean_transient_error_text(value: Any) -> str:
    """Remove whole sentences that reference a transient provider error."""
    text = str(value or "").strip()
    if not text:
        return ""
    if not _TRANSIENT_ERROR.search(text):
        return text
    kept = [part.strip() for part in _SENTENCE_SPLIT.split(text)
            if part.strip() and not _TRANSIENT_ERROR.search(part)]
    return " ".join(kept).strip()


def clean_history(history: list[dict] | None) -> list[dict]:
    """Keep the user's words; remove service-error text from assistant turns."""
    cleaned: list[dict] = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))
        original = str(item.get("content", ""))
        if not original.strip():
            continue
        if role == "assistant":
            content = clean_transient_error_text(original)
            if not content or is_transient_error_text(content):
                continue
        else:
            content = original
        updated = dict(item)
        updated["content"] = content
        cleaned.append(updated)
    return cleaned


def clean_conversation_messages(messages: Any) -> list[dict]:
    """Filter persisted message dicts before they are serialised into a prompt."""
    if not isinstance(messages, list):
        return []
    cleaned: list[dict] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))
        original = str(item.get("content", ""))
        if not original.strip():
            continue
        if role == "assistant":
            content = clean_transient_error_text(original)
            if not content or is_transient_error_text(content):
                continue
        else:
            content = original
        updated = dict(item)
        updated["content"] = content
        cleaned.append(updated)
    return cleaned
