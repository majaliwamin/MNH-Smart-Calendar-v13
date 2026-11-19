"""Deterministic mathematics, statistics and biostatistics engine tests.

Expected values are fixed independently of the implementation using standard
hand calculations or published closed-form formulae.
"""
import math

import pytest

from app.class_rep.math_engine import capabilities, detect_math_request, solve
from app.class_rep.math_engine import datasets, descriptive, epidemiology, inference, probability, regression, symbolic
from app.class_rep.math_engine.parsing import parse_two_by_two
from app.class_rep.math_engine.registry import formula_result, lookup_symbol


def test_capabilities_and_symbol_registry_are_structured():
    catalogue = capabilities()
    assert set(catalogue) >= {"pure_mathematics", "probability", "statistics", "biostatistics", "data_support"}
    symbol = lookup_symbol("μ", "population mean in a statistics assignment")
    assert symbol is not None and symbol.status == "concept"
    assert symbol.values["meanings"][0]["domain"] == "statistics"
    formula = formula_result("sample size for a proportion")
    assert formula is not None and formula.latex["expression"]
    assert formula.values["formula"]["required_inputs"]
    assert formula.values["formula"]["references"]


def test_routing_is_conservative():
    assert detect_math_request("Explain preeclampsia briefly.")[0] is False
    assert detect_math_request("What is the mean of 2, 4 and 6?")[0] is True
    assert detect_math_request("What does μ mean in statistics?")[0] is True
    assert detect_math_request("What is the mean age at delivery in the study?")[0] is False
    assert detect_math_request("Interpret the odds ratio from this study.")[0] is False
    assert detect_math_request("My patient has a mean arterial pressure of 90. What should I do?")[0] is False
    assert solve("Explain preeclampsia briefly.") is None


def test_formula_lookup_is_exact_and_never_returns_an_unrelated_formula():
    result = solve("What is the equation for the risk ratio?")
    assert result is not None and result.operation == "formula_lookup"
    assert result.values["formula"]["name"] == "risk ratio"
    assert solve("What is the formula for Hb in pregnancy?") is None
    assert solve("Explain the formula for preeclampsia risk in simple terms.") is None


def test_quartile_conventions_are_explicit_and_different():
    values = list(range(1, 9))
    linear = descriptive.quartiles(values, "linear")
    tukey = descriptive.quartiles(values, "median_halves_exclusive")
    moore = descriptive.quartiles(values, "median_halves_inclusive")
    excel_exc = descriptive.quartiles(values, "exclusive")
    assert (linear["q1"], linear["q3"], linear["iqr"]) == pytest.approx((2.75, 6.25, 3.5))
    assert (tukey["q1"], tukey["q3"], tukey["iqr"]) == pytest.approx((2.5, 6.5, 4.0))
    assert (moore["q1"], moore["q3"], moore["iqr"]) == pytest.approx((3.0, 6.0, 3.0))
    assert (excel_exc["q1"], excel_exc["q3"], excel_exc["iqr"]) == pytest.approx((2.25, 6.75, 4.5))
    routed = solve("IQR of 1 2 3 4 5 6 7 8 using Tukey")
    assert routed is not None and routed.operation == "descriptive_statistics"
    assert routed.values["quartile_method"] == "median_halves_exclusive"
    assert routed.values["iqr"] == pytest.approx(4.0)


def test_descriptive_summary_and_confidence_interval():
    result = solve("Compute a 95% confidence interval for [2,4,6,8,10].")
    assert result is not None and result.operation == "descriptive_statistics"
    values = result.values
    assert values["n"] == 5
    assert values["mean"] == pytest.approx(6.0)
    assert values["standard_deviation_sample"] == pytest.approx(math.sqrt(10))
    assert values["q1"] == pytest.approx(4.0)
    assert values["q3"] == pytest.approx(8.0)
    assert values["confidence_level"] == pytest.approx(0.95)
    assert values["ci_mean_95"] == pytest.approx([2.0735, 9.9265], abs=1e-3)


def test_symbolic_algebra_calculus_and_linear_algebra():
    equation = solve("Solve 2x + 3 = 11")
    assert equation is not None and equation.operation == "equation"
    assert "4" in equation.values["solutions"][0]
    derivative = symbolic.differentiate("x**3 + 2*x", "x")
    assert derivative.values["derivative"] == "3*x**2 + 2"
    integral = symbolic.integrate("2*x", "x")
    assert integral.values["integral"] == "x**2"
    determinant = solve("What is the determinant of [[1,2],[3,4]]?")
    assert determinant is not None and determinant.values["result"] == pytest.approx(-2.0)
    inequality = symbolic.inequality("2*x + 3 > 11", "x")
    assert "4" in inequality.values["solution_set"]
    assert symbolic.simplify("open('x')").status == "blocked"


def test_probability_binomial_bayes_and_distribution_quantile():
    binomial = solve("Calculate the probability of exactly 3 successes in 10 trials with p=0.3.")
    assert binomial is not None and binomial.operation == "distribution"
    assert binomial.values["pmf"] == pytest.approx(0.266827932, rel=1e-6)
    posterior = probability.bayes(0.01, 0.9, 0.108)
    assert posterior.values["posterior"] == pytest.approx(1 / 12)
    quantile = probability.distribution("normal", kind="quantile", mu=100, sigma=15, quantile=0.975)
    assert quantile.values["quantile"] == pytest.approx(129.399, abs=1e-2)


