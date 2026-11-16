"""AI provider adapters. Secrets and HTTP calls remain server-side."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from app.class_rep.config import provider_config


class ProviderError(RuntimeError):
    pass


def complete(messages: list[dict]) -> tuple[str, str, str]:
    """Call an OpenAI Chat Completions-compatible provider (OpenAI, Groq, OpenRouter, etc.)."""
    cfg = provider_config()
    if cfg["provider"] not in {"openai-compatible", "openai", "groq", "openrouter"}:
        raise ProviderError("The configured AI provider is not supported by this adapter.")
    if not cfg["api_key"]:
        raise ProviderError("The AI provider is not configured. Add MNH_CLASSREP_AI_API_KEY in the hosting environment.")
    if not cfg["model"]:
        raise ProviderError("The AI model name is not configured.")
    endpoint = cfg["base_url"] + "/chat/completions"
    body = json.dumps({"model": cfg["model"], "messages": messages, "temperature": 0.25,
                       "max_tokens": cfg["max_tokens"]}).encode("utf-8")
    request = Request(endpoint, data=body, headers={"Authorization": "Bearer " + cfg["api_key"],
                     "Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=cfg["timeout"]) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Do not return provider response bodies: they may contain request details.
        raise ProviderError("The AI provider rejected the request (HTTP %s). Check the provider key, model and quota." % exc.code) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ProviderError("The AI provider could not be reached. Check its endpoint and network availability.") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProviderError("The AI provider returned an unreadable response.") from exc
    try:
        text = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("The AI provider response did not contain a chat reply.") from exc
    if not isinstance(text, str) or not text.strip():
        raise ProviderError("The AI provider returned an empty reply.")
    return text.strip(), cfg["provider"], cfg["model"]
