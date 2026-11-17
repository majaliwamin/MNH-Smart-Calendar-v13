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
                 status_code: int | None = None, error_codes: tuple[str, ...] = (),
                 error_messages: tuple[str, ...] = ()):
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.error_codes = error_codes
        self.error_messages = error_messages


def _cloudflare_error_details(raw: bytes) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extract bounded Cloudflare error metadata; never retain response bodies or secrets."""
    try:
        payload = json.loads(raw.decode("utf-8"))
        errors = payload.get("errors", []) if isinstance(payload, dict) else []
        codes, messages = [], []
        for item in errors[:5] if isinstance(errors, list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("code") is not None:
                codes.append(str(item["code"])[:20])
            message = item.get("message")
            if isinstance(message, str):
                safe = " ".join(message.split()).replace("Bearer ", "[redacted] ")
                messages.append(safe[:180])
        return tuple(codes), tuple(messages)
    except (ValueError, UnicodeDecodeError, TypeError):
        return (), ()


def _cloudflare_error_codes(raw: bytes) -> tuple[str, ...]:
    return _cloudflare_error_details(raw)[0]


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
            parsed = json.loads(response.read().decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ProviderError("Provider returned an unsupported response format.",
                                    category="invalid_response")
            return parsed
    except HTTPError as exc:
        codes, messages = _cloudflare_error_details(exc.read()) if provider == "cloudflare" else ((), ())
        detail = (" Cloudflare: " + "; ".join(messages)) if messages else ""
        raise ProviderError(
            "Provider returned HTTP %s.%s" % (exc.code, detail),
            category="http_error", status_code=exc.code, error_codes=codes,
            error_messages=messages,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ProviderError("Provider could not be reached.", category="network_error") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProviderError("Provider returned an unreadable response.",
                            category="invalid_response") from exc


def _extract_chat_content(result: dict) -> str | None:
    """Read standard OpenAI-compatible chat-completion content."""
    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if isinstance(content, str):
        return content
    # Some compatible providers return content as an array of text parts.
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts) if parts else None
    return None


def _complete_one(cfg: dict, messages: list[dict]) -> str:
    provider = cfg["provider"]
    if provider == "cloudflare":
        # Cloudflare's supported OpenAI-compatible Workers AI REST endpoint.
        endpoint = ("https://api.cloudflare.com/client/v4/accounts/"
                    + cfg["account_id"] + "/ai/v1/chat/completions")
        result = _post_json(endpoint, cfg["api_key"], {
            "model": cfg["model"], "messages": messages,
            "max_tokens": cfg["max_tokens"], "temperature": 0.25,
            "stream": False,
        }, cfg["timeout"], provider)
        if result.get("success") is False:
            codes, messages_safe = _cloudflare_error_details(
                json.dumps(result).encode("utf-8"))
            raise ProviderError(
                "Cloudflare Workers AI did not accept the request.",
                category="api_rejected", error_codes=codes,
                error_messages=messages_safe,
            )
        answer = _extract_chat_content(result)
    else:
        endpoint = cfg["base_url"].rstrip("/") + "/chat/completions"
        result = _post_json(endpoint, cfg["api_key"], {
            "model": cfg["model"], "messages": messages,
            "temperature": 0.25, "max_tokens": cfg["max_tokens"],
        }, cfg["timeout"], provider)
        answer = _extract_chat_content(result)
    if not isinstance(answer, str) or not answer.strip():
        raise ProviderError("Provider returned an empty or unsupported response.",
                            category="empty_response")
    return answer.strip()


def cloudflare_diagnostic() -> dict:
    """Verify the token independently, then run one minimal Workers AI inference."""
    cfg = next((item for item in provider_configs() if item["provider"] == "cloudflare"), None)
    if not cfg:
        return {"configured": False, "token_valid": False, "inference_success": False,
                "message": "Cloudflare is not configured."}

    verify_request = Request(
        "https://api.cloudflare.com/client/v4/user/tokens/verify",
        headers={"Authorization": "Bearer " + cfg["api_key"], "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(verify_request, timeout=min(cfg["timeout"], 12)) as response:
            verify_payload = json.loads(response.read().decode("utf-8"))
            token_valid = bool(verify_payload.get("success") and
                               (verify_payload.get("result") or {}).get("status") == "active")
            token_status = response.status
    except HTTPError as exc:
        token_codes, token_messages = _cloudflare_error_details(exc.read())
        return {"configured": True, "token_valid": False, "token_http_status": exc.code,
                "token_error_codes": list(token_codes), "token_error_messages": list(token_messages),
                "inference_success": False, "stage": "token_verification"}
    except (URLError, TimeoutError, OSError):
        return {"configured": True, "token_valid": None, "inference_success": False,
                "stage": "token_verification",
                "message": "Cloudflare token verification endpoint could not be reached."}
    except (ValueError, UnicodeDecodeError, TypeError, AttributeError):
        return {"configured": True, "token_valid": None, "inference_success": False,
                "stage": "token_verification",
                "message": "Cloudflare returned an unreadable token-verification response."}

    if not token_valid:
        return {"configured": True, "token_valid": False, "token_http_status": token_status,
                "token_error_codes": [], "token_error_messages": ["Cloudflare did not report this token as active."],
                "inference_success": False, "stage": "token_verification"}

    try:
        _complete_one(cfg, [{"role": "user", "content": "Reply with exactly: CRARA diagnostic successful."}])
        return {"configured": True, "token_valid": True, "token_http_status": token_status,
                "inference_success": True, "stage": "complete"}
    except ProviderError as exc:
        return {"configured": True, "token_valid": True, "token_http_status": token_status,
                "inference_success": False, "stage": "workers_ai_inference",
                "inference_http_status": exc.status_code, "inference_error_codes": list(exc.error_codes),
                "inference_error_messages": list(exc.error_messages), "message": str(exc)[:300]}


def complete(messages: list[dict]) -> tuple[str, str, str]:
    """Try configured providers in priority order."""
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
                "CRARA provider failure provider=%s category=%s http_status=%s error_codes=%s error_messages=%s",
                cfg["provider"], exc.category, exc.status_code,
                ",".join(exc.error_codes) or "-", " | ".join(exc.error_messages) or "-",
            )
            failures.append(cfg["provider"])
    raise ProviderError(
        "All configured CRARA AI providers are temporarily unavailable (" +
        ", ".join(failures) + "). Please try again later.",
        category="all_providers_failed",
    )
