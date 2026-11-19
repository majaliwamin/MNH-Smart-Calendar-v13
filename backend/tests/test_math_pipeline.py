"""Integration tests for deterministic computation inside the CRARA reply pipeline."""
from app.class_rep import assistant
from app.class_rep.output_validation import validate_reply
from app.class_rep.math_engine import probability, solve
from app.class_rep.math_engine.presentation import blocked_math_answer
from app.class_rep.math_engine.results import MathResult, blocked_result


def _stub_context(monkeypatch, documents=None):
    monkeypatch.setattr(
        assistant, "build_calendar_context",
        lambda query="": ('{"records":{"examinations":[]}}', "2026-11-20T10:00"),
    )
    monkeypatch.setattr(assistant, "search_documents", lambda *args, **kwargs: documents or [])
    monkeypatch.setattr(
        assistant, "linguistic_context",
        lambda message: "No structured lexical entry matched this turn.",
    )


def test_math_evidence_is_injected_into_real_chat_prompt(monkeypatch):
    _stub_context(monkeypatch)
    seen = {}

    def fake_complete(messages):
        seen["system"] = messages[0]["content"]
        return "Mean 4, median 4, Q1 3, Q3 5, IQR 2.", "cloudflare", "test-model"

    monkeypatch.setattr(assistant, "complete", fake_complete)
    answer, provider, model, _ = assistant.reply("Calculate the mean of 2, 4 and 6.", [])
    assert answer.startswith("Mean 4")
    assert provider == "cloudflare" and model == "test-model"
    assert "VERIFIED COMPUTATION CONTRACT" in seen["system"]
    assert '"mean": 4' in seen["system"]
    assert '"operation": "descriptive_statistics"' in seen["system"]


def test_failed_math_validation_falls_back_to_deterministic_answer(monkeypatch):
    _stub_context(monkeypatch)
    calls = []

    def fake_complete(messages):
        calls.append(messages[-1]["content"])
        return "The mean is 99.", "cloudflare", "test-model"

    monkeypatch.setattr(assistant, "complete", fake_complete)
    answer, provider, model, _ = assistant.reply("Calculate the mean of 2, 4 and 6.", [])
    assert len(calls) == 2
    assert provider == "deterministic-math"
    assert model == "rule-based-v1"
    assert "Verified calculation" in answer
    assert "mean is 4" in answer.lower() or '"mean": 4' in answer
    assert "mean is 99" not in answer.lower()
    assert "Reproducible code" in answer


def test_missing_math_input_is_refused_without_calling_provider(monkeypatch):
    _stub_context(monkeypatch)

    def forbidden_complete(messages):
        raise AssertionError("provider must not be called for missing inputs")

    monkeypatch.setattr(assistant, "complete", forbidden_complete)
    answer, provider, model, _ = assistant.reply("Calculate the mean of these observations", [])
    assert "cannot calculate" in answer.lower()
    assert provider == "deterministic-math"
    assert "blocked" in model
    assert "4" not in answer


def test_registry_symbol_lookup_bypasses_unknown_lexical_guard(monkeypatch):
    _stub_context(monkeypatch)

    def forbidden_lexical_guard(*args, **kwargs):
        raise AssertionError("mathematical registry entries are curated knowledge")

    monkeypatch.setattr(assistant, "unknown_term_answer", forbidden_lexical_guard)
    monkeypatch.setattr(
        assistant, "complete",
        lambda messages: ("μ denotes the population mean in this statistics context.", "cloudflare", "test-model"),
    )
    answer, provider, _, _ = assistant.reply("What does μ mean in statistics?", [])
    assert "population mean" in answer
    assert provider == "cloudflare"


def test_explicit_translation_mode_still_overrides_math_registry(monkeypatch):
    _stub_context(monkeypatch)
    seen = {}

    def fake_complete(messages):
        seen["system"] = messages[0]["content"]
        return "μ: chiwerengero.", "cloudflare", "test-model"

    monkeypatch.setattr(assistant, "complete", fake_complete)
    monkeypatch.setattr(assistant, "detect_mode", lambda *args, **kwargs: "translate_into_chichewa")
    _, provider, _, _ = assistant.reply("What does μ mean in statistics?", [])
    assert provider == "cloudflare"
    assert "DEDICATED ENGLISH <-> CHICHEWA TRANSLATION" in seen["system"]
    assert "VERIFIED COMPUTATION CONTRACT" not in seen["system"]


