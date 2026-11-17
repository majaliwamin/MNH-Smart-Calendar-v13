from app.class_rep.providers import _extract_chat_content


def test_extracts_openai_compatible_chat_content():
    payload = {
        "choices": [
            {"message": {"role": "assistant", "content": "CRARA is ready."}}
        ]
    }
    assert _extract_chat_content(payload) == "CRARA is ready."


def test_extracts_text_parts_from_chat_content():
    payload = {
        "choices": [
            {"message": {"role": "assistant", "content": [
                {"type": "text", "text": "CRARA "},
                {"type": "text", "text": "is ready."},
            ]}}
        ]
    }
    assert _extract_chat_content(payload) == "CRARA is ready."


def test_returns_none_for_missing_or_unsupported_content():
    assert _extract_chat_content({}) is None
    assert _extract_chat_content({"choices": [{"message": {"content": None}}]}) is None
    assert _extract_chat_content({"choices": [{"message": {"content": [{"type": "image"}]}}]}) is None
