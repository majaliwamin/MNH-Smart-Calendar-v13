"""Descriptive statistics with explicit, reproducible quartile conventions."""
from __future__ import annotations

import math
import statistics
from collections import Counter
from typing import Any

from .results import MathResult, blocked_result

_METHOD_DESCRIPTIONS = {
    "linear": "Linear interpolation between ordered observations at position (n−1)p (R-7 / NumPy default / Excel QUARTILE.INC).",
    "median_halves_exclusive": "Median of the lower and upper halves, excluding the overall median when n is odd (Tukey's hinges).",
    "median_halves_inclusive": "Median of the lower and upper halves, including the overall median when n is odd (Moore & McCabe).",
    "exclusive": "Excel QUARTILE.EXC: interpolation at ordinal position (n+1)p; the minimum and maximum are never quartiles.",
    "nearest_rank": "Nearest-rank quantile: the observation at rank ceil(np).",
}


def _linear_quantile(values: list[float], p: float) -> float:
    n = len(values)
    if n == 1:
        return values[0]
    position = (n - 1) * p
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return values[low]
    return values[low] + (position - low) * (values[high] - values[low])


def _median_halves(values: list[float], p: float, include_median: bool) -> float:
    n = len(values)
    if n == 1:
        return values[0]
    median = statistics.median(values)
    if include_median:
        # Moore & McCabe includes the centre in both halves: one value for odd
        # n, both central values for even n. Tukey (exclusive) does not.
        split = (n + 1) // 2 if n % 2 else n // 2 + 1
        half = values[:split] if p <= 0.5 else values[n - split:]
    else:
        split = n // 2
        half = values[:split] if p <= 0.5 else values[n - split:]
    return statistics.median(half)


def _exclusive_quantile(values: list[float], p: float) -> float:
    n = len(values)
    if n < 2:
        return values[0]
    position = (n + 1) * p
    if position < 1 or position > n:
        raise ValueError("QUARTILE.EXC is undefined for this percentile and sample size")
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return values[low - 1]
    return values[low - 1] + (position - low) * (values[high - 1] - values[low - 1])


def quartiles(values: list[float], method: str = "linear") -> dict[str, Any]:
    """Return Q1, Q2, Q3 and IQR under an explicitly named convention."""
    ordered = sorted(float(v) for v in values)
    if not ordered:
        raise ValueError("at least one observation is required")
    method = method if method in _METHOD_DESCRIPTIONS else "linear"
    if method == "linear":
        q1, q2, q3 = (_linear_quantile(ordered, p) for p in (0.25, 0.5, 0.75))
    elif method in ("median_halves_exclusive", "median_halves_inclusive"):
        include = method == "median_halves_inclusive"
        q1 = _median_halves(ordered, 0.25, include)
        q2 = statistics.median(ordered)
        q3 = _median_halves(ordered, 0.75, include)
    elif method == "exclusive":
        q1, q2, q3 = (_exclusive_quantile(ordered, p) for p in (0.25, 0.5, 0.75))
    else:
        q1, q2, q3 = (ordered[max(0, math.ceil(len(ordered) * p) - 1)] for p in (0.25, 0.5, 0.75))
    return {
        "q1": float(q1), "q2": float(q2), "q3": float(q3),
        "iqr": float(q3 - q1), "method": method,
        "method_explanation": _METHOD_DESCRIPTIONS[method],
    }


def _moments(values: list[float]) -> tuple[float, float, float]:
    mean = statistics.fmean(values)
    m2 = sum((v - mean) ** 2 for v in values) / len(values)
    if m2 == 0:
        return mean, 0.0, 0.0
    m3 = sum((v - mean) ** 3 for v in values) / len(values)
    m4 = sum((v - mean) ** 4 for v in values) / len(values)
    return mean, m3 / (m2 ** 1.5), m4 / (m2 ** 2) - 3.0


