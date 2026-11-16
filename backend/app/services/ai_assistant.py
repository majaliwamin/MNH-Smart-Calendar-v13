"""Optional Communications Centre message drafter using a configured external provider.

The endpoint, model and credential are explicit environment settings. No provider
endpoint or vendor is assumed by the application.
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
    return _env("MNH_COMM_AI_API_KEY")


def base_url() -> str:
    return _env("MNH_COMM_AI_BASE_URL").rstrip("/")


def model() -> str:
    return _env("MNH_COMM_AI_MODEL")


def enabled() -> bool:
    return bool(api_key() and base_url() and model())


def status() -> dict:
    return {
        "provider": "Configured Communications Centre provider",
        "configured": enabled(),
        "model": model() if enabled() else "",
        "missing": [name for name, value in (
            ("MNH_COMM_AI_API_KEY", api_key()),
            ("MNH_COMM_AI_BASE_URL", base_url()),
            ("MNH_COMM_AI_MODEL", model()),
        ) if not value],
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
            "Communications Centre AI drafting is not configured. Set "
            "MNH_COMM_AI_API_KEY, MNH_COMM_AI_BASE_URL and MNH_COMM_AI_MODEL."
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
        raise AIError(f"The configured provider rejected the request ({error.code}).") from error
    except urllib.error.URLError as error:
        raise AIError(f"The configured provider could not be reached: {error.reason}") from error
    try:
        content = str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError):
        raise AIError("The configured provider returned an unexpected response.")
    if not content:
        raise AIError("The configured provider returned an empty draft.")
    return content
