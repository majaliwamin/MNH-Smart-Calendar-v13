"""Groq fallback configuration and Cloudflare -> Groq failover tests."""
from app.class_rep import providers
from app.class_rep.config import GROQ_DEFAULT_BASE_URL, GROQ_DEFAULT_MODEL, provider_configs
from app.class_rep.providers import ProviderError


def _clear_provider_env(monkeypatch):
    for name in (
        "MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "MNH_CLASSREP_CLOUDFLARE_API_KEY",
        "MNH_CLASSREP_HF_API_KEY", "MNH_CLASSREP_HF_MODEL",
        "MNH_CLASSREP_GROQ_API_KEY", "MNH_CLASSREP_GROQ_MODEL",
        "MNH_CLASSREP_GROQ_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_groq_fallback_needs_only_an_api_key(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "cf-account")
    monkeypatch.setenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", "cf-key")
    monkeypatch.setenv("MNH_CLASSREP_GROQ_API_KEY", "groq-key")

    configured = provider_configs()
    assert [item["provider"] for item in configured] == ["cloudflare", "groq"]
    assert configured[1]["base_url"] == GROQ_DEFAULT_BASE_URL
    assert configured[1]["model"] == GROQ_DEFAULT_MODEL
    assert configured[1]["api_key"] == "groq-key"


def test_huggingface_stays_between_cloudflare_and_groq(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "cf-account")
    monkeypatch.setenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", "cf-key")
    monkeypatch.setenv("MNH_CLASSREP_HF_API_KEY", "hf-key")
    monkeypatch.setenv("MNH_CLASSREP_HF_MODEL", "hf-model")
    monkeypatch.setenv("MNH_CLASSREP_GROQ_API_KEY", "groq-key")
    assert [item["provider"] for item in provider_configs()] == [
        "cloudflare", "huggingface", "groq",
    ]


def test_groq_base_url_override_is_honoured(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("MNH_CLASSREP_GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("MNH_CLASSREP_GROQ_BASE_URL", "https://proxy.example/v1")
    assert provider_configs()[0]["base_url"] == "https://proxy.example/v1"


def test_cloudflare_rate_limit_falls_through_to_groq(monkeypatch):
    seen = []

    def fake_post_json(endpoint, api_key, payload, timeout, provider):
        seen.append((provider, endpoint, api_key))
        if provider == "cloudflare":
            raise ProviderError("Cloudflare returned HTTP 429.", category="http_error",
                                status_code=429, error_codes=("4006",))
        assert payload["model"] == GROQ_DEFAULT_MODEL
        assert "max_tokens" in payload and "reasoning_effort" not in payload
        return {"choices": [{"message": {"content": "Groq fallback answer"}}]}

    monkeypatch.setattr(providers, "_post_json", fake_post_json)
    monkeypatch.setattr(providers, "provider_configs", lambda: [
        {"provider": "cloudflare", "account_id": "cf-account", "api_key": "cf-key",
         "model": "cf-model", "timeout": 10, "max_tokens": 500},
        {"provider": "groq", "base_url": GROQ_DEFAULT_BASE_URL, "api_key": "groq-key",
         "model": GROQ_DEFAULT_MODEL, "timeout": 10, "max_tokens": 500},
    ])
    answer, provider, model = providers.complete([{"role": "user", "content": "Moni"}])
    assert (answer, provider, model) == ("Groq fallback answer", "groq", GROQ_DEFAULT_MODEL)
    assert [item[0] for item in seen] == ["cloudflare", "groq"]
    assert seen[1][1] == GROQ_DEFAULT_BASE_URL + "/chat/completions"
    assert seen[1][2] == "groq-key"
