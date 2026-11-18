"""Environment-backed Class Rep Assistant configuration.

CARA deliberately uses Cloudflare Workers AI first, then Hugging Face, then Groq.
Secrets are read only on the server.
"""
import os


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

    hf_key = _value("MNH_CLASSREP_HF_API_KEY")
    hf_model = _value("MNH_CLASSREP_HF_MODEL")
    if hf_key and hf_model:
        providers.append({
            "provider": "huggingface", "base_url": "https://router.huggingface.co/v1",
            "api_key": hf_key, "model": hf_model,
            "timeout": timeout, "max_tokens": max_tokens,
        })

    groq_key = _value("MNH_CLASSREP_GROQ_API_KEY")
    groq_model = _value("MNH_CLASSREP_GROQ_MODEL", "llama-3.3-70b-versatile")
    groq_base_url = _value("MNH_CLASSREP_GROQ_BASE_URL")
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
