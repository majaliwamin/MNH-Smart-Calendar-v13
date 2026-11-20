"""Inferential statistics: tests, confidence intervals, power and multiplicity."""
from __future__ import annotations

import math
from typing import Any

from .results import MathResult, blocked_result

_ASSUMPTIONS = {
    "one_sample_t": ["Quantitative outcome", "Approximately normal sampling distribution (or large n)", "Independent observations"],
    "independent_t": ["Independent groups", "Approximately normal group distributions or adequate n", "Welch version does not assume equal variances"],
    "paired_t": ["Paired observations", "Approximately normal distribution of differences"],
    "chi_square": ["Categorical counts", "Independent observations", "Expected counts preferably ≥5 for the asymptotic test"],
    "fisher": ["2x2 categorical counts", "Independent observations", "Fixed margins interpretation is conditional"],
    "anova": ["Independent groups", "Approximately normal residuals", "Homogeneity of variances for classical ANOVA"],
    "mann_whitney": ["Ordinal or continuous outcome", "Independent groups", "Stochastic dominance interpretation"],
    "wilcoxon": ["Paired ordinal/continuous data", "Symmetric distribution of differences for median interpretation"],
    "kruskal": ["Ordinal or continuous outcome", "Independent groups", "Distribution-shape interpretation"],
}


def _stats():
    try:
        from scipy import stats
        return stats, None
    except Exception as exc:
        return None, str(exc)


def _finish(result: Any, operation: str, method: str, inputs: dict[str, Any], assumption_key: str,
            steps: list[str], values: dict[str, Any], interpretation: str) -> MathResult:
    return MathResult(
        operation=operation, domain="inference", method=method, inputs=inputs,
        assumptions=_ASSUMPTIONS.get(assumption_key, []), steps=steps, values=values,
        interpretation=interpretation, code="from scipy import stats\n# use the corresponding stats.* test on your arrays",
    )


def one_sample_t(values: list[float], hypothesized_mean: float, alternative: str = "two-sided") -> MathResult:
    stats, error = _stats()
    if stats is None:
        return blocked_result("one_sample_t", f"t test needs SciPy: {error}", domain="inference")
    data = [float(v) for v in values if math.isfinite(float(v))]
    if len(data) < 2:
        return blocked_result("one_sample_t", "At least two observations are required.", domain="inference")
    result = stats.ttest_1samp(data, hypothesized_mean, alternative=alternative)
    ci = result.confidence_interval(0.95)
    n = len(data)
    mean = sum(data) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in data) / (n - 1))
    d = (mean - hypothesized_mean) / sd if sd else 0.0
    return _finish(result, "one_sample_t", "Student's one-sample t test", {"n": n, "mu0": hypothesized_mean}, "one_sample_t",
                   [f"H₀: μ = {hypothesized_mean:.6g}; H₁ is {alternative}.",
                    f"Compute t = (x̄ − μ₀)/(s/√n) with x̄ = {mean:.6g}, s = {sd:.6g}, n = {n}."],
                   {"t_statistic": float(result.statistic), "p_value": float(result.pvalue),
                    "df": n - 1, "mean": mean, "sd": sd, "cohens_d": d,
                    "ci_mean_95": [float(ci.low), float(ci.high)], "significant_at_0_05": float(result.pvalue) < 0.05},
                   f"t = {result.statistic:.6g}, p = {result.pvalue:.6g}. "
                   + ("Reject H₀ at 5%." if result.pvalue < 0.05 else "Do not reject H₀ at 5%."))