def test_inferential_tests_use_expected_statistics():
    one_sample = inference.one_sample_t([2, 4, 6, 8, 10], 5)
    assert one_sample.values["t_statistic"] == pytest.approx(1 / math.sqrt(2))
    assert one_sample.values["p_value"] == pytest.approx(0.5185185185)
    assert one_sample.values["cohens_d"] == pytest.approx(1 / math.sqrt(10))
    chi = inference.chi_square([[10, 20], [20, 10]], correction=False)
    assert chi.values["chi2"] == pytest.approx(6.666666667)
    assert chi.values["p_value"] == pytest.approx(0.0098232745)
    assert chi.values["cramers_v"] == pytest.approx(1 / 3)
    corrected = inference.multiple_comparisons([0.01, 0.02, 0.04], "bonferroni")
    assert corrected.values["adjusted_p_values"] == pytest.approx([0.03, 0.06, 0.12])


def test_biostatistical_effect_measures_and_diagnostic_accuracy():
    measures = solve("Calculate the odds ratio for a=30 b=70 c=10 d=90.")
    assert measures is not None and measures.operation == "epidemiological_measures"
    assert measures.values["risk_ratio"] == pytest.approx(3.0)
    assert measures.values["odds_ratio"] == pytest.approx(27 / 7)
    assert measures.values["number_needed_to_treat"] is None
    assert measures.values["number_needed_to_harm"] == pytest.approx(5.0)
    diagnostic = epidemiology.diagnostic_accuracy({"tp": 80, "fp": 20, "fn": 20, "tn": 80}, prevalence=0.5)
    values = diagnostic.values
    assert values["sensitivity"] == pytest.approx(0.8)
    assert values["specificity"] == pytest.approx(0.8)
    assert values["ppv"] == pytest.approx(0.8)
    assert values["ppv_at_supplied_prevalence"] == pytest.approx(0.8)
    assert values["likelihood_ratio_positive"] == pytest.approx(4.0)


def test_sample_size_and_effect_size_guards():
    size = solve("Sample size for a proportion with p=0.5, precision=0.05 and 95% confidence.")
    assert size is not None and size.operation == "sample_size_proportion"
    assert size.values["n_required"] == 385
    effect = solve("Interpret a Cohen's d of 0.55.")
    assert effect is not None and effect.values["conventional_label"] == "medium"
    blocked = solve("Calculate the sample size for a study.")
    assert blocked is not None and blocked.status == "blocked" and blocked.values == {}


def test_correlation_and_linear_regression():
    correlation = regression.correlation([1, 2, 3, 4], [2, 4, 5, 4])
    assert correlation.values["coefficient"] == pytest.approx(0.7181848465)
    model = regression.linear_regression([1, 2, 3, 4], [2, 4, 5, 4])
    coefficients = {item["term"]: item["coefficient"] for item in model.values["coefficients"]}
    assert coefficients["intercept"] == pytest.approx(2.0)
    assert coefficients["x1"] == pytest.approx(0.7)
    assert model.values["r_squared"] == pytest.approx(0.5157894737)
    assert "does not establish causation" in model.interpretation


def test_blocked_math_never_invents_a_number():
    result = solve("Calculate the mean of these observations")
    assert result is not None
    assert result.status == "blocked"
    assert result.numeric_claims() == []
    assert "two" in result.interpretation.lower() or "required information" in result.warnings[0].lower()


def test_two_by_two_parsing_requires_explicit_semantics():
    assert parse_two_by_two("chi-square for [[10,20],[20,10]]") == {"a": 10, "b": 20, "c": 20, "d": 10}
    reordered = parse_two_by_two(
        "30 exposed cases, 10 unexposed cases, 70 exposed non-cases, 90 unexposed non-cases"
    )
    assert reordered == {"a": 30, "b": 70, "c": 10, "d": 90}
    assert parse_two_by_two("Calculate the odds ratio for 30 70 10 90") is None


def test_two_by_two_never_promotes_bare_prose_numbers():
    result = solve("Calculate the odds ratio from 30, 10, 70, 90.")
    assert result is not None and result.status == "blocked"


def test_narrative_documents_do_not_supply_fake_observations():
    passage = "In 2024 a study reported a 95% CI with p<0.05 and 12 deliveries."
    result = solve("Calculate the mean of the data.", source_text=passage)
    assert result is None or result.status == "blocked"


def test_explanatory_numeric_turns_stay_on_the_language_path():
    assert solve("The minimum sample size was 50. Explain.") is None


def test_unrelated_history_numbers_are_not_promoted_to_observations():
    history = [{"role": "user", "content": "In 2024 the 95% CI was p<0.05 with 12 deliveries."}]
    result = solve("Now calculate the mean.", history=history)
    assert result is None or result.status == "blocked"


def test_csv_inspection_reports_missing_values_and_duplicates():
    csv_text = "age,hb,arm\n20,12,A\n21,,A\n21,,A\n22,13,B\n"
    result = datasets.inspect_csv(csv_text, name="haemoglobin dataset")
    assert result.status == "ok"
    assert result.values["shape"] == [4, 3]
    assert result.values["duplicate_rows"] == 1
    assert result.values["total_missing_cells"] == 2
    assert result.values["numeric_summaries"]["age"]["mean"] == pytest.approx(21.0)
