"""Tests for the additive MathsDrill-derived school-mathematics complement.

These checks verify that the complement extends CRARA's calculation engine
without replacing any existing route, and that all epidemiology/biostatistics
requests remain on the original engine.
"""
import math

import pytest

from app.class_rep import assistant
from app.class_rep.math_engine import capabilities, detect_math_request, mathsdrill, solve
from app.class_rep.math_engine.presentation import deterministic_math_answer
from app.class_rep.output_validation import validate_reply


def test_capabilities_are_additive_and_named_separately():
    catalogue = capabilities()
    assert set(catalogue) >= {
        "pure_mathematics", "probability", "statistics", "biostatistics",
        "data_support", "knowledge_registry", "mathsdrill_complement",
    }
    assert "school sequences" in catalogue["mathsdrill_complement"]
    assert "odds, risk and hazard ratios" in catalogue["biostatistics"]
    assert mathsdrill.reasons()["mensuration"].startswith("Use the standard")


def test_arithmetic_and_geometric_sequences_use_explicit_parameters():
    arithmetic = solve(
        "Find the 10th term and the sum of the first 10 terms of the arithmetic sequence "
        "with first term 3 and common difference 4."
    )
    assert arithmetic is not None and arithmetic.operation == "arithmetic_sequence_sum"
    assert arithmetic.values["nth_term"] == pytest.approx(39.0)
    assert arithmetic.values["sum_first_n"] == pytest.approx(210.0)

    term = solve("Find the 5th term of the geometric sequence with first term 2 and common ratio 3.")
    assert term is not None and term.operation == "geometric_sequence_term"
    assert term.values["nth_term"] == pytest.approx(162.0)

    series = solve("Find the sum of the first 5 terms of the geometric sequence with first term 2 and common ratio 3.")
    assert series is not None and series.operation == "geometric_sequence_sum"
    assert series.values["sum_first_n"] == pytest.approx(242.0)


def test_transformations_follow_coordinate_rules():
    reflection = solve("Reflect point P(3, -4) in the y-axis.")
    assert reflection is not None and reflection.values["image"] == {"x": -3.0, "y": -4.0}

    rotation = solve("Rotate point (3, -4) by 90 degrees anticlockwise about the origin.")
    assert rotation is not None and rotation.values["image"] == {"x": 4.0, "y": 3.0}

    translation = solve("Translate point (2, 5) by vector [-3, 1].")
    assert translation is not None and translation.values["image"] == {"x": -1.0, "y": 6.0}


def test_mensuration_and_circle_geometry_use_standard_formulae():
    circle = solve("Find the area of a circle with radius 7.")
    assert circle is not None and circle.operation == "mensuration"
    assert circle.values["value"] == pytest.approx(49 * math.pi)
    assert circle.values["exact_form"] == "49π"

    cylinder = solve("Find the volume of a cylinder with radius 3 and height 10.")
    assert cylinder is not None and cylinder.values["value"] == pytest.approx(90 * math.pi)

    chord = solve("Find the chord length in a circle with radius 5 and distance from centre 3.")
    assert chord is not None and chord.operation == "circle_geometry"
    assert chord.values["value"] == pytest.approx(8.0)


def test_similarity_locus_bearing_modelling_and_graph_reading():
    similarity = solve("Find the area ratio for similar triangles with scale factor 2.")
    assert similarity is not None and similarity.values["result"] == pytest.approx(4.0)

    locus = solve("Find the locus of points equidistant from A(1, 2) and B(5, 6).")
    assert locus is not None and locus.values["midpoint"] == {"x": 3.0, "y": 4.0}
    assert "y = -1" in locus.values["equation"]

    bearing = solve("Find the bearing from (0, 0) to (3, 4).")
    assert bearing is not None and bearing.values["distance"] == pytest.approx(5.0)
    assert bearing.values["bearing_degrees"] == pytest.approx(36.86989765, abs=1e-6)

    model = solve("A fixed cost of 50 plus 10 per hour. Find the cost for 3 hours.")
    assert model is not None and model.operation == "linear_model"
    assert model.values["value"] == pytest.approx(80.0)

    graph = solve("Read off the value at x = 4 on the line through (1, 3) and (2, 5).")
    assert graph is not None and graph.values["gradient"] == pytest.approx(2.0)
    assert graph.values["value_at_x"] == pytest.approx(9.0)


def test_linear_programming_is_solved_from_explicit_constraints():
    result = solve("Maximise 3x + 2y subject to x + y <= 4, x <= 3, y <= 2.")
    assert result is not None and result.operation == "linear_program"
    assert result.values["optimal_point"] == {"x": 3.0, "y": 1.0}
    assert result.values["optimal_value"] == pytest.approx(11.0)
    assert "non-negative" in " ".join(result.assumptions).lower()


def test_incomplete_school_requests_are_blocked_not_guessed():
    result = mathsdrill.solve("Find the area of a circle.")
    assert result is not None and result.status == "blocked"
    assert result.numeric_claims() == []

    ambiguous = mathsdrill.solve("Find the nth term of the sequence.")
    assert ambiguous is not None and ambiguous.status == "blocked"
    assert "arithmetic" in ambiguous.interpretation.lower()


def test_epidemiology_and_biostatistics_are_untouched_by_the_complement():
    assert mathsdrill.solve("Calculate the odds ratio for a=30 b=70 c=10 d=90.") is None
    original = solve("Calculate the odds ratio for a=30 b=70 c=10 d=90.")
    assert original is not None and original.operation == "epidemiological_measures"
    assert original.values["odds_ratio"] == pytest.approx(27 / 7)

    assert mathsdrill.solve("Calculate sensitivity for TP=80 FN=20 FP=20 TN=80.") is None
    assert detect_math_request("Calculate the odds ratio for a=30 b=70 c=10 d=90.")[0] is True
    assert solve("Explain preeclampsia briefly.") is None


def test_new_operations_survive_existing_math_output_validation():
    result = solve("Find the area of a circle with radius 7.")
    assert result is not None
    answer = deterministic_math_answer(result)
    validation = validate_reply(answer, "Find the area of a circle with radius 7.", "EN", evidence_available=True, math_result=result)
    assert validation.ok, validation.reasons


def test_school_math_complement_runs_in_the_real_reply_pipeline(monkeypatch):
    monkeypatch.setattr(assistant, "build_calendar_context", lambda query="": ('{"records":{}}', "2026-11-20T10:00"))
    monkeypatch.setattr(assistant, "search_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        assistant, "linguistic_context",
        lambda message: "No structured lexical entry matched this turn.",
    )
    seen = {}

    def fake_complete(messages):
        seen["system"] = messages[0]["content"]
        return "The image is (-3, -4).", "cloudflare", "test-model"

    monkeypatch.setattr(assistant, "complete", fake_complete)
    answer, provider, _, _ = assistant.reply("Reflect point P(3, -4) in the y-axis.", [])
    assert answer == "The image is (-3, -4)."
    assert provider == "cloudflare"
    assert '"operation": "geometric_transformation"' in seen["system"]
    assert '"x": -3' in seen["system"]