def independent_t(group_a: list[float], group_b: list[float], equal_var: bool = False) -> MathResult:
    stats, error = _stats()
    if stats is None:
        return blocked_result("independent_t", f"t test needs SciPy: {error}", domain="inference")
    a = [float(v) for v in group_a if math.isfinite(float(v))]
    b = [float(v) for v in group_b if math.isfinite(float(v))]
    if len(a) < 2 or len(b) < 2:
        return blocked_result("independent_t", "Each group needs at least two observations.", domain="inference")
    result = stats.ttest_ind(a, b, equal_var=equal_var)
    ci = result.confidence_interval(0.95)
    pooled_sd = math.sqrt(((len(a) - 1) * (sum((v - sum(a) / len(a)) ** 2 for v in a)) +
                           (len(b) - 1) * (sum((v - sum(b) / len(b)) ** 2 for v in b))) /
                          (len(a) + len(b) - 2)) if equal_var else math.sqrt(
        (sum((v - sum(a) / len(a)) ** 2 for v in a) / (len(a) - 1) +
         sum((v - sum(b) / len(b)) ** 2 for v in b) / (len(b) - 1)) / 2)
    diff = sum(a) / len(a) - sum(b) / len(b)
    return _finish(result, "independent_t", "Welch t test" if not equal_var else "Pooled two-sample t test",
                   {"n_a": len(a), "n_b": len(b), "equal_var": equal_var}, "independent_t",
                   [f"Compare group means using {'Welch' if not equal_var else 'pooled'} t test.",
                    f"Observed difference = {diff:.6g}."],
                   {"t_statistic": float(result.statistic), "p_value": float(result.pvalue),
                    "df": float(getattr(result, "df", len(a) + len(b) - 2)),
                    "mean_difference": diff, "cohens_d": diff / pooled_sd if pooled_sd else 0.0,
                    "ci_difference_95": [float(ci.low), float(ci.high)]},
                   f"t = {result.statistic:.6g}, p = {result.pvalue:.6g}. A p-value is not effect size; report the CI and Cohen's d.")


def paired_t(before: list[float], after: list[float]) -> MathResult:
    stats, error = _stats()
    if stats is None:
        return blocked_result("paired_t", f"paired t test needs SciPy: {error}", domain="inference")
    if len(before) != len(after) or len(before) < 2:
        return blocked_result("paired_t", "Paired t needs equal-length vectors with at least two pairs.", domain="inference")
    diffs = [float(b) - float(a) for a, b in zip(before, after)]
    result = stats.ttest_rel([float(v) for v in before], [float(v) for v in after])
    ci = result.confidence_interval(0.95)
    mean_diff = sum(diffs) / len(diffs)
    sd_diff = math.sqrt(sum((d - mean_diff) ** 2 for d in diffs) / (len(diffs) - 1))
    return _finish(result, "paired_t", "Paired t test", {"pairs": len(diffs)}, "paired_t",
                   [f"Compute paired differences: {[round(d, 8) for d in diffs]}.",
                    f"Mean difference = {mean_diff:.6g}; SD of differences = {sd_diff:.6g}."],
                   {"t_statistic": float(result.statistic), "p_value": float(result.pvalue),
                    "df": len(diffs) - 1, "mean_difference": mean_diff,
                    "ci_mean_difference_95": [float(ci.low), float(ci.high)],
                    "cohens_dz": mean_diff / sd_diff if sd_diff else 0.0},
                   f"Paired t = {result.statistic:.6g}, p = {result.pvalue:.6g}.")


def chi_square(table: list[list[int]], correction: bool = True) -> MathResult:
    stats, error = _stats()
    if stats is None:
        return blocked_result("chi_square", f"chi-square needs SciPy: {error}", domain="inference")
    if len(table) < 2 or any(len(row) < 2 for row in table):
        return blocked_result("chi_square", "Provide at least a 2x2 contingency table.", domain="inference")
    result = stats.chi2_contingency(table, correction=correction)
    chi2, p, df, expected = result
    n = sum(sum(row) for row in table)
    v = math.sqrt(float(chi2) / n) if n else 0.0
    small_expected = len(table) == 2 and len(table[0]) == 2 and min(min(r) for r in expected) < 5
    method = "Pearson chi-square"
    values: dict[str, Any] = {
        "chi2": float(chi2), "p_value": float(p), "df": int(df),
        "expected_counts": [[float(x) for x in row] for row in expected],
        "cramers_v": v, "min_expected_count": float(min(min(r) for r in expected)),
    }
    warnings: list[str] = []
    if small_expected:
        warnings.append("At least one expected count is below 5; prefer Fisher's exact test for a 2x2 table.")
        try:
            fisher = stats.fisher_exact(table)
            values["fisher_or"] = float(fisher.statistic)
            values["fisher_p"] = float(fisher.pvalue)
        except Exception:
            pass
    finished = _finish(result, "chi_square", method, {"table": table, "correction": correction}, "chi_square",
                       ["Compute expected counts under independence.", "Sum (O−E)²/E over all cells."],
                       values, f"χ²({df}) = {chi2:.6g}, p = {p:.6g}. Check expected counts before relying on the asymptotic p-value.")
    finished.warnings = warnings
    return finished


