"""Tests for CRARA's manual-first statistics teaching engine."""
import pytest

from app.class_rep import assistant
from app.class_rep import statistics_lessons as lessons


def test_manual_lesson_contains_reasoning_but_no_python():
    answer, provider, model = lessons.answer_lesson(
        "Teach me hypothesis testing using the Z table and normal distribution", [], "EN"
    )
    assert provider == lessons.PROVIDER
    assert model == lessons.MODEL
    assert "Step 1 — Research question" in answer
    assert "H_0" in answer and "H_1" in answer
    assert "SE=\\frac{\\sigma}{\\sqrt{n}}" in answer
    assert "row **2.0** and column **0.00**" in answer
    assert "0.9772" in answer and "0.0455" in answer
    assert "critical values}=\\pm1.96" in answer
    assert "```chart" in answer
    assert "```python" not in answer
    assert lessons.MANUAL_MARKER in answer
    assert "/resources/hypothesis-testing-lab.html" in answer


def test_python_stage_is_refused_before_manual_stage():
    answer, _, _ = lessons.answer_lesson("show me the Python code for the z test", [], "EN")
    assert "```python" not in answer
    assert lessons.MANUAL_MARKER in answer


def test_python_stage_follows_manual_stage():
    history = [{"role": "assistant", "content": lessons.MANUAL_MARKER}]
    answer, provider, model = lessons.answer_lesson(
        "now show me the Python code in JupyterLab", history, "EN"
    )
    assert provider == lessons.PROVIDER
    assert model == lessons.MODEL
    assert "```python" in answer
    assert "stats.norm.ppf" in answer
    assert "stats.norm.sf" in answer
    assert "Python automates arithmetic" in answer


def test_manual_marker_records_topic_for_python_continuity():
    answer, _, _ = lessons.answer_lesson("teach me the one-sample t test", [], "EN")
    assert f"{lessons.MANUAL_MARKER} topic=one_sample_t" in answer


def test_bare_python_request_uses_topic_from_manual_history():
    history = [{"role": "assistant", "content": f"{lessons.MANUAL_MARKER} topic=one_sample_t"}]
    answer, _, _ = lessons.answer_lesson("show me Python", history, "EN")
    assert "stats.t.ppf" in answer
    assert "stats.t.sf" in answer
    assert "stats.norm.ppf" not in answer


@pytest.mark.parametrize("message,topic", [
    ("Explain the one sample t test for haemoglobin", "one_sample_t"),
    ("Walk me through one-way ANOVA for facility types", "anova"),
    ("Teach chi-square independence for gravidity and preterm", "chi_square_independence"),
    ("Show Mann-Whitney U manually", "mann_whitney"),
    ("Explain the paired t test for blood pressure", "paired_t"),
])
def test_topic_detection(message, topic):
    assert lessons.detect_topic(message) == topic
    answer, _, _ = lessons.answer_lesson(message, [], "EN")
    assert lessons.MANUAL_MARKER in answer
    assert "```python" not in answer


def test_timetable_and_general_turns_are_not_hijacked():
    assert lessons.answer_lesson("What classes are on Friday?", [], "EN") is None
    assert lessons.answer_lesson("Hello, how are you?", [], "EN") is None
    assert lessons.answer_lesson("What is the capital of Malawi?", [], "EN") is None


def test_assistant_uses_manual_first_lesson_without_provider(monkeypatch):
    def forbidden_provider(_messages):
        raise AssertionError("provider must not be called for deterministic statistics lessons")

    monkeypatch.setattr(assistant, "complete", forbidden_provider)
    answer, provider, model, updated = assistant.reply(
        "Explain hypothesis testing with the Z table", [], response_language="EN"
    )
    assert provider == lessons.PROVIDER
    assert model == lessons.MODEL
    assert updated is None
    assert "```python" not in answer
    assert lessons.MANUAL_MARKER in answer
