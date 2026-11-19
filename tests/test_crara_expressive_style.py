"""Expressive style is limited to casual social turns."""
import app.class_rep.assistant as assistant
from app.class_rep.expressive_style import (
    ALL_EMOJIS,
    CASUAL_MODES,
    CURATED_JOKES_EN,
    VERIFIED_INFORMAL_CHICHEWA,
    VERIFIED_LIGHT_CHICHEWA,
    casual_flourish,
    casual_style_block,
)
from app.class_rep.language_intelligence import (
    detect_mode,
    detect_tone,
    language_profile,
    tone_style_instruction,
)


def test_emoji_palette_covers_faces_microbiology_mother_baby_and_study():
    for emoji in ("🤣", "😂", "😭", "😐", "🦠", "🧬", "🔬", "🤰", "👶", "🍼", "🩺", "📝", "📚"):
        assert emoji in ALL_EMOJIS


def test_curated_jokes_are_short_clean_and_not_medical_advice():
    assert len(CURATED_JOKES_EN) >= 4
    for joke in CURATED_JOKES_EN:
        assert len(joke) < 140
        assert "dose" not in joke.casefold()
        assert "diagnos" not in joke.casefold()
    assert all("😊" in line or "🙂" in line or "😄" in line or "👋" in line
               for line in VERIFIED_LIGHT_CHICHEWA)


def test_verified_chichewa_forms_stay_within_curated_greeting_lessons():
    forms = {form for form, _ in VERIFIED_INFORMAL_CHICHEWA}
    assert {"Moni", "Muli bwanji?", "Eya", "Chabwino", "Zikomo"} <= forms
    assert all("slang" not in note.casefold() for _, note in VERIFIED_INFORMAL_CHICHEWA)


def test_tone_detection_distinguishes_playful_distressed_and_neutral():
    assert detect_tone("haha 🤣 that is funny") == "playful"
    assert detect_tone("I am so anxious about the results 😭") == "distressed"
    assert detect_tone("Explain the study design in detail") == "neutral"
    assert language_profile("Moni!")["tone"] in {"warm", "playful"}


def test_short_casual_topic_mention_does_not_become_an_academic_turn():
    assert detect_mode("Just finished microbiology lab 🦠") == "converse"
    assert detect_mode("microbiology") == "converse"
    assert detect_mode("Explain microbiology to me") == "academic"
    assert detect_mode("What is preeclampsia?") == "academic"


def test_style_block_is_gated_to_non_distressed_social_turns():
    assert "CURATED SOCIAL LINES" in casual_style_block("converse", "playful", "EN")
    assert "CURATED SOCIAL LINES" in casual_style_block("followup", "warm", "CH")
    assert casual_style_block("academic", "warm", "EN") == ""
    assert casual_style_block("translate_into_chichewa", "playful", "EN") == ""
    assert casual_style_block("explain", "playful", "EN") == ""
    assert casual_style_block("converse", "distressed", "EN") == ""
    assert tone_style_instruction("distressed", "converse", "EN") == ""
    assert CASUAL_MODES == {"converse", "followup"}


def test_chichewa_style_block_forbids_invented_slang():
    block = casual_style_block("converse", "warm", "CH")
    assert "do not invent slang" in block
    assert "Moni" in block
    assert "CURATED SOCIAL LINES" in block


def test_casual_flourish_adds_one_mood_or_topic_emoji():
    assert casual_flourish("Hello! How are you?", "haha") .endswith("🤣")
    assert casual_flourish("Moni! Muli bwanji?", "Moni", "CH").endswith("🙂")
    assert casual_flourish("Nice!", "just finished microbiology lab").endswith("🦠")
    assert casual_flourish("Hi", "baby monitoring shift").endswith("🤰👶")


def test_live_greeting_gets_emoji_but_medical_definition_does_not(monkeypatch):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("Curated answers must bypass retrieval and model inference.")

    monkeypatch.setattr(assistant, "build_calendar_context", unexpected_call)
    monkeypatch.setattr(assistant, "search_documents", unexpected_call)
    monkeypatch.setattr(assistant, "complete", unexpected_call)

    greeting, provider, _, _ = assistant.reply("Moni", [], response_language="CH")
    assert provider == "curated-lexicon"
    assert greeting.endswith("🙂")

    definition, provider, _, _ = assistant.reply("Malungo ndi chani?", [], response_language="CH")
    assert provider == "curated-lexicon"
    assert "malaria" in definition.casefold()
    assert not any(emoji in definition for emoji in ("🙂", "🤣", "🦠"))


def test_model_prompt_includes_style_only_for_casual_turns(monkeypatch):
    captured = {}

    def fake_complete(messages):
        captured["system"] = messages[0]["content"]
        return "Hey! Good to see you 😊", "test-provider", "test-model"

    monkeypatch.setattr(assistant, "build_calendar_context", lambda *a, **k: ("{}", None))
    monkeypatch.setattr(assistant, "search_documents", lambda *a, **k: [])
    monkeypatch.setattr(assistant, "complete", fake_complete)

    assistant.reply("Hey there! How's your week going?", [], response_language="EN")
    assert "CASUAL SOCIAL STYLE" in captured["system"]
    assert "CURATED SOCIAL LINES" in captured["system"]

    assistant.reply("Explain the pathophysiology of preeclampsia", [], response_language="EN")
    assert "CASUAL SOCIAL STYLE" not in captured["system"]
