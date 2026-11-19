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
