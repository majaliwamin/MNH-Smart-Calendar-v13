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
            return json.dumps({"choices": [{"message": {"role": "assistant", "content": "  Hello class  "}}]}).encode()

    monkeypatch.setattr(providers, "provider_configs", lambda: [{
        "provider": "cloudflare", "account_id": "account-test",
        "api_key": "test-secret", "model": "@cf/qwen/test",
        "timeout": 5, "max_tokens": 100,
    }])
    seen = {}
    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        seen["payload"] = json.loads(request.data.decode())
        return FakeResponse()
    monkeypatch.setattr(providers, "urlopen", fake_urlopen)
    result = providers.complete([{"role": "user", "content": "hello"}])
    assert result == ("Hello class", "cloudflare", "@cf/qwen/test")
    assert seen["url"] == "https://api.cloudflare.com/client/v4/accounts/account-test/ai/v1/chat/completions"
    assert seen["authorization"] == "Bearer test-secret"
    assert seen["payload"]["model"] == "@cf/qwen/test"
    assert seen["payload"]["messages"] == [{"role": "user", "content": "hello"}]
    assert seen["payload"]["stream"] is False


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


def test_document_chunking_and_text_extraction():
    from app.class_rep.documents import _extract, _split
    assert _extract("notes.txt", b"Maternal health\nNeonatal health")[0][1].startswith("Maternal health")
    chunks = _split("word " * 1200)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 1800 for chunk in chunks)


def test_document_ingestion_is_persisted_as_private_cara_collection(monkeypatch):
    from app.class_rep import documents

    stored = []
    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, sql, params):
            stored.append((sql, params))
    monkeypatch.setattr(documents, "database", lambda: FakeConnection())
    monkeypatch.setattr(documents, "_vectors", lambda texts, prefix: [[0.1, 0.2] for _ in texts])
    result = documents.ingest("programme.txt", b"Important programme rules for students.")
    assert result["title"] == "programme.txt"
    assert result["chunks"] == 1
    assert any(params[0] == "cara_documents" for _, params in stored)
    assert any(params[0] == "cara_document_index" for _, params in stored)


def test_document_admin_token_is_required(monkeypatch):
    from app.class_rep.routes import _require_document_admin
    from fastapi import HTTPException
    monkeypatch.setenv("MNH_CLASSREP_DOCUMENT_ADMIN_TOKEN", "strong-secret")
    try:
        _require_document_admin("wrong")
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("Invalid document admin token must be rejected")
    _require_document_admin("strong-secret")


def test_voice_adapters_validate_and_return_audio(monkeypatch):
    from app.class_rep import voice
    monkeypatch.setenv("MNH_CLASSREP_CLOUDFLARE_STT_MODEL", "@cf/test/speech-to-text")
    monkeypatch.setattr(voice, "_run", lambda model, payload: {"text": "Hello class"})
    assert voice.transcribe(b"audio-bytes", "audio/webm") == "Hello class"
    try:
        voice.transcribe(b"not-audio", "text/plain")
    except voice.VoiceError:
        pass
    else:
        raise AssertionError("Non-audio uploads must be rejected")
    import base64
    monkeypatch.setattr(voice, "_run", lambda model, payload: {"audio": base64.b64encode(b"mp3").decode()})
    audio, content_type = voice.speak("Hello")
    assert audio == b"mp3" and content_type == "audio/mpeg"


def test_cara_analytics_intent_rejects_unauthorised_request(monkeypatch):
    from app.class_rep import routes
    from app.class_rep.schemas import ChatRequest
    from fastapi import HTTPException

    class Client:
        host = "127.0.0.1"
    class Request:
        client = Client()
    monkeypatch.setattr(routes, "_user", lambda request: {"id": "test-user"})
    monkeypatch.setattr(routes, "role_for_password", lambda password: None)
    try:
        routes.chat(ChatRequest(message="Show programme analytics"), Request(), None)
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "HOD" in exc.detail
    else:
        raise AssertionError("CARA analytics must require an authorised management role")


def test_cara_analytics_intent_accepts_only_management_roles(monkeypatch):
    from app.class_rep import routes
    assert routes._ANALYTICS_QUERY.search("Show missed sessions and attendance")
    assert routes._ANALYTICS_QUERY.search("Compare online vs face-to-face")
    assert routes._ANALYTICS_ROLES == {"hod", "coordinator", "executive_dean"}


def test_ocr_text_normaliser_handles_easyocr_and_paddleocr_results():
    from app.class_rep.ocr import _texts
    easy = [[[0, 0], [1, 0], [1, 1], [0, 1]], "Maternal health", 0.98]
    paddle_v2 = [[[0, 0], [1, 0], [1, 1], [0, 1]], ["Neonatal health", 0.97]]
    paddle_v3 = {"rec_texts": ["Pregnancy", "Newborn"]}
    assert _texts([easy]) == ["Maternal health"]
    assert _texts([paddle_v2]) == ["Neonatal health"]
    assert _texts(paddle_v3) == ["Pregnancy", "Newborn"]


def test_ocr_engine_order_and_configuration():
    from app.class_rep.ocr import _engine_order, OCRDocumentError
    import pytest
    assert _engine_order("auto") == ["paddleocr", "easyocr"]
    assert _engine_order("easyocr") == ["easyocr"]
    with pytest.raises(OCRDocumentError, match="must be auto"):
        _engine_order("unknown")


def test_paddleocr_v3_result_object_is_supported():
    from app.class_rep.ocr import _texts
    class Result:
        json = {"res": {"rec_texts": ["OCR output"]}}
    assert _texts([Result()]) == ["OCR output"]



def test_cloudflare_http_failures_log_status_and_error_code_without_secrets(monkeypatch, caplog):
    from io import BytesIO
    from urllib.error import HTTPError

    monkeypatch.setattr(providers, "provider_configs", lambda: [{
        "provider": "cloudflare", "account_id": "account-test",
        "api_key": "never-log-this-token", "model": "@cf/qwen/test",
        "timeout": 5, "max_tokens": 100,
    }])

    def reject_request(request, timeout):
        raise HTTPError(
            request.full_url, 403, "Forbidden", {},
            BytesIO(json.dumps({"success": False, "errors": [
                {"code": 10000, "message": "Authentication error"}
            ]}).encode()),
        )

    monkeypatch.setattr(providers, "urlopen", reject_request)
    with caplog.at_level("WARNING"):
        try:
            providers.complete([{"role": "user", "content": "private prompt"}])
        except ProviderError as exc:
            assert "temporarily unavailable" in str(exc)
        else:
            raise AssertionError("A rejected provider request must fail safely")

    assert "provider=cloudflare" in caplog.text
    assert "http_status=403" in caplog.text
    assert "error_codes=10000" in caplog.text
    assert "never-log-this-token" not in caplog.text
    assert "private prompt" not in caplog.text
