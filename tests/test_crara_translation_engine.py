from app.class_rep import translation


def test_detect_language_chichewa_and_english():
    assert translation.detect_language("Muli bwanji, ndikufuna thandizo") == "CH"
    assert translation.detect_language("Please translate this into English") == "EN"
    assert translation.detect_language("Matewe") == "AUTO"


def test_mlw_glossary_matches_and_cites_printed_page():
    matches = translation.glossary_matches("Explain placental abruption and maternal and neonatal health")
    terms = {item["en"] for item in matches}
    assert "placental abruption" in terms
    assert "maternal and neonatal health" in terms
    context = translation.glossary_context("placental abruption")
    assert "printed p. 11" in context
    assert "kuchoka kwa nsengwa" in context


def test_mlw_glossary_matches_chichewa_source_phrases():
    matches = translation.glossary_matches("Wodwalayo akumva ululu wa m'mimba.")
    terms = {item["en"] for item in matches}
    assert "patient" in terms
    assert "abdominal pain" in terms


def test_glossary_does_not_force_unmatched_terms():
    assert translation.glossary_context("matewe") == (
        "No exact MLW glossary entry matched. Do not invent a dictionary citation or force a technical equivalent."
    )


def test_translation_instruction_preserves_semantics_and_register():
    prompt = translation.translation_instruction(
        "CH", "EN", "professional", "clinical", "interpret",
        translation.glossary_context("patient")
    )
    assert "Source language: Chichewa. Target language: English." in prompt
    assert "negation" in prompt
    assert "natural, idiomatic Malawian Chichewa" in prompt
    assert "printed p. 101" in prompt


def test_translate_text_uses_specialized_provider_prompt(monkeypatch):
    seen = {}

    def fake_complete(messages):
        seen["system"] = messages[0]["content"]
        seen["user"] = messages[1]["content"]
        return "The patient has abdominal pain.", "test-provider", "test-model"

    monkeypatch.setattr(translation, "complete", fake_complete)
    answer, provider, model = translation.translate_text(
        "Wodwalayo akumva ululu wa m'mimba.",
        "CH", "EN", "clinical", "medicine", "translate"
    )
    assert answer == "The patient has abdominal pain."
    assert (provider, model) == ("test-provider", "test-model")
    assert "Source language: Chichewa. Target language: English." in seen["system"]
    assert "abdominal pain" in seen["system"]
    assert seen["user"].startswith("Wodwalayo")


def test_auto_direction_is_bidirectional(monkeypatch):
    seen = []

    def fake_complete(messages):
        seen.append(messages[0]["content"])
        return "translated", "test-provider", "test-model"

    monkeypatch.setattr(translation, "complete", fake_complete)
    translation.translate_text("Muli bwanji?", "AUTO", "AUTO")
    translation.translate_text("How are you?", "AUTO", "AUTO")
    assert "Source language: Chichewa. Target language: English." in seen[0]
    assert "Source language: English. Target language: Chichewa." in seen[1]



def test_explicit_target_language_overrides_default_selector():
    assert translation.requested_target_language("Translate this into English", "CH") == "EN"
    assert translation.requested_target_language("Translate this into Chichewa", "EN") == "CH"


def test_chat_translation_infers_interpretation_and_register():
    assert translation.requested_mode("Interpret the intended meaning in context") == "interpret"
    assert translation.requested_register("Translate this for a clinical consultation") == "clinical"
