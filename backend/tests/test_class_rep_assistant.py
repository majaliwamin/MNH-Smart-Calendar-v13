import json
from app.class_rep import assistant, providers
from app.class_rep.providers import ProviderError


def test_assistant_uses_shared_calendar_context_and_limits_history(monkeypatch):
    seen = {}
    monkeypatch.setattr(assistant, "build_calendar_context", lambda: ('{"records":{"examinations":[]}}', "2026-11-16T10:00"))
    def fake_complete(messages):
        seen["messages"] = messages
        return "The examination time is not recorded.", "openai-compatible", "test-model"
    monkeypatch.setattr(assistant, "complete", fake_complete)
    history = [{"role": "user", "content": "old %s" % n} for n in range(20)]
    reply, provider, model, updated = assistant.reply("What time is the exam?", history)
    assert "not recorded" in reply
    assert provider == "openai-compatible" and model == "test-model"
    assert updated == "2026-11-16T10:00"
    assert len(seen["messages"]) == 12  # system + last ten history turns + current request
    assert "CURRENT AUTHORITATIVE CALENDAR SNAPSHOT" in seen["messages"][0]["content"]
    assert seen["messages"][-1]["content"] == "What time is the exam?"


def test_provider_fails_closed_when_api_key_is_missing(monkeypatch):
    monkeypatch.setattr(providers, "provider_config", lambda: {
        "provider": "openai-compatible", "base_url": "https://example.invalid/v1",
        "api_key": "", "model": "test-model", "timeout": 5, "max_tokens": 100
    })
    try:
        providers.complete([{"role": "user", "content": "hello"}])
    except ProviderError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("Provider must not make unauthenticated requests")


def test_provider_parses_chat_completion_response(monkeypatch):
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps({"choices": [{"message": {"content": "  Hello class  "}}]}).encode()
    monkeypatch.setattr(providers, "provider_config", lambda: {
        "provider": "openai-compatible", "base_url": "https://example.test/v1",
        "api_key": "test-secret", "model": "test-model", "timeout": 5, "max_tokens": 100
    })
    monkeypatch.setattr(providers, "urlopen", lambda request, timeout: FakeResponse())
    result = providers.complete([{"role": "user", "content": "hello"}])
    assert result == ("Hello class", "openai-compatible", "test-model")
