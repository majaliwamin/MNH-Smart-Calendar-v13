"""Structured, model-independent computation records."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any


_PRIMARY_BY_OPERATION: dict[str, tuple[str, ...]] = {
    "descriptive_statistics": ("mean", "median", "q1", "q3", "iqr"),
    "grouped_statistics": ("bin_width",),
    "equation": ("solutions",),
    "inequality": ("solution_set",),
    "simplify": ("result",),
    "differentiation": ("derivative",),
    "integration": ("integral",),
    "limit": ("limit",),
    "matrix": ("result",),
    "vector": ("result",),
    "coordinate_geometry": ("distance", "midpoint", "slope"),
    "combinatorics": ("value",),
    "complex_numbers": ("result",),
    "numerical_root": ("root",),
    "optimization": ("selected",),
    "differential_equation": ("solution",),
    "bayes_theorem": ("posterior",),
    "probability_rule": ("union", "intersection", "conditional"),
    "distribution": ("pmf", "pdf", "cdf", "survival", "between", "quantile", "central_interval"),
    "central_limit_theorem": ("z", "probability"),
    "one_sample_t": ("t_statistic", "p_value", "cohens_d"),
    "independent_t": ("t_statistic", "p_value", "cohens_d"),
    "paired_t": ("t_statistic", "p_value", "cohens_dz"),
    "chi_square": ("chi2", "p_value", "cramers_v"),
    "anova": ("f_statistic", "p_value", "eta_squared"),
    "mann_whitney": ("u_statistic", "p_value"),
    "wilcoxon": ("statistic", "p_value"),
    "kruskal_wallis": ("h_statistic", "p_value"),
    "multiple_comparisons": ("adjusted_p_values",),
    "statistical_power": ("cohens_h", "power"),
    "correlation": ("coefficient", "p_value"),
    "linear_regression": ("r_squared", "adj_r_squared", "f_statistic"),
    "logistic_regression": ("log_likelihood", "aic"),
    "count_regression": ("aic", "deviance"),
    "cox_regression": ("coefficients",),
    "kaplan_meier": ("median_survival",),
    "epidemiological_measures": ("risk_ratio", "odds_ratio", "absolute_risk_difference", "number_needed_to_treat"),
    "diagnostic_accuracy": ("sensitivity", "specificity", "ppv", "npv"),
    "roc_auc": ("auc",),
    "sample_size_proportion": ("n_required", "n_unrounded"),
    "sample_size_two_means": ("cohens_d", "n_per_group"),
    "effect_size": ("effect_size",),
    "arithmetic_sequence_term": ("nth_term",),
    "arithmetic_sequence_sum": ("sum_first_n",),
    "geometric_sequence_term": ("nth_term",),
    "geometric_sequence_sum": ("sum_first_n",),
    "geometric_transformation": ("image",),
    "mensuration": ("value",),
    "circle_geometry": ("value",),
    "similarity": ("scale_factor", "result"),
    "linear_model": ("value",),
    "graph_reading": ("gradient", "y_intercept", "value_at_x"),
    "locus": ("midpoint",),
    "bearing": ("distance", "bearing_degrees"),
    "linear_program": ("optimal_value", "optimal_point"),
}


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return round(value, 12)
    if hasattr(value, "item"):
        try:
            return _clean(value.item())
        except Exception:
            return str(value)
    return value


@dataclass
class MathResult:
    """A verified computational result plus everything needed to explain it."""

    operation: str
    domain: str = "general"
    method: str = ""
    status: str = "ok"  # ok | blocked | concept
    inputs: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)
    latex: dict[str, str] = field(default_factory=dict)
    code: str = ""
    warnings: list[str] = field(default_factory=list)
    chart: dict[str, Any] | None = None
    interpretation: str = ""
    verified: bool = True

    def as_dict(self) -> dict[str, Any]:
        return _clean({
            "operation": self.operation,
            "domain": self.domain,
            "method": self.method,
            "status": self.status,
            "inputs": self.inputs,
            "assumptions": self.assumptions,
            "steps": self.steps,
            "values": self.values,
            "latex": self.latex,
            "code": self.code,
            "warnings": self.warnings,
            "chart": self.chart,
            "interpretation": self.interpretation,
            "verified": self.verified,
        })

    def numeric_claims(self) -> list[float]:
        """Numbers the final answer must preserve (validation uses this)."""
        claims: list[float] = []

        def walk(value: Any) -> None:
            if isinstance(value, bool):
                return
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                claims.append(float(value))
            elif isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    walk(item)

        walk(self.values)
        return claims

    def required_claims(self, limit: int = 12) -> list[tuple[str, float]]:
        """Headline ``(label, value)`` pairs the final answer must preserve.

        Labels let validation associate a number with the quantity it belongs
        to, so a wrong value swapped between the mean and median cannot pass.
        """
        primary_keys = _PRIMARY_BY_OPERATION.get(self.operation, ())
        claims: list[tuple[str, float]] = []

        def add(key: str, value: Any) -> None:
            if isinstance(value, bool):
                return
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                claims.append((key, float(value)))
            elif isinstance(value, str):
                for token in re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", value):
                    number = float(token)
                    if math.isfinite(number):
                        claims.append((key, number))
            elif isinstance(value, dict):
                for item in value.values():
                    add(key, item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    add(key, item)

        for key in primary_keys:
            if key in self.values:
                add(key, self.values[key])
        if not claims:
            for key in ("n", "n_total", "total", "n_events"):
                if key in self.values:
                    add(key, self.values[key])
        unique: list[tuple[str, float]] = []
        for claim in claims:
            if claim not in unique:
                unique.append(claim)
            if len(unique) >= limit:
                break
        return unique

    def required_numbers(self, limit: int = 5) -> list[float]:
        """Headline numbers the final answer must preserve (label-free view)."""
        return [value for _, value in self.required_claims(limit=limit)]

    def evidence_block(self, max_chars: int = 8000) -> str:
        """Render a bounded prompt block. It is source data, not instructions."""
        payload = self.as_dict()
        payload.pop("code", None)  # code is exposed separately when requested
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncated computation record]"
        header = "VERIFIED DETERMINISTIC COMPUTATION (authoritative numeric source data)"
        if self.status == "blocked":
            header = "COMPUTATION BLOCKED (do not calculate; ask for the missing information)"
        elif self.status == "concept":
            header = "VERIFIED SYMBOL / FORMULA REGISTRY LOOKUP (authoritative terminology source)"
        return header + ":\n" + text


def blocked_result(operation: str, reason: str, domain: str = "general", **inputs: Any) -> MathResult:
    """Return a truthful refusal rather than a guessed calculation."""
    return MathResult(
        operation=operation,
        domain=domain,
        method="insufficient or invalid input",
        status="blocked",
        inputs=inputs,
        assumptions=[],
        steps=[reason],
        values={},
        warnings=[reason],
        interpretation=reason,
        verified=False,
    )
