"""Chichewa conversational-intelligence evaluation suite.

These tests verify the deterministic parts of the language pipeline and the
evidence that reaches the model. They do NOT claim that a live model produced
linguistically perfect Chichewa; tests requiring native-speaker judgement are
marked explicitly with ``native_speaker_review``.
"""
import json
import pytest

from app.class_rep.language_intelligence import (
    detect_language,
    detect_mode,
    language_profile,
    resolve_response_language,
)
from app.class_rep.linguistic_knowledge import (
    lexicon_stats,
    linguistic_context,
    lookup_entries,
)


# ---------------------------------------------------------------------------
# Greetings and everyday conversation (including reported regressions)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("message", [
    "mwadzuka bwanj",
    "Mwadzuka bwanji?",
    "mwaswera bwanj",
    "Mwaswera bwanji?",
    "Moni",
    "Zikomo kwambiri",
    "Eya.",
    "Pitiriza",
    "Chifukwa chiyani?",
    "Fotokozani m'Chichewa.",
])
def test_chichewa_everyday_messages_are_detected_as_chichewa(message):
    assert detect_language(message) == "CH"


@pytest.mark.parametrize("message", [
    "Hello, how are you?",
    "Please explain the study design in detail.",
    "What does preeclampsia mean?",
    "Continue with the calculation.",
])
def test_english_messages_are_not_misdetected_as_chichewa(message):
    assert detect_language(message) == "EN"


def test_empty_input_defaults_to_english():
    assert detect_language("") == "EN"
    assert language_profile("") == {"detected_language": "EN", "mode": "converse"}


# ---------------------------------------------------------------------------
# Meanings, verbs, tense/aspect, negation, pronouns, questions, politeness
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("message,expected_headword", [
    ("Kodi malungo ndi chani?", "malungo"),
    ("Tanthauzo la mawu akuti mwana", "mwana"),
    ("Bukhu ndi ndalama zingati?", "buku"),
    ("Ti-na-pita amatanthauza chiyani?", "ku-pita"),
    ("Pali ndani pano?", "ndani"),
    ("Chonde fotokozani za munthu ndi anthu", "munthu"),
])
def test_meaning_and_grammar_questions_retrieve_source_backed_entries(message, expected_headword):
    entries = lookup_entries(message)
    assert any(entry["term"] == expected_headword for entry in entries), [
        entry["term"] for entry in entries
    ]
    assert all(entry["source"] and entry["verification"] for entry in entries)


def test_curated_entries_never_claim_unavailable_dictionary_verification():
    context = linguistic_context("malungo ndi chani?")
    assert "malaria" in context
    assert "curated-high-confidence" in context
    assert "Never claim a dictionary verified a term" in context
    assert "is not present in this repository" in context


def test_unverified_and_damaged_source_forms_are_flagged():
    liti = lookup_entries("liti")[0]
    assert liti["verification"] == "unverified-damaged-source"
    assert liti["confidence"] == "low"
    window = lookup_entries("zenera windo")[0]
    assert window["verification"] == "requires-native-review"
    assert "windo" in window["variants"]


def test_unknown_term_has_no_invented_lexicon_entry():
    assert lookup_entries("matewe nanga?") == []
    context = linguistic_context("matewe nanga?")
    assert "No curated Chichewa lexical entry" in context
    assert "ask for the surrounding sentence" in context


# ---------------------------------------------------------------------------
# Communication modes: conversing is not the same as translating
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("message,expected_mode", [
    ("Muli bwanji?", "converse"),
    ("Ndili bwino, zikomo. Nanga inu?", "converse"),
    ("Translate 'how are you' into Chichewa", "translate_into_chichewa"),
    ("Fotokozani m'Chichewa", "translate_into_chichewa"),
    ("nd rickets in english", "translate_into_english"),
    ("What is the English meaning of malungo?", "translate_into_english"),
    ("malungo ndi chani?", "explain"),
    ("Explain the pathophysiology of preeclampsia", "academic"),
])
def test_intent_modes_are_separated(message, expected_mode):
    assert detect_mode(message) == expected_mode


@pytest.mark.parametrize("followup", ["eya", "inde", "ayi", "next", "pitiriza", "chifukwa chiyani"])
def test_short_followups_need_history_and_are_not_generic_requests(followup):
    assert detect_mode(followup) == "converse"
    assert detect_mode(followup, [{"role": "assistant", "content": "Previous claim."}]) == "followup"


def test_response_language_follows_target_not_message_language():
    assert resolve_response_language("EN", "nd rickets in english") == "EN"
    assert resolve_response_language("EN", "Translate this into Chichewa") == "CH"
    assert resolve_response_language("EN", "Mwaswera bwanj") == "CH"
    assert resolve_response_language("CH", "Explain this in English please") == "EN"


def test_saved_explicit_preference_is_honoured():
    assert resolve_response_language(
        "EN", "Muli bwanji?", persisted_preference="EN", explicit_preference=True
    ) == "EN"
    assert resolve_response_language(
        "EN", "Hello", persisted_preference="CH", explicit_preference=True
    ) == "CH"


# ---------------------------------------------------------------------------
# Long, multi-turn conversations and code-switching
# ---------------------------------------------------------------------------
def test_contextual_followup_sequence_does_not_reset_language_or_mode():
    conversation = [
        {"message": "Mwaswera bwanji?", "language": "CH"},
        {"message": "Eya.", "language": "CH"},
        {"message": "Chifukwa chiyani?", "language": "CH"},
        {"message": "Pitiriza.", "language": "CH"},
        {"message": "Fotokozani m'Chichewa.", "language": "CH"},
        {"message": "Now explain that in English", "language": "EN"},
    ]
    history = []
    for turn in conversation:
        assert resolve_response_language("EN", turn["message"], history=history) == turn["language"]
        history.append({"role": "user", "content": turn["message"]})
        history.append({"role": "assistant", "content": "A contextual continuation."})


