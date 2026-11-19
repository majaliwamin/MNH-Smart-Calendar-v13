"""Epidemiological measures, diagnostic accuracy, ROC and sample-size design."""
from __future__ import annotations

import math
from typing import Any

from .results import MathResult, blocked_result

ASSUMPTIONS_2X2 = [
    "The 2x2 cell mapping is explicit: a=exposed cases, b=exposed non-cases, c=unexposed cases, d=unexposed non-cases.",
    "Groups and outcome status are defined before analysis; counts are not imputed.",
]


def _cells(table: Any) -> tuple[int, int, int, int] | None:
    if isinstance(table, dict):
        keys = ("a", "b", "c", "d") if all(key in table for key in ("a", "b", "c", "d")) else ("tp", "fp", "fn", "tn")
        try:
            return tuple(int(table[key]) for key in keys)  # type: ignore[return-value]
        except Exception:
            return None
    if isinstance(table, (list, tuple)) and len(table) == 2:
        try:
            rows = [[int(v) for v in row] for row in table]
            if all(len(row) == 2 for row in rows):
                return rows[0][0], rows[0][1], rows[1][0], rows[1][1]
        except Exception:
            return None
    return None


def contingency_measures(table: Any) -> MathResult:
    """Compute cohort/case-control effect measures from a 2x2 table."""
    cells = _cells(table)
    if cells is None or any(v < 0 for v in cells):
        return blocked_result("epidemiological_measures", "Provide a valid 2x2 table with non-negative counts.", domain="epidemiology")
    a, b, c, d = cells
    total = a + b + c + d
    if total == 0:
        return blocked_result("epidemiological_measures", "The 2x2 table has no observations.", domain="epidemiology")
    r_exposed = a / (a + b) if a + b else None
    r_unexposed = c / (c + d) if c + d else None
    rr = (r_exposed / r_unexposed) if r_exposed is not None and r_unexposed not in (None, 0) else None
    odds_exposed = a / b if b else None
    odds_unexposed = c / d if d else None
    or_value = (odds_exposed / odds_unexposed) if odds_exposed is not None and odds_unexposed else None
    if or_value is None and 0 not in (a, b, c, d):
        or_value = (a * d) / (b * c)
    ar = (r_exposed - r_unexposed) if r_exposed is not None and r_unexposed is not None else None
    arr = -ar if ar is not None else None
    rrr = (1 - rr) if rr is not None else None
    pe = (a + b) / total
    paf = (pe * (rr - 1)) / (1 + pe * (rr - 1)) if rr is not None and (1 + pe * (rr - 1)) != 0 else None
    nnt = 1 / arr if arr and arr > 0 else None
    nnh = 1 / ar if ar and ar > 0 else None
    values = {
        "table": {"a": a, "b": b, "c": c, "d": d}, "total": total,
        "risk_exposed": r_exposed, "risk_unexposed": r_unexposed,
        "odds_exposed": odds_exposed, "odds_unexposed": odds_unexposed,
        "risk_ratio": rr, "odds_ratio": or_value, "absolute_risk_difference": ar,
        "absolute_risk_reduction": arr, "relative_risk_reduction": rrr,
        "attributable_risk": ar, "population_attributable_fraction": paf,
        "number_needed_to_treat": nnt, "number_needed_to_harm": nnh,
        "prevalence_in_sample": (a + c) / total,
    }
    return MathResult(
        operation="epidemiological_measures", domain="epidemiology", method="2x2 effect measures",
        inputs={"table": values["table"]}, assumptions=ASSUMPTIONS_2X2,
        steps=["Define the risk in each exposure group.", "Form ratios and differences from those risks.", "Derive NNT/NNH only when the absolute difference is non-zero."],
        values=values,
        latex={"rr": r"RR=\frac{a/(a+b)}{c/(c+d)}", "or": r"OR=\frac{ad}{bc}", "nnt": r"NNT=\frac{1}{|ARR|}"},
        interpretation="Effect measures quantify association; causation requires appropriate design and control of confounding.",
    )