def anova(groups: list[list[float]]) -> MathResult:
    stats, error = _stats()
    if stats is None:
        return blocked_result("anova", f"ANOVA needs SciPy: {error}", domain="inference")
    clean = [[float(v) for v in group if math.isfinite(float(v))] for group in groups]
    if len(clean) < 2 or any(len(g) < 2 for g in clean):
        return blocked_result("anova", "ANOVA needs at least two groups with two observations each.", domain="inference")
    result = stats.f_oneway(*clean)
    all_values = [v for group in clean for v in group]
    grand_mean = sum(all_values) / len(all_values)
    ss_between = sum(len(g) * (sum(g) / len(g) - grand_mean) ** 2 for g in clean)
    ss_total = sum((v - grand_mean) ** 2 for v in all_values)
    eta_sq = ss_between / ss_total if ss_total else 0.0
    return _finish(result, "anova", "One-way ANOVA", {"groups": [len(g) for g in clean]}, "anova",
                   ["Partition variance into between-group and within-group components.", "Compare mean squares using F."],
                   {"f_statistic": float(result.statistic), "p_value": float(result.pvalue),
                    "df_between": len(clean) - 1, "df_within": len(all_values) - len(clean),
                    "eta_squared": eta_sq},
                   f"F({len(clean) - 1}, {len(all_values) - len(clean)}) = {result.statistic:.6g}, p = {result.pvalue:.6g}. "
                   "A significant omnibus test does not identify which groups differ.")


def nonparametric(test: str, group_a: list[float], group_b: list[float] | None = None) -> MathResult:
    stats, error = _stats()
    if stats is None:
        return blocked_result(test, f"Non-parametric test needs SciPy: {error}", domain="inference")
    a = [float(v) for v in group_a if math.isfinite(float(v))]
    key = test.casefold()
    if key in ("mann_whitney", "mann-whitney", "mannwhitneyu"):
        if not group_b or len(a) < 2 or len(group_b) < 2:
            return blocked_result(test, "Mann–Whitney needs two groups with at least two observations.", domain="inference")
        result = stats.mannwhitneyu(a, [float(v) for v in group_b], alternative="two-sided")
        return _finish(result, "mann_whitney", "Mann–Whitney U test", {"n_a": len(a), "n_b": len(group_b)}, "mann_whitney",
                       ["Rank all observations and compare rank sums between independent groups."],
                       {"u_statistic": float(result.statistic), "p_value": float(result.pvalue)},
                       f"U = {result.statistic:.6g}, p = {result.pvalue:.6g}.")
    if key in ("wilcoxon", "wilcoxon_signed_rank"):
        if not group_b or len(a) != len(group_b):
            return blocked_result(test, "Wilcoxon needs equal-length paired vectors.", domain="inference")
        result = stats.wilcoxon(a, [float(v) for v in group_b])
        return _finish(result, "wilcoxon", "Wilcoxon signed-rank test", {"pairs": len(a)}, "wilcoxon",
                       ["Rank absolute paired differences, then sum signed ranks."],
                       {"statistic": float(result.statistic), "p_value": float(result.pvalue)},
                       f"W = {result.statistic:.6g}, p = {result.pvalue:.6g}.")
    if key in ("kruskal", "kruskal-wallis", "kruskalwallis"):
        groups = [a] + [[float(v) for v in g] for g in (group_b or [])]
        if len(groups) < 2:
            return blocked_result(test, "Kruskal–Wallis needs at least two groups.", domain="inference")
        result = stats.kruskal(*groups)
        return _finish(result, "kruskal_wallis", "Kruskal–Wallis H test", {"groups": [len(g) for g in groups]}, "kruskal",
                       ["Compare rank sums across independent groups."],
                       {"h_statistic": float(result.statistic), "p_value": float(result.pvalue), "df": len(groups) - 1},
                       f"H = {result.statistic:.6g}, p = {result.pvalue:.6g}.")
    return blocked_result(test, f"Unsupported non-parametric test: {test}", domain="inference")