def test_code_switched_academic_question_is_supported_by_evidence():
    message = "Explain preeclampsia but fotokozani m'Chichewa"
    assert detect_mode(message) == "translate_into_chichewa"
    assert resolve_response_language("EN", message) == "CH"
    assert "preeclampsia" in linguistic_context(message)


# ---------------------------------------------------------------------------
# Medical/biomedical terminology and English loanwords
# ---------------------------------------------------------------------------
def test_medical_term_is_grounded_without_fabricated_equivalent():
    context = linguistic_context("malungo ndi chani?")
    assert "malaria" in context
    assert "Plasmodium" not in context  # curated common-usage entry, not a dictionary claim
    rickets = lookup_entries("nd rickets in english")[0]
    assert rickets["verification"] == "policy-backed-loanword"
    assert "inventing a translation" in rickets["grammar"]
    preeclampsia = lookup_entries("preeclampsia")[0]
    assert "No MLW" in preeclampsia["notes"]


# ---------------------------------------------------------------------------
# Independent output validation and bounded repair
# ---------------------------------------------------------------------------
def test_validation_rejects_template_and_unsupported_verification():
    from app.class_rep.output_validation import validate_reply

    assert not validate_reply("Ndife CRARA...", "Moni", "CH").ok
    assert not validate_reply(
        "The dictionary verified that term.", "matewe nanga?", "EN", "explain", True
    ).ok
    assert validate_reply("Ndili bwino, zikomo. Nanga inu?", "Muli bwanji?", "CH").ok


def test_validation_regenerates_once_then_falls_back_honestly(monkeypatch):
    import app.class_rep.assistant as assistant

    calls = []

    def complete(messages):
        calls.append(messages)
        if len(calls) == 1:
            return "I am CRARA and here is a long generic service menu.", "test", "m1"
        return "Ndili bwino, zikomo. Nanga inu?", "test", "m2"

    monkeypatch.setattr(assistant, "build_calendar_context", lambda message: ("{}", None))
    monkeypatch.setattr(assistant, "search_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(assistant, "complete", complete)

    answer, provider, model, _ = assistant.reply("Kodi muli makalasi lero?", [], response_language="CH")
    assert answer == "Ndili bwino, zikomo. Nanga inu?"
    assert "validated" in provider
    assert len(calls) == 2
    assert "OUTPUT VALIDATION FAILED" in calls[1][0]["content"]


def test_persistent_validation_failure_returns_truthful_limitation(monkeypatch):
    import app.class_rep.assistant as assistant

    monkeypatch.setattr(assistant, "build_calendar_context", lambda message: ("{}", None))
    monkeypatch.setattr(assistant, "search_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(assistant, "complete", lambda messages: ("Ndife CRARA...", "test", "m"))
    answer, provider, model, _ = assistant.reply("Kodi muli makalasi lero?", [], response_language="CH")
    assert provider == "validation-fallback"
    assert "sindinathe kutsimikizira" in answer


def test_retrieved_evidence_is_injected_without_full_curriculum(monkeypatch):
    import app.class_rep.assistant as assistant

    captured = {}

    def complete(messages):
        captured["messages"] = messages
        return "Mwana wanga akuphunzira bwino.", "test", "m"

    monkeypatch.setattr(assistant, "build_calendar_context", lambda message: ("{}", None))
    monkeypatch.setattr(assistant, "search_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(assistant, "complete", complete)
    assistant.reply("Kodi mwana wanga akuphunzira bwanji?", [], response_language="CH")
    system = captured["messages"][0]["content"]
    assert "STRUCTURED CHICHEWA LEXICAL KNOWLEDGE" in system
    assert "Verification:" in system
    assert "EVIDENCE RULES" in system
    assert "CURRENT TASK:" in system
    assert "CHICHEWA LEARNING CURRICULUM" not in system
    assert "No relevant uploaded document passages were retrieved." in system


# ---------------------------------------------------------------------------
# Ambiguity and clarification
# ---------------------------------------------------------------------------
def test_ambiguous_short_expression_requests_context_not_invention():
    context = linguistic_context("matewe nd chan")
    # The abbreviated question word may be recognised, but the unknown headword
    # must never acquire an invented entry or a confident dictionary claim.
    assert all(entry["term"] != "matewe" for entry in lookup_entries("matewe nd chan"))
    assert "unverified" in context.casefold() or "Never claim a dictionary" in context
    assert "ask for context when needed" in context


def test_lexicon_integrity():
    stats = lexicon_stats()
    assert stats["entries"] >= 50
    assert stats["version"].startswith("2026.11.19")
    from app.class_rep.linguistic_knowledge import LEXICON_PATH
    data = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    required = {"term", "senses", "pos", "grammar", "source", "verification", "confidence"}
    for entry in data["entries"]:
        assert required.issubset(entry), entry.get("term")


def assistant_module_path():
    import app.class_rep.assistant as assistant
    return assistant.__file__


# ---------------------------------------------------------------------------
# Explicitly NOT validated: real linguistic acceptability needs a native speaker
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="native_speaker_review: requires a fluent Malawian Chichewa speaker to judge idiomatic acceptability")
def test_native_speaker_review_mwaswera_reply():
    assert "Ndaswera bwino, zikomo. Nanga inu?" is not None


@pytest.mark.skip(reason="native_speaker_review: zenera/windo register and regional distribution are unverified")
def test_native_speaker_review_window_variants():
    assert "zenera" and "windo"
