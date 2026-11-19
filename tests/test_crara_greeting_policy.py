from app.class_rep.assistant import SYSTEM_PROMPT


def test_crara_greeting_is_only_used_for_greeting_only_openers():
    assert "only when the user's message is itself a greeting" in SYSTEM_PROMPT
    assert "If a greeting is followed by a question, request, topic, instruction or substantive information" in SYSTEM_PROMPT
    assert "Do not replace it with an introduction" in SYSTEM_PROMPT


def test_crara_does_not_repeat_generic_introduction_in_follow_up_turns():
    assert "After the opening greeting has already occurred" in SYSTEM_PROMPT
    assert "Interpret short follow-ups such as" in SYSTEM_PROMPT
    assert "Do not output the phrase \"Ndife CRARA...\"" in SYSTEM_PROMPT


def test_crara_display_identity_uses_class_rep_wording():
    assert "CRARA (Class Rep & Academic Relations Assistant)" in SYSTEM_PROMPT
    assert "Classroom Representative & Academic Relations Assistant" not in SYSTEM_PROMPT
