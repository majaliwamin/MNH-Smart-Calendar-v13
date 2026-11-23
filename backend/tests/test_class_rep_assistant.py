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
    assert seen["payload"]["reasoning_effort"] == "low"
    assert seen["payload"]["chat_template_kwargs"] == {"enable_thinking": False, "preserve_thinking": False}
    assert seen["payload"]["max_completion_tokens"] == 100
    assert "max_tokens" not in seen["payload"]


def test_provider_falls_back_in_priority_order(monkeypatch):
    configured = [
        {"provider": "cloudflare", "model": "cf-model"},
        {"provider": "gemini", "model": "gemini-model"},
        {"provider": "groq", "model": "groq-model"},
    ]
    monkeypatch.setattr(providers, "provider_configs", lambda: configured)
    calls = []
    def fake_complete_one(cfg, messages):
        calls.append(cfg["provider"])
        if cfg["provider"] == "cloudflare":
            raise ProviderError("unavailable")
        return "Gemini answer"
    monkeypatch.setattr(providers, "_complete_one", fake_complete_one)
    assert providers.complete([{"role": "user", "content": "hello"}]) == (
        "Gemini answer", "gemini", "gemini-model"
    )
    assert calls == ["cloudflare", "gemini"]


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


def test_resolved_schedule_exposes_numeric_dayindex_cells_as_dated_sessions(monkeypatch):
    from datetime import datetime as real_datetime

    from app.class_rep import assistant, context

    class FrozenDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime(2026, 11, 20, 9, 0, tzinfo=tz)

    class Row(dict):
        pass

    rows = [
        Row(col="cells", id="session-fri-pm", data=json.dumps({
            "dayIndex": 4, "startTime": "13:30", "endTime": "15:30",
            "code": "Library", "title": "Library Sesion", "weekStart": "2026-11-16",
            "mode": "face_to_face", "status": "scheduled",
        }), updated_at=1795000000000),
        Row(col="modules", id="Library", data=json.dumps(
            {"title": "Library Session"}), updated_at=1795000000000),
        Row(col="recurring", id="journal-club", data=json.dumps({
            "title": "Journal Club", "day": "Tuesday", "time": "13:00–14:00",
            "enabled": True,
        }), updated_at=1795000000000),
    ]

    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params=()):
            if "FROM audit" in query:
                return type("Rows", (), {"fetchall": lambda self: []})()
            return type("Rows", (), {"fetchall": lambda self: rows})()

    monkeypatch.setattr(context, "database", lambda: FakeConnection())
    monkeypatch.setattr(context, "datetime", FrozenDatetime)
    payload, _ = context.build_calendar_context("any upcoming class?")
    data = json.loads(payload)
    assert data["records"]["cells"] == []
    assert data["records"]["recurring"] == []
    weeks = data["resolved_schedule"]["weeks"]
    assert [week["week_start"] for week in weeks] == ["2026-11-16", "2026-11-23"]
    friday = [item for item in weeks[0]["sessions"] if item["date"] == "2026-11-20"]
    assert friday and all(item["weekday"] == "Friday" for item in friday)
    assert any(
        item["title"] == "Library Sesion" and item["start"] == "13:30"
        and item["end"] == "15:30" and item["is_today"] and item["is_upcoming"]
        for item in friday
    )
    assert "is the only timetable source" in assistant.SYSTEM_PROMPT

from app.class_rep import assistant


def test_assistant_uses_live_context_and_limits_history(monkeypatch):
    seen = {}
    monkeypatch.setattr(assistant, "build_calendar_context",
                        lambda query="": ('{"records":{"examinations":[]}}', "2026-11-16T10:00"))
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
    result = documents.ingest("programme.txt", b"Important programme rules for students.", source_id="0123456789abcdef0123456789abcdef")
    assert result["title"] == "programme.txt"
    assert result["chunks"] == 1
    assert result["source_id"] == "0123456789abcdef0123456789abcdef"
    assert any(params[0] == "cara_documents" and json.loads(params[2])["source_id"] == result["source_id"] for _, params in stored)
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
    monkeypatch.setattr(voice, "_run_audio", lambda model, payload: (b"mp3", "audio/mpeg"))
    audio, content_type = voice.speak("Hello")
    assert audio == b"mp3" and content_type == "audio/mpeg"


