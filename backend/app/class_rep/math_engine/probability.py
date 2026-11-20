"""Probability rules, distributions and distribution-based quantities."""
from __future__ import annotations

import math
from typing import Any

from .results import MathResult, blocked_result

_DISTRIBUTIONS = {
    "binomial": "binom", "poisson": "poisson", "normal": "norm", "gaussian": "norm",
    "standard normal": "norm", "z": "norm", "t": "t", "chi-square": "chi2",
    "chisquare": "chi2", "f": "f", "exponential": "expon", "uniform": "uniform",
}


def _scipy_stats():
    try:
        from scipy import stats
        return stats, None
    except Exception as exc:  # pragma: no cover - dependency declared in requirements
        return None, str(exc)


def bayes(prior: float, likelihood: float, evidence: float, event: str = "A", test: str = "B") -> MathResult:
    """Compute a posterior probability using Bayes' theorem."""
    for name, value in (("prior", prior), ("likelihood", likelihood), ("evidence", evidence)):
        if not 0 <= value <= 1:
            return blocked_result("bayes", f"{name} must be between 0 and 1.", domain="probability")
    if evidence == 0:
        return blocked_result("bayes", "The evidence probability P(B) cannot be zero.", domain="probability")
    posterior = likelihood * prior / evidence
    if posterior > 1:
        return blocked_result("bayes", "The supplied probabilities are inconsistent: posterior exceeds 1.", domain="probability",
                              prior=prior, likelihood=likelihood, evidence=evidence)
    return MathResult(
        operation="bayes_theorem", domain="probability", method="Bayes theorem",
        inputs={"prior": prior, "likelihood": likelihood, "evidence": evidence},
        steps=[f"P({event}|{test}) = P({test}|{event}) × P({event}) / P({test})",
               f"= {likelihood:.6g} × {prior:.6g} / {evidence:.6g} = {posterior:.6g}."],
        values={"posterior": posterior},
        latex={"formula": r"P(A\mid B)=\frac{P(B\mid A)P(A)}{P(B)}"},
        code=f"posterior = {likelihood} * {prior} / {evidence}",
        interpretation=f"P({event}|{test}) = {posterior:.6g} after updating the prior with the observed evidence.",
    )


def probability_rule(p_a: float, p_b: float, intersection: float | None = None, rule: str = "union") -> MathResult:
    """Union, intersection or conditional probability of two events."""
    if not (0 <= p_a <= 1 and 0 <= p_b <= 1):
        return blocked_result("probability_rule", "Event probabilities must be between 0 and 1.", domain="probability")
    rule = rule.casefold()
    if rule in ("and", "intersection"):
        if intersection is not None:
            value = intersection
        else:
            value = p_a * p_b
        label = "intersection"
    elif rule in ("given", "conditional"):
        if intersection is None or p_b == 0:
            return blocked_result("probability_rule", "Conditional probability needs P(B) > 0 and P(A∩B).", domain="probability")
        value = intersection / p_b
        label = "conditional"
    else:
        if intersection is None:
            return blocked_result("probability_rule", "Union needs P(A∩B); supply 0 for mutually exclusive events.", domain="probability")
        value = p_a + p_b - intersection
        label = "union"
    if not 0 <= value <= 1:
        return blocked_result("probability_rule", "The supplied probabilities produce an impossible result.", domain="probability")
    return MathResult(
        operation="probability_rule", domain="probability", method=label,
        inputs={"p_a": p_a, "p_b": p_b, "intersection": intersection},
        steps=[f"Apply the {label} rule to the supplied events."],
        values={label: value}, interpretation=f"P = {value:.6g}.",
    )


