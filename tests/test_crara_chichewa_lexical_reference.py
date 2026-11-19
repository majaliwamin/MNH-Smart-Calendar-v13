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