def multiple_comparisons(p_values: list[float], method: str = "holm", alpha: float = 0.05) -> MathResult:
    """Adjust p-values for multiple testing."""
    if not p_values or any(not 0 <= p <= 1 for p in p_values):
        return blocked_result("multiple_comparisons", "Provide p-values between 0 and 1.", domain="inference")
    key = method.casefold().replace("-", "_")
    try:
        from statsmodels.stats.multitest import multipletests
        reject, adjusted, _, _ = multipletests(p_values, alpha=alpha, method=key)
        adjusted = [float(v) for v in adjusted]
        reject = [bool(v) for v in reject]
    except Exception:
        if key == "bonferroni":
            adjusted = [min(1.0, p * len(p_values)) for p in p_values]
        elif key == "holm":
            ordered = sorted(range(len(p_values)), key=lambda i: p_values[i])
            adjusted = [0.0] * len(p_values)
            running = 0.0
            for rank, idx in enumerate(ordered, start=1):
                running = max(running, (len(p_values) - rank + 1) * p_values[idx])
                adjusted[idx] = min(1.0, running)
        else:
            return blocked_result("multiple_comparisons", f"Unsupported correction: {method}", domain="inference")
        reject = [p < alpha for p in adjusted]
    return MathResult(
        operation="multiple_comparisons", domain="inference", method=key,
        inputs={"p_values": p_values, "alpha": alpha}, assumptions=["P-values come from valid individual tests."],
        steps=[f"Apply {key} adjustment at α = {alpha}."],
        values={"adjusted_p_values": adjusted, "reject_null": reject},
        interpretation="Report adjusted p-values for multiplicity; unadjusted p-values inflate false-positive risk.",
    )


def power_two_proportions(p1: float, p2: float, n_per_group: int, alpha: float = 0.05) -> MathResult:
    stats, error = _stats()
    if stats is None:
        return blocked_result("power", f"Power needs SciPy: {error}", domain="inference")
    if not (0 <= p1 <= 1 and 0 <= p2 <= 1) or n_per_group < 2:
        return blocked_result("power", "Power needs proportions in [0,1] and n ≥ 2 per group.", domain="inference")
    try:
        from statsmodels.stats.power import NormalIndPower
        from statsmodels.stats.proportion import proportion_effectsize
        effect = abs(float(proportion_effectsize(p1, p2)))
        analysis = NormalIndPower()
        power = float(analysis.power(effect_size=effect, nobs1=n_per_group, alpha=alpha, ratio=1.0))
    except Exception as exc:
        return blocked_result("power", f"Power calculation needs statsmodels: {exc}", domain="inference")
    return MathResult(
        operation="statistical_power", domain="inference", method="two-proportion z power",
        inputs={"p1": p1, "p2": p2, "n_per_group": n_per_group, "alpha": alpha},
        assumptions=["Independent groups", "Normal approximation to proportions"],
        steps=[f"Compute Cohen's h effect size = {effect:.6g}.", f"Evaluate power at n = {n_per_group} per group."],
        values={"cohens_h": effect, "power": power},
        interpretation=f"Approximate power = {power:.4f}. Low power means a true effect may be missed.",
    )