def diagnostic_accuracy(table: Any, prevalence: float | None = None) -> MathResult:
    """Sensitivity, specificity, predictive values and likelihood ratios."""
    cells = _cells(table)
    if cells is None:
        return blocked_result("diagnostic_accuracy", "Provide a 2x2 table a=TP, b=FP, c=FN, d=TN.", domain="epidemiology")
    tp, fp, fn, tn = cells
    total = tp + fp + fn + tn
    if total == 0:
        return blocked_result("diagnostic_accuracy", "The diagnostic table has no observations.", domain="epidemiology")
    sensitivity = tp / (tp + fn) if tp + fn else None
    specificity = tn / (tn + fp) if tn + fp else None
    ppv = tp / (tp + fp) if tp + fp else None
    npv = tn / (tn + fn) if tn + fn else None
    lr_positive = sensitivity / (1 - specificity) if sensitivity is not None and specificity not in (None, 1) else None
    lr_negative = (1 - sensitivity) / specificity if sensitivity is not None and specificity not in (None, 0) else None
    adjusted_ppv = None
    adjusted_npv = None
    if prevalence is not None and 0 <= prevalence <= 1 and sensitivity is not None and specificity is not None:
        numerator = sensitivity * prevalence
        denominator = numerator + (1 - specificity) * (1 - prevalence)
        adjusted_ppv = numerator / denominator if denominator else None
        numerator_n = specificity * (1 - prevalence)
        denominator_n = (1 - sensitivity) * prevalence + numerator_n
        adjusted_npv = numerator_n / denominator_n if denominator_n else None
    return MathResult(
        operation="diagnostic_accuracy", domain="epidemiology", method="2x2 diagnostic table",
        inputs={"table": {"tp": tp, "fp": fp, "fn": fn, "tn": tn}, "prevalence": prevalence},
        assumptions=["A valid reference standard defines true disease status.", "Predictive values depend on disease prevalence."],
        steps=["Compute sensitivity and specificity from disease strata.", "Compute predictive values from test-result strata."],
        values={"sensitivity": sensitivity, "specificity": specificity, "ppv": ppv, "npv": npv,
                "likelihood_ratio_positive": lr_positive, "likelihood_ratio_negative": lr_negative,
                "accuracy": (tp + tn) / total, "youden_j": (sensitivity + specificity - 1) if sensitivity is not None and specificity is not None else None,
                "ppv_at_supplied_prevalence": adjusted_ppv, "npv_at_supplied_prevalence": adjusted_npv},
        interpretation="Sensitivity and specificity are test properties; predictive values change with prevalence.",
    )


