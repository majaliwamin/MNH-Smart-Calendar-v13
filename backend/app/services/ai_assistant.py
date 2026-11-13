"""AI message assistant — drafts text only, never sends anything.

Provider-agnostic, OpenAI-compatible chat-completions client using only the
standard library (urllib). Credentials live in the environment:

    MNH_AI_API_KEY    API key (drafting is disabled when missing)
    MNH_AI_BASE_URL   OpenAI-compatible base URL (default https://api.openai.com/v1)
    MNH_AI_MODEL      model name (default gpt-4o-mini)

The assistant is a drafting aid: every result is returned to the caller for
human review and editing. It has no access to the WhatsApp module and cannot
create wa.me links, open conversations, place calls, or touch the outbox.
"""
import json
import os
import urllib.error
import urllib.request


class AIError(RuntimeError):
    """Drafting failed, or the provider is not configured."""


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def api_key() -> str:
    return _env("MNH_AI_API_KEY")


def base_url() -> str:
    url = _env("MNH_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    return url if url.endswith("/v1") or "/v1" in url else url


def model() -> str:
    return _env("MNH_AI_MODEL", "gpt-4o-mini")


def enabled() -> bool:
    return bool(api_key())


def status() -> dict:
    return {
        "provider": "OpenAI-compatible chat completions",
        "configured": enabled(),
        "model": model(),
        "missing": ["MNH_AI_API_KEY"] if not enabled() else [],
    }


SYSTEM_PROMPT = (
    "You draft short WhatsApp messages for the Maternal & Neonatal Health (MNH) "
    "Smart Timetable at a health sciences institution. Use ONLY the facts provided "
    "in the user's request — never invent dates, times, names, rooms or exam details. "
    "Keep messages under 600 characters, professional but warm, plain text (WhatsApp "
    "*bold* markers allowed), and include the sender line "
    "'Maternal & Neonatal Health Smart Time Table' as the first line. "
    "Reply with the message text only — no explanations."
)


def draft(prompt: str, *, timeout: int = 45) -> str:
    """Return an AI-drafted message for human review. Raises AIError on failure."""
    if not enabled():
        raise AIError(
            "AI drafting is not configured on this server yet. Set MNH_AI_API_KEY "
            "(and optionally MNH_AI_BASE_URL / MNH_AI_MODEL)."
        )
    text = str(prompt or "").strip()
    if not text:
        raise AIError("Describe the message you want drafted.")
    payload = {
        "model": model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:4000]},
        ],
        "temperature": 0.4,
        "max_tokens": 500,
    }
    request = urllib.request.Request(
        f"{base_url()}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            failure = json.loads(error.read().decode("utf-8") or "{}")
            detail = str((failure.get("error") or {}).get("message") or "")
        except (ValueError, AttributeError):
            detail = ""
        raise AIError(f"The AI provider rejected the request ({error.code}). {detail}".strip()) from error
    except urllib.error.URLError as error:
        raise AIError(f"The AI provider could not be reached: {error.reason}") from error
    try:
        content = str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError):
        raise AIError("The AI provider returned an unexpected response.")
    if not content:
        raise AIError("The AI provider returned an empty draft.")
    return content