def test_voice_accepts_binary_cloudflare_tts_response(monkeypatch):
    from app.class_rep import voice

    class FakeHeaders:
        def get_content_type(self):
            return "audio/mpeg"

    class FakeResponse:
        headers = FakeHeaders()

        def read(self):
            return b"ID3-mp3-bytes"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "account")
    monkeypatch.setenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", "key")
    monkeypatch.setattr(voice, "urlopen", lambda request, timeout=60: FakeResponse())
    audio, content_type = voice._run_audio("@cf/deepgram/aura-2-en", {"text": "Hello"})
    assert audio == b"ID3-mp3-bytes" and content_type == "audio/mpeg"


def test_voice_transcription_uses_default_model_when_not_pinned(monkeypatch):
    from app.class_rep import voice

    monkeypatch.delenv("MNH_CLASSREP_CLOUDFLARE_STT_MODEL", raising=False)
    seen = {}

    def fake_run(model, payload):
        seen["model"] = model
        return {"text": "Recorded lecture"}

    monkeypatch.setattr(voice, "_run", fake_run)
    assert voice.transcribe(b"audio-bytes", "audio/mpeg") == "Recorded lecture"
    assert seen["model"] == voice.STT_MODEL_DEFAULT


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


def test_document_keyword_match_skips_remote_embedding(monkeypatch):
    from app.class_rep import documents

    record = {
        "owner_id": "student-1", "title": "MNH Lipid Profile Notes",
        "page": 2, "text": "Dyslipidaemia is an abnormal lipid profile.",
        "embedding": [],
    }

    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params=()):
            return type("Rows", (), {"fetchall": lambda self: [{"data": json.dumps(record)}]})()

    monkeypatch.setattr(documents, "database", lambda: FakeConnection())
    monkeypatch.setattr(
        documents, "_vectors",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("remote embedding should be skipped")),
    )
    result = documents.search_documents("What is dyslipidaemia?", owner_id="student-1")
    assert len(result) == 1
    assert result[0]["retrieval"] == "keyword"
    assert "abnormal lipid profile" in result[0]["text"]


def test_document_search_does_not_make_remote_embedding_request_for_unmatched_query(monkeypatch):
    from app.class_rep import documents

    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params=()):
            return type("Rows", (), {"fetchall": lambda self: [{
                "data": json.dumps({
                    "owner_id": "student-1", "title": "Placental Malaria",
                    "page": 1, "text": "Placental malaria and pregnancy outcomes.",
                    "embedding": [0.1, 0.2],
                })
            }]})()

    monkeypatch.setattr(documents, "database", lambda: FakeConnection())
    monkeypatch.setattr(
        documents, "_vectors",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("chat must not wait for remote embeddings")),
    )
    assert documents.search_documents("What time is the next session?", owner_id="student-1") == []


def test_calendar_context_omits_unrelated_records_for_general_questions(monkeypatch):
    from app.class_rep import context

    calls = []
    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params=()):
            calls.append((query, params))
            return type("Rows", (), {"fetchall": lambda self: []})()

    monkeypatch.setattr(context, "database", lambda: FakeConnection())
    payload, _ = context.build_calendar_context("What is dyslipidaemia?")
    data = json.loads(payload)
    assert data["context_scope"] == "not required for this question"
    assert data["records"] == {name: [] for name in context.COLLECTIONS}
    assert not any("FROM audit" in query for query, _ in calls)


def test_calendar_context_includes_timetable_records_for_schedule_questions(monkeypatch):
    from app.class_rep import context

    calls = []
    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params=()):
            calls.append((query, params))
            return type("Rows", (), {"fetchall": lambda self: []})()

    monkeypatch.setattr(context, "database", lambda: FakeConnection())
    payload, _ = context.build_calendar_context("What is the next session?")
    data = json.loads(payload)
    assert data["context_scope"] == "timetable"
    assert "cells" in calls[0][1]
    assert "communications" not in calls[0][1]


def test_resource_inventory_query_includes_shared_resources(monkeypatch):
    from app.class_rep import context

    seen = {}
    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params=()):
            seen["query"] = query
            seen["params"] = params
            return type("Rows", (), {"fetchall": lambda self: [
                {"col": "resources", "id": "lecture-1",
                 "data": json.dumps({"title": "MNH lecture notes", "filename": "MNH-notes.pdf"}),
                 "updated_at": 1795000000000}
            ]})()
    monkeypatch.setattr(context, "database", lambda: FakeConnection())
    payload, _ = context.build_calendar_context("Do we have any notes uploaded?")
    data = json.loads(payload)
    assert "resources" in seen["params"]
    assert data["records"]["resources"][0]["filename"] == "MNH-notes.pdf"
    assert data["context_scope"] == "resources"