def describe(
    values: list[float],
    quartile_method: str = "linear",
    confidence: float = 0.95,
    data_name: str = "observations",
) -> MathResult:
    """Compute a full descriptive summary for ungrouped numeric observations."""
    cleaned = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
    if len(cleaned) < 2:
        return blocked_result(
            "descriptive_statistics",
            "At least two finite numeric observations are required for descriptive statistics.",
            domain="statistics", observations=list(values),
        )
    ordered = sorted(cleaned)
    n = len(ordered)
    mean = statistics.fmean(ordered)
    median = statistics.median(ordered)
    counts = Counter(ordered)
    max_count = max(counts.values())
    modes = sorted(value for value, count in counts.items() if count == max_count)
    if max_count == 1:
        modes = []
    sample_variance = statistics.variance(ordered)
    population_variance = statistics.pvariance(ordered)
    sample_sd = math.sqrt(sample_variance)
    population_sd = math.sqrt(population_variance)
    sem = sample_sd / math.sqrt(n) if n > 1 else 0.0
    q = quartiles(ordered, quartile_method)
    _, g1, g2 = _moments(ordered)
    if n > 2:
        skewness = math.sqrt(n * (n - 1)) / (n - 2) * g1
    else:
        skewness = g1
    if n > 3:
        kurtosis = ((n - 1) * ((n + 1) * g2 + 6)) / ((n - 2) * (n - 3))
    else:
        kurtosis = g2

    critical = None
    try:
        from scipy import stats as scipy_stats
        critical = float(scipy_stats.t.ppf(0.5 + confidence / 2.0, n - 1))
    except Exception:
        critical = 1.96
    ci = (mean - critical * sem, mean + critical * sem)

    lower_fence = q["q1"] - 1.5 * q["iqr"]
    upper_fence = q["q3"] + 1.5 * q["iqr"]
    outliers = [v for v in ordered if v < lower_fence or v > upper_fence]

    steps = [
        f"Sort the {n} observations in ascending order: {ordered}.",
        f"Use the {q['method']} quartile convention: {q['method_explanation']}",
        f"Q1 = {q['q1']:.6g}, Q2 = {q['q2']:.6g}, Q3 = {q['q3']:.6g}.",
        f"IQR = Q3 − Q1 = {q['q3']:.6g} − {q['q1']:.6g} = {q['iqr']:.6g}.",
        f"The middle 50% of observations lie between {q['q1']:.6g} and {q['q3']:.6g}.",
    ]
    code = (
        "import numpy as np\nfrom scipy import stats\n\n"
        f"data = {ordered!r}\n"
        f"q1, q2, q3 = np.percentile(data, [25, 50, 75], method='linear')\n"
        "iqr = q3 - q1\n"
        "print(stats.describe(data), q1, q2, q3, iqr)\n"
    )
    convention_iqrs: dict[str, float] = {}
    for key in _METHOD_DESCRIPTIONS:
        try:
            convention_iqrs[key] = quartiles(ordered, key)["iqr"]
        except (ValueError, IndexError):
            # Some conventions are undefined for very small samples.
            continue

    return MathResult(
        operation="descriptive_statistics",
        domain="statistics",
        method=q["method"],
        inputs={"data_name": data_name, "n": n, "values": ordered, "quartile_method": q["method"]},
        assumptions=[
            "Observations are quantitative and sampled or measured on a common scale.",
            "Quartile convention is stated explicitly; reporting IQR without it is ambiguous.",
        ],
        steps=steps,
        values={
            "n": n, "sorted_values": ordered, "mean": mean, "median": median,
            "mode": modes, "minimum": ordered[0], "maximum": ordered[-1],
            "range": ordered[-1] - ordered[0],
            "q1": q["q1"], "q2": q["q2"], "q3": q["q3"], "iqr": q["iqr"],
            "quartile_method": q["method"],
            "quartile_conventions": convention_iqrs,
            "variance_sample": sample_variance, "variance_population": population_variance,
            "standard_deviation_sample": sample_sd,
            "standard_deviation_population": population_sd,
            "coefficient_of_variation": sample_sd / mean if mean else None,
            "standard_error_mean": sem,
            "confidence_level": confidence,
            "ci_mean": list(ci),
            "ci_mean_95": list(ci),
            "skewness_bias_corrected": skewness,
            "kurtosis_excess_bias_corrected": kurtosis,
            "five_number_summary": [ordered[0], q["q1"], q["q2"], q["q3"], ordered[-1]],
            "outlier_fences": [lower_fence, upper_fence],
            "outliers_iqr_rule": outliers,
            "frequency_distribution": {str(k): v for k, v in sorted(counts.items())},
        },
        latex={
            "mean": r"\bar{x}=\frac{1}{n}\sum x_i",
            "iqr": r"IQR=Q_3-Q_1",
            "sd": r"s=\sqrt{\frac{\sum(x_i-\bar{x})^2}{n-1}}",
            "ci": r"\bar{x}\pm t_{\alpha/2,n-1}\frac{s}{\sqrt{n}}",
        },
        code=code,
        interpretation=(
            f"The middle 50% of {data_name} spans {q['q1']:.6g} to {q['q3']:.6g} "
            f"(IQR {q['iqr']:.6g}) using the {q['method']} convention."
        ),
    )


def grouped_summary(values: list[float], bins: int = 5) -> MathResult:
    """Summarise grouped data with explicit bin edges and frequencies."""
    cleaned = [float(v) for v in values if math.isfinite(float(v))]
    if len(cleaned) < 2 or bins < 2:
        return blocked_result("grouped_statistics", "Grouped data need at least two values and two bins.", domain="statistics")
    minimum, maximum = min(cleaned), max(cleaned)
    width = (maximum - minimum) / bins
    counts = [0] * bins
    for value in cleaned:
        index = min(bins - 1, int((value - minimum) / width))
        counts[index] += 1
    rows = []
    for index in range(bins):
        lower = minimum + index * width
        upper = lower + width
        rows.append({
            "class": f"[{lower:.4g}, {upper:.4g})" if index < bins - 1 else f"[{lower:.4g}, {upper:.4g}]",
            "frequency": counts[index],
            "relative_frequency": counts[index] / len(cleaned),
            "midpoint": lower + width / 2,
        })
    return MathResult(
        operation="grouped_statistics", domain="statistics", method="equal-width grouping",
        inputs={"n": len(cleaned), "bins": bins}, steps=[f"Create {bins} equal-width classes across {minimum:.6g} to {maximum:.6g}."],
        values={"classes": rows, "bin_width": width, "total": len(cleaned)},
        interpretation="Grouped summaries approximate the raw data; retain raw values where possible.",
    )