def roc_auc(labels: list[int], scores: list[float]) -> MathResult:
    try:
        from sklearn.metrics import roc_auc_score, roc_curve
    except Exception as exc:
        return blocked_result("roc_auc", f"ROC analysis needs scikit-learn: {exc}", domain="epidemiology")
    if len(labels) != len(scores) or len(set(labels)) < 2:
        return blocked_result("roc_auc", "ROC needs scores and at least two outcome classes.", domain="epidemiology")
    try:
        auc = float(roc_auc_score(labels, scores))
        fpr, tpr, _ = roc_curve(labels, scores)
    except Exception as exc:
        return blocked_result("roc_auc", f"ROC analysis failed: {exc}", domain="epidemiology")
    return MathResult(
        operation="roc_auc", domain="epidemiology", method="empirical ROC curve",
        inputs={"n": len(labels), "positive": sum(int(v) for v in labels)},
        assumptions=["Scores are continuous or ordinal with a meaningful direction.", "Labels are verified."],
        steps=["Vary the classification threshold.", "Plot true-positive against false-positive rate and integrate."],
        values={"auc": auc, "fpr": [float(v) for v in fpr[:: max(1, len(fpr) // 40)]],
                "tpr": [float(v) for v in tpr[:: max(1, len(tpr) // 40)]]},
        chart={"type": "line", "title": "ROC curve", "labels": [f"{v:.3f}" for v in fpr[:: max(1, len(fpr) // 40)]],
               "datasets": [{"label": "TPR", "data": [float(v) for v in tpr[:: max(1, len(tpr) // 40)]]}]},
        interpretation="AUC describes ranking discrimination, not calibration or clinical usefulness.",
    )


def sample_size_proportion(expected_p: float, precision: float, confidence: float = 0.95, population: int | None = None) -> MathResult:
    try:
        from scipy import stats as scipy_stats
    except Exception as exc:
        return blocked_result("sample_size", f"Sample size needs SciPy: {exc}", domain="epidemiology")
    if not 0 < expected_p < 1 or not 0 < precision < 1:
        return blocked_result("sample_size", "Expected proportion and precision must be between 0 and 1.", domain="epidemiology")
    z = float(scipy_stats.norm.ppf(0.5 + confidence / 2))
    n0 = (z ** 2 * expected_p * (1 - expected_p)) / (precision ** 2)
    n = n0
    correction = None
    if population:
        if population < 1:
            return blocked_result("sample_size", "Population size must be positive.", domain="epidemiology")
        n = n0 / (1 + (n0 - 1) / population)
        correction = "finite population correction"
    final = math.ceil(n)
    return MathResult(
        operation="sample_size_proportion", domain="epidemiology", method="normal approximation for a proportion",
        inputs={"expected_p": expected_p, "precision": precision, "confidence": confidence, "population": population},
        assumptions=["Simple random sampling", "Expected proportion is scientifically justified", "No design effect included"],
        steps=[f"z = {z:.6g} for {confidence:.0%} confidence.", f"n₀ = z²p(1−p)/d² = {n0:.4f}.",
               f"Round up to {final}." + (f" Apply {correction}." if correction else "")],
        values={"z": z, "n_unrounded": n, "n_required": final, "design_effect_added": False},
        latex={"formula": r"n=\frac{Z_{\alpha/2}^2p(1-p)}{d^2}"},
        interpretation="Adjust for clustering, non-response and design effect before field use; state every adjustment.",
    )


def sample_size_two_means(delta: float, sd: float, power: float = 0.8, alpha: float = 0.05) -> MathResult:
    try:
        from statsmodels.stats.power import TTestIndPower
    except Exception as exc:
        return blocked_result("sample_size", f"Sample size needs statsmodels: {exc}", domain="epidemiology")
    if delta <= 0 or sd <= 0 or not 0 < power < 1 or not 0 < alpha < 1:
        return blocked_result("sample_size", "delta, sd must be positive; power and alpha in (0,1).", domain="epidemiology")
    effect = delta / sd
    n = TTestIndPower().solve_power(effect_size=effect, power=power, alpha=alpha, ratio=1.0)
    final = math.ceil(n)
    return MathResult(
        operation="sample_size_two_means", domain="epidemiology", method="two-independent-means t test power",
        inputs={"delta": delta, "sd": sd, "power": power, "alpha": alpha},
        assumptions=["Independent groups", "Equal allocation", "SD estimate is valid"],
        steps=[f"Cohen's d = Δ/σ = {effect:.6g}.", f"Solve for n at power {power:.0%}, α = {alpha:.3g}: {n:.4f}.", f"Round up to {final} per group."],
        values={"cohens_d": effect, "n_per_group": final, "n_total": final * 2},
        interpretation="This is a baseline estimate; clustering and attrition require further adjustment.",
    )


def effect_size_interpretation(value: float, kind: str = "cohens_d") -> MathResult:
    magnitude = abs(value)
    label = "negligible" if magnitude < 0.2 else "small" if magnitude < 0.5 else "medium" if magnitude < 0.8 else "large"
    return MathResult(
        operation="effect_size", domain="epidemiology", method="conventional thresholds",
        inputs={"value": value, "kind": kind}, assumptions=["Thresholds are rules of thumb, not universal truths."],
        steps=[f"Compare |{kind}| = {magnitude:.6g} with conventional thresholds."],
        values={"effect_size": value, "conventional_label": label},
        interpretation="Statistical significance and clinical importance are distinct; interpret effect size with context and precision.",
    )
