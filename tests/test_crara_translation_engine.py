from app.class_rep.translation_engine import (
    TRANSLATION_ENGINE_INSTRUCTIONS,
    build_translation_reference_context,
    is_translation_or_interpretation_request,
)


def test_detects_both_translation_directions_and_interpretation():
    assert is_translation_or_interpretation_request("Translate 'I am pregnant' into Chichewa")
    assert is_translation_or_interpretation_request("What does malungo mean?")
    assert is_translation_or_interpretation_request("Malungo ndi chani?")
    assert is_translation_or_interpretation_request("How do you say zikomo in English?")
    assert not is_translation_or_interpretation_request("Mwaswera bwanji?")
    assert not is_translation_or_interpretation_request("Please update the timetable")


def test_reference_retrieval_is_owner_scoped_and_deduplicated():
    calls = []

    def search(query, limit, owner_id):
        calls.append((query, limit, owner_id))
        return [
            {"title": "Medical Terms – Mawu a za Chipatala", "page": 10,
             "text": "abdomen — mimba", "score": 2, "retrieval": "keyword"},
            {"title": "Medical Terms – Mawu a za Chipatala", "page": 10,
             "text": "abdomen — mimba", "score": 2, "retrieval": "keyword"},
        ]

    context = build_translation_reference_context(
        "Translate abdominal pain into Chichewa for a clinical research form",
        owner_id="account-123",
        search=search,
    )
    assert "Medical Terms – Mawu a za Chipatala" in context
    assert "page 10" in context
    assert "abdomen — mimba" in context
    assert len(calls) >= 1
    assert all(call[2] == "account-123" for call in calls)


def test_missing_reference_is_reported_without_claiming_verification():
    context = build_translation_reference_context(
        "What does an unverified Chichewa expression mean?",
        search=lambda *args, **kwargs: [],
    )
    assert "No matching passage was retrieved" in context
    assert "Do not claim that a dictionary verified the answer" in context


def test_non_translation_chat_does_not_trigger_document_retrieval():
    called = []

    def search(*args, **kwargs):
        called.append(True)
        return []

    assert build_translation_reference_context(
        "When is our next lecture?", search=search
    ) == ""
    assert not called


def test_reply_injects_translation_engine_and_retrieved_reference(monkeypatch):
    import app.class_rep.assistant as assistant
    from app.class_rep.translation_engine import TRANSLATION_ENGINE_INSTRUCTIONS

    captured = {}

    monkeypatch.setattr(assistant, "build_calendar_context", lambda message: ("{}", None))
    monkeypatch.setattr(assistant, "search_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        assistant,
        "build_translation_reference_context",
        lambda message, owner_id="shared": (
            "Retrieved reference: Medical Terms – Mawu a za Chipatala, page 10\n"
            "abdominal pain — ululu wa m’mimba"
        ),
    )

    def complete(messages):
        captured["system"] = messages[0]["content"]
        return "Ululu wa m’mimba.", "test-provider", "test-model"

    monkeypatch.setattr(assistant, "complete", complete)
    answer, provider, model, _ = assistant.reply(
        "Translate abdominal pain into Chichewa for a patient information sheet",
        [], owner_id="shared", response_language="EN"
    )
    assert answer == "Ululu wa m’mimba."
    assert provider == "test-provider"
    assert model == "test-model"
    assert TRANSLATION_ENGINE_INSTRUCTIONS in captured["system"]
    assert "Medical Terms – Mawu a za Chipatala" in captured["system"]
    assert "abdominal pain — ululu wa m’mimba" in captured["system"]


def test_morning_greeting_is_natural_and_deterministic():
    from app.class_rep.lexical_reference import direct_chichewa_conversation_answer

    answer = direct_chichewa_conversation_answer("mwadzuka bwanj", "CH")
    assert answer == "Tadzuka bwino, zikomo. Inu mwadzuka bwanji?"
    assert "Ndin bwanji" not in answer


def test_yes_after_assistant_offer_continues_conversation_without_menu():
    from app.class_rep.lexical_reference import direct_chichewa_conversation_answer

    history = [
        {"role": "assistant", "content": "Kodi nditha kukuthandizani ndi kanthu lero?"},
    ]
    answer = direct_chichewa_conversation_answer("eya", "CH", history)
    assert answer == "Chabwino. Ndi nkhani iti imene mukufuna tikambirane?"
    assert "PhD" not in answer
    assert "Mukhoza kundifunsira" not in answer


def test_short_greeting_respects_selected_english_language():
    from app.class_rep.lexical_reference import direct_chichewa_conversation_answer

    answer = direct_chichewa_conversation_answer("mwadzuka bwanji?", "EN")
    assert answer.startswith("That is a morning greeting")
