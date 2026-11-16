"""Server-side AI adapters with Cloudflare -> Hugging Face -> Groq fallback."""
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.class_rep.config import provider_configs

logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    """Safe provider failure with diagnostic metadata (never credentials or prompts)."""

    def __init__(self, message: str, *, category: str = "provider_error",
                 status_code: int | None = None, error_codes: tuple[str, ...] = ()):
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.error_codes = error_codes


def _cloudflare_error_codes(raw: bytes) -> tuple[str, ...]:
    """Extract only Cloudflare numeric error codes; discard response text."""
    try:
        payload = json.loads(raw.decode("utf-8"))
        errors = payload.get("errors", []) if isinstance(payload, dict) else []
        return tuple(str(item["code"]) for item in errors
                     if isinstance(item, dict) and item.get("code") is not None)[:5]
    except (ValueError, UnicodeDecodeError, TypeError):
        return ()


def _post_json(endpoint: str, api_key: str, payload: dict, timeout: int,
               provider: str) -> dict:
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
        codes = _cloudflare_error_codes(exc.read()) if provider == "cloudflare" else ()
        raise ProviderError(
            "Provider returned HTTP %s." % exc.code,
            category="http_error", status_code=exc.code, error_codes=codes,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ProviderError("Provider could not be reached.", category="network_error") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProviderError("Provider returned an unreadable response.",
                            category="invalid_response") from exc


def _complete_one(cfg: dict, messages: list[dict]) -> str:
    provider = cfg["provider"]
    if provider == "cloudflare":
        endpoint = ("https://api.cloudflare.com/client/v4/accounts/"
                    + cfg["account_id"] + "/ai/run/" + cfg["model"])
        result = _post_json(endpoint, cfg["api_key"], {
            "messages": messages, "max_tokens": cfg["max_tokens"],
            "temperature": 0.25,
        }, cfg["timeout"], provider)
        if result.get("success") is False:
            codes = _cloudflare_error_codes(json.dumps(result).encode("utf-8"))
            raise ProviderError(
                "Cloudflare Workers AI did not accept the request.",
                category="api_rejected", error_codes=codes,
            )
        answer = (result.get("result") or {}).get("response")
    else:
        endpoint = cfg["base_url"].rstrip("/") + "/chat/completions"
        result = _post_json(endpoint, cfg["api_key"], {
            "model": cfg["model"], "messages": messages,
            "temperature": 0.25, "max_tokens": cfg["max_tokens"],
        }, cfg["timeout"], provider)
        try:
            answer = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            answer = None
    if not isinstance(answer, str) or not answer.strip():
        raise ProviderError("Provider returned an empty or unsupported response.",
                            category="empty_response")
    return answer.strip()


def complete(messages: list[dict]) -> tuple[str, str, str]:
    """Try configured providers in priority order; never call OpenAI."""
    configured = provider_configs()
    if not configured:
        raise ProviderError(
            "No AI provider is configured. Add Cloudflare credentials, then Hugging Face "
            "or Groq credentials as fallbacks in the hosting environment.",
            category="not_configured",
        )
    failures = []
    for cfg in configured:
        try:
            answer = _complete_one(cfg, messages)
            return answer, cfg["provider"], cfg["model"]
        except ProviderError as exc:
            # Safe diagnostics only: never log tokens, endpoints, prompts or response bodies.
            logger.warning(
                "CARA provider failure provider=%s category=%s http_status=%s error_codes=%s",
                cfg["provider"], exc.category, exc.status_code,
                ",".join(exc.error_codes) or "-",
            )
            failures.append(cfg["provider"])
    raise ProviderError(
        "All configured CARA AI providers are temporarily unavailable (" +
        ", ".join(failures) + "). Please try again later.",
        category="all_providers_failed",
    )
