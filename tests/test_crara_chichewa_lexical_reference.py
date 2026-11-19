from app.class_rep.lexical_reference import lexical_reference_context


def test_malungo_is_grounded_as_malaria_not_relatives():
    note = lexical_reference_context("malungo ndi chani?")
    assert "means malaria" in note
    assert "does NOT mean relatives" in note
    assert "Do not invent idioms" in note


def test_afternoon_greeting_has_natural_reply():
    note = lexical_reference_context("Mwaswera bwanj")
    assert "Ndaswera bwino, zikomo. Nanga inu?" in note


def test_unmatched_words_do_not_receive_invented_dictionary_entries():
    assert lexical_reference_context("Mudzi ndi chani?") == ""


def test_matching_is_case_insensitive_and_word_bounded():
    assert "means malaria" in lexical_reference_context("MALUNGO")
    assert lexical_reference_context("malungoka") == ""


from app.class_rep.lexical_reference import direct_malungo_definition_answer


def test_direct_malungo_question_gets_deterministic_chichewa_answer():
    answer = direct_malungo_definition_answer("Malungo ndi chani?", "CH")
    assert answer is not None
    assert "matenda a malungo (malaria)" in answer
    assert "achibale" in answer


def test_direct_malungo_question_gets_deterministic_english_answer():
    answer = direct_malungo_definition_answer("What does malungo mean?", "EN")
    assert answer is not None
    assert "malaria" in answer
    assert "does not mean relatives" in answer


def test_malungo_reference_does_not_override_unrelated_questions():
    assert direct_malungo_definition_answer("Tell me about malaria prevention") is None
    assert direct_malungo_definition_answer("Muli bwanji?") is None


def test_live_reply_uses_deterministic_malungo_answer_before_model(monkeypatch):
    import app.class_rep.assistant as assistant

    def unexpected_call(*args, **kwargs):
        raise AssertionError("A curated lexical answer must bypass retrieval and model inference.")

    monkeypatch.setattr(assistant, "build_calendar_context", unexpected_call)
    monkeypatch.setattr(assistant, "search_documents", unexpected_call)
    monkeypatch.setattr(assistant, "complete", unexpected_call)

    answer, provider, model, updated = assistant.reply(
        "Malungo ndi chani?", [], response_language="EN"
    )
    assert "malaria" in answer
    assert "relatives or kin" in answer
    assert provider == "curated-lexicon"
    assert model == "deterministic-lexicon-v2"
    assert updated is None


def test_live_reply_respects_selected_chichewa_for_malungo(monkeypatch):
    import app.class_rep.assistant as assistant

    def unexpected_call(*args, **kwargs):
        raise AssertionError("A curated lexical answer must bypass retrieval and model inference.")

    monkeypatch.setattr(assistant, "build_calendar_context", unexpected_call)
    monkeypatch.setattr(assistant, "search_documents", unexpected_call)
    monkeypatch.setattr(assistant, "complete", unexpected_call)

    answer, provider, model, _ = assistant.reply(
        "Malungo ndi chani?", [], response_language="CH"
    )
    assert "amatanthauza" in answer
    assert "malaria" in answer
    assert provider == "curated-lexicon"


def test_unverified_word_follow_up_does_not_receive_invented_definition():
    from app.class_rep.lexical_reference import unverified_chichewa_term_answer

    answer = unverified_chichewa_term_answer("matewe nanga?", "EN")
    assert answer is not None
    assert "sufficiently verified" in answer
    assert "guess" in answer


def test_unverified_word_guard_respects_chichewa_response_setting():
    from app.class_rep.lexical_reference import unverified_chichewa_term_answer

    answer = unverified_chichewa_term_answer("matewe nanga?", "CH")
    assert answer is not None
    assert "Sindikufuna kungoyerekezera" in answer


def test_unverified_word_guard_does_not_intercept_long_or_normal_questions():
    from app.class_rep.lexical_reference import unverified_chichewa_term_answer

    assert unverified_chichewa_term_answer("Explain malaria prevention in detail") is None
    assert unverified_chichewa_term_answer("Muli bwanji?") is None