def distribution(
    name: str,
    *,
    kind: str = "pmf",
    value: float | None = None,
    x: float | None = None,
    n: int | None = None,
    p: float | None = None,
    mu: float | None = None,
    sigma: float | None = None,
    lam: float | None = None,
    df: float | None = None,
    df2: float | None = None,
    low: float | None = None,
    high: float | None = None,
    quantile: float | None = None,
    ci: float = 0.95,
) -> MathResult:
    """Calculate pmf/pdf, cdf, survival, critical value or interval for a distribution."""
    stats, error = _scipy_stats()
    if stats is None:
        return blocked_result("distribution", f"Distribution calculations need SciPy: {error}", domain="probability", name=name)
    key = _DISTRIBUTIONS.get(str(name or "").casefold().strip())
    if key is None:
        return blocked_result("distribution", f"Unsupported distribution: {name}", domain="probability")
    if key == "binom":
        if n is None or p is None or not 0 <= p <= 1:
            return blocked_result("distribution", "Binomial needs n and 0 ≤ p ≤ 1.", domain="probability", name=name)
        dist = stats.binom(n, p)
    elif key == "poisson":
        if lam is None or lam <= 0:
            return blocked_result("distribution", "Poisson needs λ > 0.", domain="probability", name=name)
        dist = stats.poisson(lam)
    elif key == "norm":
        if mu is None or sigma is None or sigma <= 0:
            return blocked_result("distribution", "Normal needs μ and σ > 0.", domain="probability", name=name)
        dist = stats.norm(mu, sigma)
    elif key == "t":
        if df is None or df <= 0:
            return blocked_result("distribution", "t distribution needs positive df.", domain="probability", name=name)
        dist = stats.t(df)
    elif key == "chi2":
        if df is None or df <= 0:
            return blocked_result("distribution", "Chi-square needs positive df.", domain="probability", name=name)
        dist = stats.chi2(df)
    elif key == "f":
        if not df or not df2 or df <= 0 or df2 <= 0:
            return blocked_result("distribution", "F distribution needs positive df1 and df2.", domain="probability", name=name)
        dist = stats.f(df, df2)
    elif key == "expon":
        if lam is None or lam <= 0:
            return blocked_result("distribution", "Exponential needs rate λ > 0.", domain="probability", name=name)
        dist = stats.expon(scale=1.0 / lam)
    else:
        if low is None or high is None or high <= low:
            return blocked_result("distribution", "Uniform needs low < high.", domain="probability", name=name)
        dist = stats.uniform(low, high - low)

    params = {k: v for k, v in {"n": n, "p": p, "mu": mu, "sigma": sigma, "lambda": lam, "df": df, "df2": df2, "low": low, "high": high}.items() if v is not None}
    point = x if x is not None else value
    kind = kind.casefold()
    kind_aliases = {
        "mass": "pmf", "density": "pdf", "probability": "cdf", "less_than": "cdf",
        "at_most": "cdf", "greater_than": "survival", "at_least": "survival",
        "critical_value": "quantile", "interval": "ci",
    }
    kind = kind_aliases.get(kind, kind)
    values: dict[str, Any] = {}
    if kind in ("pmf", "pdf"):
        if point is None:
            return blocked_result("distribution", "A value x is needed for pmf/pdf.", domain="probability", name=name)
        values[kind] = float(dist.pmf(point) if key in ("binom", "poisson") else dist.pdf(point))
    elif kind == "cdf":
        if point is None:
            return blocked_result("distribution", "A value x is needed for a CDF probability.", domain="probability", name=name)
        values["cdf"] = float(dist.cdf(point))
    elif kind in ("sf", "survival", "greater_than", "at_least"):
        if point is None:
            return blocked_result("distribution", "A value x is needed for a survival probability.", domain="probability", name=name)
        values["survival"] = float(dist.sf(point))
    elif kind == "between":
        if point is None or high is None or high < point:
            return blocked_result("distribution", "An interval needs a lower x and upper high.", domain="probability", name=name)
        values["between"] = float(dist.cdf(high) - dist.cdf(point))
        params["interval"] = [point, high]
    elif kind in ("ppf", "quantile", "critical_value"):
        if quantile is None or not 0 <= quantile <= 1:
            return blocked_result("distribution", "A quantile between 0 and 1 is needed.", domain="probability", name=name)
        values["quantile"] = float(dist.ppf(quantile))
    elif kind in ("ci", "interval"):
        lower = (1 - ci) / 2
        upper = 1 - lower
        values["central_interval"] = [float(dist.ppf(lower)), float(dist.ppf(upper))]
        values["confidence_level"] = ci
    else:
        return blocked_result("distribution", f"Unsupported operation: {kind}", domain="probability", name=name)

    return MathResult(
        operation="distribution", domain="probability", method=f"{name} {kind}",
        inputs={"distribution": name, **params, "kind": kind},
        steps=[f"Use the {name} distribution with the supplied parameters and request {kind}."],
        values=values,
        interpretation="Distribution values are computed by SciPy; no value is estimated by the language model.",
        code=f"from scipy import stats\n# dist = stats.{key}(...)\n# dist.{kind if kind not in ('between',) else 'cdf'}(...)\n",
    )


def central_limit_theorem(mean: float, sd: float, n: int, target: float) -> MathResult:
    """Approximate P(sample mean ≤ target) using the CLT."""
    stats, error = _scipy_stats()
    if stats is None:
        return blocked_result("central_limit_theorem", f"CLT needs SciPy: {error}", domain="probability")
    if sd <= 0 or n < 2:
        return blocked_result("central_limit_theorem", "CLT needs σ > 0 and n ≥ 2.", domain="probability")
    se = sd / math.sqrt(n)
    z = (target - mean) / se
    probability = float(stats.norm.cdf(z))
    return MathResult(
        operation="central_limit_theorem", domain="probability", method="normal approximation to the sample mean",
        inputs={"population_mean": mean, "population_sd": sd, "n": n, "target": target},
        steps=[f"SE = σ/√n = {sd:.6g}/√{n} = {se:.6g}.", f"z = ({target:.6g} − {mean:.6g})/{se:.6g} = {z:.6g}."],
        values={"standard_error": se, "z": z, "probability": probability},
        warnings=["The approximation requires a sufficiently large n or a roughly normal population."],
        interpretation=f"Approximate probability that the sample mean is at most {target:.6g} is {probability:.6g}.",
    )