def test_uploaded_csv_passage_is_used_without_prompting_model_to_calculate(monkeypatch):
    csv_text = "age,hb\n20,12\n21,13\n22,11\n23,14\n"
    _stub_context(monkeypatch, documents=[{"text": csv_text, "title": "haemoglobin.csv"}])
    seen = {}

    def fake_complete(messages):
        seen["system"] = messages[0]["content"]
        return (
            "Rows 4, columns 2, hb mean 12.5. No missing cells and no duplicate rows.",
            "cloudflare", "test-model",
        )

    monkeypatch.setattr(assistant, "complete", fake_complete)
    answer, provider, _, _ = assistant.reply("Summarise the uploaded data", [])
    assert "hb mean 12.5" in answer
    assert provider == "cloudflare"
    assert '"operation": "dataset_inspection"' in seen["system"]
    assert "total_missing_cells" in seen["system"]


def test_multi_turn_computation_uses_recent_numeric_history(monkeypatch):
    _stub_context(monkeypatch)
    seen = {}

    def fake_complete(messages):
        seen["system"] = messages[0]["content"]
        return "Mean 4, median 4, Q1 3, Q3 5, IQR 2.", "cloudflare", "test-model"

    monkeypatch.setattr(assistant, "complete", fake_complete)
    history = [{"role": "user", "content": "Here are the values: 2, 4, 6."}]
    answer, _, _, _ = assistant.reply("Now calculate the mean.", history)
    assert answer.startswith("Mean 4")
    assert '"operation": "descriptive_statistics"' in seen["system"]
    assert '"n": 3' in seen["system"]


def test_explicit_bilingual_registry_question_keeps_translation_contract(monkeypatch):
    _stub_context(monkeypatch)
    seen = {}

    def fake_complete(messages):
        seen["system"] = messages[0]["content"]
        return "μ: chiwerengero cha anthu.", "cloudflare", "test-model"

    monkeypatch.setattr(assistant, "complete", fake_complete)
    assistant.reply("In Chichewa, what does the symbol μ mean in statistics?", [])
    assert "DEDICATED ENGLISH <-> CHICHEWA TRANSLATION" in seen["system"]
    assert "VERIFIED SYMBOL / FORMULA REGISTRY LOOKUP" in seen["system"]


def test_chart_values_are_validated_against_verified_result():
    result = solve("Calculate a Kaplan–Meier curve with time=[1,2,3,4] and event=[1,0,1,0].")
    assert result is not None and result.chart is not None
    good_chart = "Median survival 3.\n```chart\n" + __import__("json").dumps(result.chart) + "\n```"
    bad_chart = good_chart.replace('"data": [', '"data": [99, ')
    assert validate_reply(good_chart, "?", "EN", "converse", False, result).ok is True
    validation = validate_reply(bad_chart, "?", "EN", "converse", False, result)
    assert validation.ok is False
    assert any("chart" in reason for reason in validation.reasons)
    wrong_type = __import__("json").loads(__import__("json").dumps(result.chart))
    wrong_type["type"] = "pie"
    wrong_type_text = "Median survival 3.\n```chart\n" + __import__("json").dumps(wrong_type) + "\n```"
    assert validate_reply(wrong_type_text, "?", "EN", "converse", False, result).ok is False


def test_math_validation_links_values_to_labels_and_allows_conventional_rounding():
    descriptive = solve("Calculate the mean of 2, 4 and 6.")
    wrong = "mean is 99, median is 4, Q1 is 3, Q3 is 5, IQR is 2"
    correct = "Mean 4, median 4, Q1 3, Q3 5, IQR 2."
    assert validate_reply(wrong, "?", "EN", "converse", False, descriptive).ok is False
    assert validate_reply(correct, "?", "EN", "converse", False, descriptive).ok is True

    coarse = solve("Interpret a Cohen's d of 4.6.")
    assert validate_reply("d = 5.", "?", "EN", "converse", False, coarse).ok is False
    assert validate_reply("d = 4.6.", "?", "EN", "converse", False, coarse).ok is True

    exact = probability.bayes(0.01, 0.9, 0.108)
    assert validate_reply("The posterior is 0.0833.", "?", "EN", "converse", False, exact).ok is True

    decimals = solve("Calculate the mean of 0.1, 0.2 and 0.7.")
    rounded = "Mean 0.333, median 0.2, Q1 0.15, Q3 0.45, IQR 0.3."
    assert validate_reply(rounded, "?", "EN", "converse", False, decimals).ok is True

    tiny = MathResult(operation="multiple_comparisons", values={"adjusted_p_values": [1e-15]})
    assert validate_reply("Adjusted p-values 0.5.", "?", "EN", "converse", False, tiny).ok is False


def test_blocked_chichewa_answer_does_not_append_english_reason():
    result = blocked_result("descriptive_statistics", "At least two numeric observations are required.")
    answer = blocked_math_answer(result, "CH")
    assert "At least two" not in answer
    assert "Chonde" in answer
