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
    assert "Do not infer a complete conjugation rule" in lesson


def test_assistant_context_includes_source_cautions_for_verb_patterns():
    from app.class_rep.language import CHICHEWA_CURRICULUM_CONTEXT
    assert "lesson-03-common-verbs-simple-sentences.md" in CHICHEWA_CURRICULUM_CONTEXT
    assert "do not generalise its limited examples" in CHICHEWA_CURRICULUM_CONTEXT


def test_chichewa_noun_classes_lesson_teaches_pairs_and_concord_cautiously():
    from pathlib import Path
    lesson = (Path(__file__).resolve().parents[1] / "docs" / "crara-chichewa-lessons" / "lesson-04-noun-classes-agreement.md").read_text(encoding="utf-8")
    assert "munthu" in lesson and "anthu" in lesson
    assert "mwana" in lesson and "ana" in lesson
    assert "buku labwino" in lesson and "mabuku abwino" in lesson
    assert "not a complete subject-marker chart" in lesson
    assert "do not" in lesson.lower()


def test_assistant_context_includes_noun_class_lesson_and_cautions():
    from app.class_rep.language import CHICHEWA_CURRICULUM_CONTEXT
    assert "lesson-04-noun-classes-agreement.md" in CHICHEWA_CURRICULUM_CONTEXT
    assert "Do not guess noun classes" in CHICHEWA_CURRICULUM_CONTEXT



def test_chichewa_pronouns_and_demonstratives_lesson_keeps_forms_distinct():
    from pathlib import Path
    lesson = (Path(__file__).resolve().parents[1] / "docs" / "crara-chichewa-lessons" / "lesson-05-pronouns-demonstratives.md").read_text(encoding="utf-8")
    assert "ine" in lesson and "iwe" in lesson and "iye" in lesson
    assert "ife" in lesson and "inu" in lesson and "iwo" in lesson
    assert "independent pronoun" in lesson
    assert "subject markers" in lesson
    assert "Ichi ndi chani?" in lesson
    assert "not a complete demonstrative or concord chart" in lesson


def test_assistant_context_includes_pronoun_and_demonstrative_cautions():
    from app.class_rep.language import CHICHEWA_CURRICULUM_CONTEXT
    assert "lesson-05-pronouns-demonstratives.md" in CHICHEWA_CURRICULUM_CONTEXT
    assert "Distinguish independent pronouns" in CHICHEWA_CURRICULUM_CONTEXT
    assert "do not invent a complete near/far" in CHICHEWA_CURRICULUM_CONTEXT


def test_chichewa_question_words_lesson_teaches_supported_forms_cautiously():
    from pathlib import Path
    lesson = (Path(__file__).resolve().parents[1] / "docs" / "crara-chichewa-lessons" / "lesson-06-asking-questions.md").read_text(encoding="utf-8")
    assert "**ndani?**" in lesson
    assert "**chani?**" in lesson
    assert "**kuti?**" in lesson
    assert "**chifukwa?**" in lesson
    assert "**zingati?**" in lesson
    assert "mismatched" in lesson
    assert "do not" in lesson.lower()


def test_assistant_context_includes_question_word_lesson_and_source_cautions():
    from app.class_rep.language import CHICHEWA_CURRICULUM_CONTEXT
    assert "lesson-06-asking-questions.md" in CHICHEWA_CURRICULUM_CONTEXT
    assert "ndani (who)" in CHICHEWA_CURRICULUM_CONTEXT
    assert "page 33 liti quiz line is mismatched" in CHICHEWA_CURRICULUM_CONTEXT


def test_crara_language_toggle_owner_check_uses_authenticated_email_only():
    from app.class_rep.routes import _is_language_toggle_owner
    assert _is_language_toggle_owner({"id": "owner", "email": "majaliwamin@gmail.com"})
    assert _is_language_toggle_owner({"email": "MAJALIOWAMIN@GMAIL.COM"})
    assert not _is_language_toggle_owner({"id": "owner", "email": "someone@example.com"})
    assert not _is_language_toggle_owner({"email": ""})
    assert not _is_language_toggle_owner({})



def test_chichewa_possession_lesson_teaches_only_source_supported_example():
    from pathlib import Path
    lesson = (Path(__file__).resolve().parents[1] / "docs" / "crara-chichewa-lessons" / "lesson-07-possession.md").read_text(encoding="utf-8")
    assert "mwana wanga" in lesson
    assert "my child" in lesson
    assert "does not provide a complete table" in lesson
    assert "do not" in lesson.lower()


def test_assistant_context_includes_possession_lesson_and_cautions():
    from app.class_rep.language import CHICHEWA_CURRICULUM_CONTEXT
    assert "lesson-07-possession.md" in CHICHEWA_CURRICULUM_CONTEXT
    assert "mwana wanga" in CHICHEWA_CURRICULUM_CONTEXT
    assert "do not invent a full possessive paradigm" in CHICHEWA_CURRICULUM_CONTEXT



def test_chichewa_adjectives_lesson_uses_documented_agreement_examples():
    from pathlib import Path
    lesson = (Path(__file__).resolve().parents[1] / "docs" / "crara-chichewa-lessons" / "lesson-08-adjectives-modifiers.md").read_text(encoding="utf-8")
    assert "munthu wabwino" in lesson and "anthu abwino" in lesson
    assert "mwana wabwino" in lesson and "ana abwino" in lesson
    assert "chinthu chabwino" in lesson and "zinthu zabwino" in lesson
    assert "buku labwino" in lesson and "mabuku abwino" in lesson
    assert "not a complete chart" in lesson.lower()
    assert "do not" in lesson.lower()


def test_assistant_context_includes_adjective_lesson_and_agreement_cautions():
    from app.class_rep.language import CHICHEWA_CURRICULUM_CONTEXT
    assert "lesson-08-adjectives-modifiers.md" in CHICHEWA_CURRICULUM_CONTEXT
    assert "munthu wabwino/anthu abwino" in CHICHEWA_CURRICULUM_CONTEXT
    assert "Distinguish adjective agreement" in CHICHEWA_CURRICULUM_CONTEXT


def test_chichewa_adverbs_lesson_uses_source_listed_time_place_and_manner_forms():
    from pathlib import Path
    lesson = (Path(__file__).resolve().parents[1] / "docs" / "crara-chichewa-lessons" / "lesson-09-adverbs-time-place-manner.md").read_text(encoding="utf-8")
    for form in ("lero", "mawa", "tsopano", "madzulo", "posachedwa", "pano", "apo", "pafupi", "patali", "mofulumira", "pang’ono pang’ono"):
        assert form in lesson
    assert "Adjectives/adverbs/Other" in lesson
    assert "do not" in lesson.lower()


def test_assistant_context_includes_adverbs_lesson_and_source_limitations():
    from app.class_rep.language import CHICHEWA_CURRICULUM_CONTEXT
    assert "lesson-09-adverbs-time-place-manner.md" in CHICHEWA_CURRICULUM_CONTEXT
    assert "mofulumira" in CHICHEWA_CURRICULUM_CONTEXT
    assert "do not infer a full paradigm" in CHICHEWA_CURRICULUM_CONTEXT
