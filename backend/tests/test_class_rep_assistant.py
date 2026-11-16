import json
from app.class_rep import providers
from app.class_rep.providers import ProviderError


def test_provider_fails_closed_when_no_provider_is_configured(monkeypatch):
    monkeypatch.setattr(providers, "provider_configs", lambda: [])
    try:
        providers.complete([{"role": "user", "content": "hello"}])
    except ProviderError as exc:
        assert "No AI provider is configured" in str(exc)
    else:
        raise AssertionError("CARA must not make unauthenticated requests")


def test_cloudflare_provider_parses_workers_ai_response(monkeypatch):
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"success": True, "result": {"response": "  Hello class  "}}).encode()

    monkeypatch.setattr(providers, "provider_configs", lambda: [{
        "provider": "cloudflare", "account_id": "account-test",
        "api_key": "test-secret", "model": "@cf/qwen/test",
        "timeout": 5, "max_tokens": 100,
    }])
    seen = {}
    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        return FakeResponse()
    monkeypatch.setattr(providers, "urlopen", fake_urlopen)
    result = providers.complete([{"role": "user", "content": "hello"}])
    assert result == ("Hello class", "cloudflare", "@cf/qwen/test")
    assert "/accounts/account-test/ai/run/@cf/qwen/test" in seen["url"]
    assert seen["authorization"] == "Bearer test-secret"


def test_provider_falls_back_in_priority_order(monkeypatch):
    configured = [
        {"provider": "cloudflare", "model": "cf-model"},
        {"provider": "huggingface", "model": "hf-model"},
        {"provider": "groq", "model": "groq-model"},
    ]
    monkeypatch.setattr(providers, "provider_configs", lambda: configured)
    calls = []
    def fake_complete_one(cfg, messages):
        calls.append(cfg["provider"])
        if cfg["provider"] == "cloudflare":
            raise ProviderError("unavailable")
        return "HF answer"
    monkeypatch.setattr(providers, "_complete_one", fake_complete_one)
    assert providers.complete([{"role": "user", "content": "hello"}]) == (
        "HF answer", "huggingface", "hf-model"
    )
    assert calls == ["cloudflare", "huggingface"]


def test_all_provider_failures_return_safe_error(monkeypatch):
    monkeypatch.setattr(providers, "provider_configs", lambda: [
        {"provider": "cloudflare", "model": "cf"},
        {"provider": "groq", "model": "g"},
    ])
    monkeypatch.setattr(providers, "_complete_one",
                        lambda cfg, messages: (_ for _ in ()).throw(ProviderError("private provider detail")))
    try:
        providers.complete([{"role": "user", "content": "hello"}])
    except ProviderError as exc:
        assert "cloudflare, groq" in str(exc)
        assert "private provider detail" not in str(exc)
    else:
        raise AssertionError("Provider failure should be reported safely")


def test_activity_history_is_included_in_cara_context(monkeypatch):
    from app.class_rep import context

    class Row(dict):
        pass
    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params=()):
            if "FROM audit" in query:
                return type("Rows", (), {"fetchall": lambda self: [
                    Row(at=1794850000000, action="updated", collection="cells",
                        item_id="session-1", summary="Updated session: MIPN 8100")
                ]})()
            return type("Rows", (), {"fetchall": lambda self: [
                Row(col="modules", id="MIPN 8100",
                    data=json.dumps({"title": "Medical Imaging"}), updated_at=1794850000000)
            ]})()
    monkeypatch.setattr(context, "database", lambda: FakeConnection())
    payload, updated = context.build_calendar_context()
    data = json.loads(payload)
    assert data["records"]["modules"][0]["title"] == "Medical Imaging"
    assert data["recent_activity_history"][0]["summary"] == "Updated session: MIPN 8100"
    assert updated is not None

from app.class_rep import assistant


def test_assistant_uses_live_context_and_limits_history(monkeypatch):
    seen = {}
    monkeypatch.setattr(assistant, "build_calendar_context",
                        lambda: ('{"records":{"examinations":[]}}', "2026-11-16T10:00"))
    def fake_complete(messages):
        seen["messages"] = messages
        return "The examination time is not recorded.", "cloudflare", "test-model"
    monkeypatch.setattr(assistant, "complete", fake_complete)
    history = [{"role": "user", "content": "old %s" % n} for n in range(20)]
    answer, provider, model, updated = assistant.reply("What time is the exam?", history)
    assert "not recorded" in answer
    assert provider == "cloudflare" and model == "test-model"
    assert updated == "2026-11-16T10:00"
    assert len(seen["messages"]) == 12
    assert "CURRENT LIVE APPLICATION KNOWLEDGE SNAPSHOT" in seen["messages"][0]["content"]
    assert seen["messages"][-1]["content"] == "What time is the exam?"
