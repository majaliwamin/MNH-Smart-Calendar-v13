"""Tests for provider-error hygiene and the curated quadratic derivation."""
from starlette.requests import Request

from app.class_rep import assistant, routes
from app.class_rep.error_hygiene import clean_conversation_messages, clean_history
from app.class_rep.math_engine import capabilities, solve
from app.class_rep.math_engine.presentation import deterministic_math_answer
from app.class_rep.output_validation import validate_reply


def _stub_context(monkeypatch):
    monkeypatch.setattr(assistant, "build_calendar_context",
                        lambda query="": ('{"records":{}}', "2026-11-20T10:00"))
    monkeypatch.setattr(assistant, "search_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(assistant, "linguistic_context",
                        lambda message: "No structured lexical entry matched this turn.")


def test_quadratic_formula_derivation_is_deterministic_and_validation_safe():
    result = solve("Derive the quadratic formula.")
    assert result is not None
    assert result.operation == "quadratic_formula_derivation"
    assert result.status == "concept"
    assert result.values["formula"] == r"x=\frac{-b\pm\sqrt{b^{2}-4ac}}{2a}"
    assert len(result.steps) == 7
    assert "curated quadratic-formula derivation" in capabilities()["pure_mathematics"]

    answer = deterministic_math_answer(result)
    validation = validate_reply(answer, "Derive the quadratic formula.", "EN", math_result=result)
    assert validation.ok, validation.reasons


def test_history_cleaning_drops_service_error_turns_but_keeps_user_words():
    history = [
        {"role": "user", "content": "Derive the quadratic formula."},
        {"role": "assistant", "content":
            "CRARA service error: All configured CRARA AI providers are temporarily unavailable."},
        {"role": "assistant", "content":
            "The previous message was an automated system error. The formula is x = (-b ± √(b²-4ac))/(2a)."},
    ]
    cleaned = clean_history(history)
    assert len(cleaned) == 2
    assert cleaned[0]["role"] == "user"
    assert cleaned[1]["content"].startswith("The formula is")

    persisted = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "AI service providers were temporarily unavailable."},
    ]
    assert len(clean_conversation_messages(persisted)) == 1


def test_assistant_does_not_replay_errors_from_history_or_memory(monkeypatch):
    _stub_context(monkeypatch)
    seen = {}

    def fake_complete(messages):
        seen["system"] = messages[0]["content"]
        return "The examination time is not recorded.", "cloudflare", "test-model"

    monkeypatch.setattr(assistant, "complete", fake_complete)
    history = [
        {"role": "user", "content": "What time is the exam?"},
        {"role": "assistant", "content": "CRARA service error: providers temporarily unavailable."},
    ]
    memory_context = (
        "ACTIVE CONVERSATION HISTORY: CRARA service error: All configured AI providers were "
        "temporarily unavailable. KEEP THIS: the seminar is on Thursday."
    )
    answer, provider, _, _ = assistant.reply(
        "What time is the exam?", history, memory_context=memory_context
    )
    assert answer == "The examination time is not recorded."
    assert provider == "cloudflare"
    folded = seen["system"].casefold()
    assert "service error" not in folded
    assert "automated system error" not in folded
    assert "temporarily unavailable" not in folded
    assert "the seminar is on thursday" in folded


def test_validation_rejects_paraphrased_errors_and_malformed_latex():
    error_reply = (
        "The previous message was an automated system error indicating that the AI service "
        "providers were temporarily unavailable. Here is the derivation."
    )
    result = validate_reply(error_reply, "Derive the quadratic formula.", "EN")
    assert not result.ok
    assert any("transient" in reason or "banned" in reason for reason in result.reasons)

    malformed = r"Subtract \\(\frac{c}{a}\\) and \(\left\(\frac{b}{2a}\right\)^2\)."
    result = validate_reply(malformed, "Derive the quadratic formula.", "EN")
    assert not result.ok
    assert any("double-escaped" in reason for reason in result.reasons)
    assert any("nested" in reason for reason in result.reasons)

    legitimate = validate_reply(
        "AI service providers process language requests online.",
        "What are AI service providers?", "EN"
    )
    assert legitimate.ok, legitimate.reasons


def test_conversation_turn_does_not_persist_service_error_replies(monkeypatch):
    saved = []
    monkeypatch.setattr(routes, "_user", lambda request: {"id": "user-1"})
    monkeypatch.setattr(routes, "_explicit_project", lambda *args, **kwargs: None)
    monkeypatch.setattr(routes, "_explicit_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(routes, "_explicit_reminder", lambda *args, **kwargs: None)
    monkeypatch.setattr(routes.memory, "save_turn", lambda *args: saved.append(args))

    request = Request({"type": "http"})
    failed = routes.conversation_turn(request, {
        "message": "Derive the quadratic formula.",
        "reply": "CRARA service error: AI service providers were temporarily unavailable.",
        "conversation_id": "c1",
    })
    assert failed["saved"] is False
    assert saved == []

    succeeded = routes.conversation_turn(request, {
        "message": "Derive the quadratic formula.",
        "reply": "Here is the derivation.",
        "conversation_id": "c1",
    })
    assert succeeded["saved"] is True
    assert len(saved) == 1
