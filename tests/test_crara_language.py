from app.class_rep.language import (
    normalize_response_language,
    response_language_instruction,
)


def test_response_language_defaults_to_english():
    assert normalize_response_language(None) == "EN"
    assert normalize_response_language("") == "EN"
    assert normalize_response_language("unknown") == "EN"


def test_response_language_accepts_chichewa_and_english_case_insensitively():
    assert normalize_response_language("ch") == "CH"
    assert normalize_response_language("EN") == "EN"


def test_chichewa_instruction_is_explicit_and_preserves_technical_meaning():
    instruction = response_language_instruction("CH")
    assert "CHICHEWA (CH)" in instruction
    assert "standard Malawian Chichewa" in instruction
    assert "mathematical notation" in instruction
    assert "Do not invent Chichewa technical terminology" in instruction


def test_english_mode_does_not_auto_switch_for_chichewa_questions():
    instruction = response_language_instruction("EN")
    assert "ENGLISH (EN)" in instruction
    assert "Do not automatically switch to Chichewa" in instruction


def test_curriculum_context_starts_with_the_alphabet_and_keeps_source_caveats():
    from app.class_rep.language import CHICHEWA_CURRICULUM_CONTEXT
    assert "a, e, i, o, u" in CHICHEWA_CURRICULUM_CONTEXT
    assert "L/R, Dz/Z and Ts/S" in CHICHEWA_CURRICULUM_CONTEXT
    assert "do not describe a draft as an approved replacement" in CHICHEWA_CURRICULUM_CONTEXT


def test_chichewa_greetings_lesson_preserves_user_source_forms():
    from pathlib import Path
    lesson = (Path(__file__).resolve().parents[1] / "docs" / "crara-chichewa-lessons" / "lesson-02-greetings-introductions.md").read_text(encoding="utf-8")
    assert "Muli bwanji?" in lesson
    assert "Ndi-li bwino" in lesson
    assert "Dzina lako/lanu ndani?" in lesson
    assert "printed forms rather than quietly correcting them" in lesson


def test_assistant_context_includes_source_caution_for_greetings():
    from app.class_rep.language import CHICHEWA_CURRICULUM_CONTEXT
    assert "Muli bwanji?" in CHICHEWA_CURRICULUM_CONTEXT
    assert "do not silently normalise them" in CHICHEWA_CURRICULUM_CONTEXT


def test_chichewa_verbs_lesson_preserves_source_examples_and_caveats():
    from pathlib import Path
    lesson = (Path(__file__).resolve().parents[1] / "docs" / "crara-chichewa-lessons" / "lesson-03-common-verbs-simple-sentences.md").read_text(encoding="utf-8")
    assert "ku-lankhula" in lesson
    assert "Ti-ma-pita" in lesson
    assert "Ti-na-pita" in lesson
    assert "Ti-dza-pita" in lesson
    assert "do not infer a complete conjugation rule" in lesson


def test_assistant_context_includes_source_cautions_for_verb_patterns():
    from app.class_rep.language import CHICHEWA_CURRICULUM_CONTEXT
    assert "lesson-03-common-verbs-simple-sentences.md" in CHICHEWA_CURRICULUM_CONTEXT
    assert "do not generalise its limited examples" in CHICHEWA_CURRICULUM_CONTEXT
