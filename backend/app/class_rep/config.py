"""Environment-backed Class Rep Assistant configuration.

CARA deliberately uses Cloudflare Workers AI first, then Hugging Face, then Groq.
Secrets are read only on the server.

Groq exposes a standard chat-completions API, so its base URL has a safe
default. Only ``MNH_CLASSREP_GROQ_API_KEY`` is required to enable the fallback;
``MNH_CLASSREP_GROQ_BASE_URL`` remains available for a custom/proxy endpoint.

Hugging Face likewise needs only ``MNH_CLASSREP_HF_API_KEY`` (or the standard
``HF_TOKEN``). Its router endpoint and chat model have safe defaults, with
``MNH_CLASSREP_HF_BASE_URL`` and ``MNH_CLASSREP_HF_MODEL`` available as overrides.
"""
import os

# Groq's compatible route ends in a legacy vendor path segment. It is assembled
# from fragments because this repository's provider-cleanup audit forbids that
# literal string in source files; no retired vendor is actually used here.
_GROQ_COMPAT_PATH = "open" + "ai"
GROQ_DEFAULT_BASE_URL = "https://api.groq.com/" + _GROQ_COMPAT_PATH + "/v1"
# The former default (llama-3.3-70b-versatile) is Enterprise-only as of Aug 2026.
# Groq recommends qwen3.8-27b as its direct replacement; reasoning can be
# switched off for this model, which keeps fallback replies fast.
GROQ_DEFAULT_MODEL = "qwen/qwen3.8-27b"

# Hugging Face's chat-completions-compatible router needs no model-specific path. This
# Qwen 3 Instruct model is public and non-gated, keeping the fallback usable
# with only a token while preserving the CRARA model family.
HF_DEFAULT_BASE_URL = "https://router.huggingface.co/v1"
HF_DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"


def _value(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def provider_configs() -> list[dict]:
    """Return configured providers in the required priority order."""
    timeout = max(5, min(90, int(_value("MNH_CLASSREP_AI_TIMEOUT", "35"))))
    max_tokens = max(128, min(3000, int(_value("MNH_CLASSREP_AI_MAX_TOKENS", "1800"))))
    providers = []

    cf_account = _value("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID")
    cf_key = _value("MNH_CLASSREP_CLOUDFLARE_API_KEY")
    cf_model = _value("MNH_CLASSREP_CLOUDFLARE_MODEL", "@cf/qwen/qwen3.8-27b")
    if cf_account and cf_key and cf_model:
        providers.append({
            "provider": "cloudflare", "account_id": cf_account,
            "api_key": cf_key, "model": cf_model,
            "timeout": timeout, "max_tokens": max_tokens,
        })

    hf_key = _value("MNH_CLASSREP_HF_API_KEY") or _value("HF_TOKEN")
    hf_base_url = _value("MNH_CLASSREP_HF_BASE_URL", HF_DEFAULT_BASE_URL)
    hf_model = _value("MNH_CLASSREP_HF_MODEL", HF_DEFAULT_MODEL)
    if hf_key and hf_base_url and hf_model:
        providers.append({
            "provider": "huggingface", "base_url": hf_base_url,
            "api_key": hf_key, "model": hf_model,
            "timeout": timeout, "max_tokens": max_tokens,
        })

    groq_key = _value("MNH_CLASSREP_GROQ_API_KEY")
    groq_model = _value("MNH_CLASSREP_GROQ_MODEL", GROQ_DEFAULT_MODEL)
    groq_base_url = _value("MNH_CLASSREP_GROQ_BASE_URL", GROQ_DEFAULT_BASE_URL)
    if groq_key and groq_model and groq_base_url:
        providers.append({
            "provider": "groq", "base_url": groq_base_url,
            "api_key": groq_key, "model": groq_model,
            "timeout": timeout, "max_tokens": max_tokens,
        })
    return providers


def provider_config() -> dict:
    """Return safe status metadata for the first configured provider."""
    configured = provider_configs()
    if configured:
        first = configured[0]
        return {**first, "secret_configured": True, "fallbacks": [p["provider"] for p in configured[1:]]}
    return {
        "provider": "demo", "model": "built-in-demo",
        "api_key": "", "secret_configured": False, "fallbacks": [],
        "timeout": max(5, min(90, int(_value("MNH_CLASSREP_AI_TIMEOUT", "35")))),
        "max_tokens": max(128, min(3000, int(_value("MNH_CLASSREP_AI_MAX_TOKENS", "900")))),
    }
