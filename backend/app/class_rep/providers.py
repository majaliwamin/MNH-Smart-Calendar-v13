"""Server-side AI adapters with Cloudflare -> Hugging Face -> Groq fallback."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.class_rep.config import provider_configs


class ProviderError(RuntimeError):
    pass


def _post_json(endpoint: str, api_key: str, payload: dict, timeout: int) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(endpoint, data=body, headers={
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ProviderError("Provider returned HTTP %s." % exc.code) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ProviderError("Provider could not be reached.") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProviderError("Provider returned an unreadable response.") from exc


def _complete_one(cfg: dict, messages: list[dict]) -> str:
    provider = cfg["provider"]
    if provider == "cloudflare":
        endpoint = ("https://api.cloudflare.com/client/v4/accounts/"
                    + cfg["account_id"] + "/ai/run/" + cfg["model"])
        result = _post_json(endpoint, cfg["api_key"], {
            "messages": messages, "max_tokens": cfg["max_tokens"],
            "temperature": 0.25,
        }, cfg["timeout"])
        if result.get("success") is False:
            raise ProviderError("Cloudflare Workers AI did not accept the request.")
        answer = (result.get("result") or {}).get("response")
    else:
        endpoint = cfg["base_url"].rstrip("/") + "/chat/completions"
        result = _post_json(endpoint, cfg["api_key"], {
            "model": cfg["model"], "messages": messages,
            "temperature": 0.25, "max_tokens": cfg["max_tokens"],
        }, cfg["timeout"])
        try:
            answer = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            answer = None
    if not isinstance(answer, str) or not answer.strip():
        raise ProviderError("Provider returned an empty or unsupported response.")
    return answer.strip()


def complete(messages: list[dict]) -> tuple[str, str, str]:
    """Try configured providers in priority order; never call OpenAI."""
    configured = provider_configs()
    if not configured:
        raise ProviderError(
            "No AI provider is configured. Add Cloudflare credentials, then Hugging Face "
            "or Groq credentials as fallbacks in the hosting environment."
        )
    failures = []
    for cfg in configured:
        try:
            answer = _complete_one(cfg, messages)
            return answer, cfg["provider"], cfg["model"]
        except ProviderError:
            # Do not expose provider response bodies, request content, or secrets.
            failures.append(cfg["provider"])
    raise ProviderError(
        "All configured CARA AI providers are temporarily unavailable (" +
        ", ".join(failures) + "). Please try again later."
    )