def test_document_search_uses_semantic_fallback_when_keywords_miss(monkeypatch):
    from app.class_rep import documents

    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params=()):
            if "LIMIT ?" in query:
                return type("Rows", (), {"fetchall": lambda self: []})()
            return type("Rows", (), {"fetchall": lambda self: [
                {"data": json.dumps({"title": "Placental immunology notes", "page": 4,
                                     "text": "Maternal immune tolerance at the placenta.",
                                     "owner_id": "shared", "embedding": [1.0, 0.0]})}
            ]})()
    monkeypatch.setenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", "test-key")
    monkeypatch.setenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "test-account")
    monkeypatch.setattr(documents, "database", lambda: FakeConnection())
    monkeypatch.setattr(documents, "_vectors",
                        lambda texts, prefix, timeout=45: [[1.0, 0.0]])
    results = documents.search_documents("maternal immune adaptation", limit=3)
    assert results
    assert results[0]["title"] == "Placental immunology notes"
    assert results[0]["retrieval"] == "semantic"
    assert results[0]["page"] == 4



def test_default_ai_response_budget_supports_complete_academic_answers(monkeypatch):
    from app.class_rep.config import provider_configs

    monkeypatch.setenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "test-account")
    monkeypatch.setenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", "test-key")
    monkeypatch.delenv("MNH_CLASSREP_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("MNH_CLASSREP_GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("MNH_CLASSREP_GROQ_API_KEY", raising=False)
    monkeypatch.delenv("MNH_CLASSREP_GROQ_BASE_URL", raising=False)

    configured = provider_configs()
    assert configured[0]["max_tokens"] == 1800


def test_recent_document_passages_are_owner_scoped_and_limited(monkeypatch):
    from app.class_rep import documents

    def record(doc_id, title, text, owner="student-1", updated_at=100):
        return {"data": json.dumps({"document_id": doc_id, "title": title,
                                    "owner_id": owner, "page": 1, "text": text}),
                "updated_at": updated_at}

    rows = [
        record("doc-shared", "shared-handout.pdf", "Newer shared handout.",
               owner="shared", updated_at=300),
        record("doc-a", "week-4-notes.pdf", "Second paragraph from the newest upload.",
               updated_at=200),
        record("doc-a", "week-4-notes.pdf", "First paragraph from the newest upload.",
               updated_at=200),
        record("doc-b", "private-notes.txt", "Another student's private notes.",
               owner="student-2", updated_at=400),
    ]

    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params=()):
            return type("Rows", (), {"fetchall": lambda self: rows})()

    monkeypatch.setattr(documents, "database", lambda: FakeConnection())
    passages = documents.recent_document_passages("student-1", document_limit=1, chunk_limit=2)
    assert [item["text"] for item in passages] == [
        "First paragraph from the newest upload.",
        "Second paragraph from the newest upload.",
    ]
    assert all(item["title"] == "week-4-notes.pdf" for item in passages)
    assert all(item["retrieval"] == "recent_upload" for item in passages)



def test_generic_upload_summary_uses_most_recent_document(monkeypatch):
    monkeypatch.setattr(assistant, "build_calendar_context",
                        lambda query="": ("{}", None))
    monkeypatch.setattr(assistant, "search_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(assistant, "recent_document_passages", lambda *args, **kwargs: [
        {"title": "week-4-lecture.mp3", "page": None,
         "text": "Audio transcript from week-4-lecture.mp3: placental malaria.",
         "retrieval": "recent_upload"},
    ])
    seen = {}

    def fake_complete(messages):
        seen["system"] = messages[0]["content"]
        return "Summary of the uploaded lecture.", "test", "test-model"

    monkeypatch.setattr(assistant, "complete", fake_complete)
    answer, provider, _, _ = assistant.reply("Summarise my uploaded lecture notes", [])
    assert answer == "Summary of the uploaded lecture."
    assert provider == "test"
    assert "Audio transcript from week-4-lecture.mp3" in seen["system"]
    assert "most recently indexed document supplied" in seen["system"]
