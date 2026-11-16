"""Environment-backed Class Rep Assistant configuration."""
import os


def provider_config():
    """Return provider settings without ever exposing the secret to clients."""
    return {
        "provider": os.getenv("MNH_CLASSREP_AI_PROVIDER", "openai-compatible").strip().lower(),
        "base_url": os.getenv("MNH_CLASSREP_AI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/"),
        "api_key": os.getenv("MNH_CLASSREP_AI_API_KEY", "").strip(),
        "model": os.getenv("MNH_CLASSREP_AI_MODEL", "gpt-4o-mini").strip(),
        "timeout": max(5, min(90, int(os.getenv("MNH_CLASSREP_AI_TIMEOUT", "35")))),
        "max_tokens": max(128, min(3000, int(os.getenv("MNH_CLASSREP_AI_MAX_TOKENS", "900")))),
    }
