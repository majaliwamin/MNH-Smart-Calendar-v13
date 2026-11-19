"""Structured mathematical symbol and formula registry."""
from __future__ import annotations

import re
from typing import Any

from .results import MathResult


def _meaning(symbol: str, meaning: str, domain: str, context: str) -> dict[str, str]:
    return {"symbol": symbol, "meaning": meaning, "domain": domain, "context": context}


SYMBOLS: list[dict[str, str]] = [
    _meaning("+", "addition", "arithmetic", "Combining quantities."),
    _meaning("−", "subtraction or negation", "arithmetic", "Difference or signed direction."),
    _meaning("×", "multiplication", "arithmetic", "Product or dimension of a matrix."),
    _meaning("÷", "division", "arithmetic", "Ratio or quotient."),
    _meaning("=", "equality", "logic", "Two expressions have the same value."),
    _meaning("≠", "inequality", "logic", "Two expressions are not equal."),
    _meaning("≈", "approximately equal", "numerical", "Rounded or estimated equality."),
    _meaning("<", "less than", "order", "Strict ordering."),
    _meaning(">", "greater than", "order", "Strict ordering."),
    _meaning("≤", "less than or equal to", "order", "Non-strict bound."),
    _meaning("≥", "greater than or equal to", "order", "Non-strict bound."),
    _meaning("±", "plus or minus", "numerical", "Two possible signs; often an uncertainty bound."),
    _meaning("√", "square root", "algebra", "Non-negative root of a squared quantity."),
    _meaning("∑", "summation", "algebra", "Add a sequence of terms."),
    _meaning("∏", "product", "algebra", "Multiply a sequence of terms."),
    _meaning("∞", "infinity", "analysis", "Unbounded limit; not an ordinary number."),
    _meaning("∂", "partial derivative", "calculus", "Derivative with respect to one variable while others are fixed."),
    _meaning("∇", "gradient / nabla", "vector calculus", "Vector of partial derivatives."),
    _meaning("∫", "integral", "calculus", "Accumulation or area under a curve."),
    _meaning("∮", "closed-line integral", "vector calculus", "Integral around a closed path."),
    _meaning("Δ", "difference / change or Laplacian", "mathematics", "Context decides: finite change, discriminant, or Laplacian."),
    _meaning("π", "pi", "geometry", "Circle circumference-to-diameter ratio."),
    _meaning("e", "Euler's number", "analysis", "Base of natural logarithms."),
    _meaning("θ", "theta", "trigonometry/statistics", "Angle or an unknown parameter."),
    _meaning("α", "alpha", "statistics", "Significance level; also an angle or regression intercept."),
    _meaning("β", "beta", "statistics", "Type II error probability; also a regression coefficient."),
    _meaning("λ", "lambda", "probability", "Rate parameter of Poisson/exponential models, or eigenvalue."),
    _meaning("μ", "mu", "statistics", "Population mean; context can also indicate a drift parameter."),
    _meaning("σ", "sigma", "statistics", "Population standard deviation."),
    _meaning("ρ", "rho", "statistics", "Population correlation coefficient."),
    _meaning("ℝ", "real numbers", "sets", "Set of all real numbers."),
    _meaning("ℤ", "integers", "sets", "Set of all integers."),
    _meaning("ℚ", "rational numbers", "sets", "Numbers expressible as a ratio of integers."),
    _meaning("ℕ", "natural numbers", "sets", "Counting numbers."),
    _meaning("∈", "element of", "sets", "Membership in a set."),
    _meaning("∉", "not an element of", "sets", "Non-membership."),
    _meaning("⊂", "proper subset of", "sets", "Strict containment."),
    _meaning("⊆", "subset of", "sets", "Containment, possibly equal."),
    _meaning("∩", "intersection", "sets", "Elements common to sets."),
    _meaning("∪", "union", "sets", "Elements in either set."),
    _meaning("∅", "empty set", "sets", "Set with no elements."),
    _meaning("∴", "therefore", "logic", "Introduces a conclusion."),
    _meaning("∵", "because", "logic", "Introduces a reason."),
    _meaning("n", "sample size", "statistics", "Number of observations in a sample."),
    _meaning("N", "population size", "statistics", "Number of units in a population."),
    _meaning("x̄", "sample mean", "statistics", "Arithmetic average of sample observations."),
    _meaning("s", "sample standard deviation", "statistics", "Spread of observations around the sample mean."),
    _meaning("s²", "sample variance", "statistics", "Squared sample standard deviation."),
    _meaning("σ²", "population variance", "statistics", "Squared population standard deviation."),
    _meaning("SE", "standard error", "statistics", "Standard deviation of a sampling distribution."),
    _meaning("CI", "confidence interval", "statistics", "Range of plausible parameter values at a stated confidence level."),
    _meaning("H₀", "null hypothesis", "inference", "Default claim being tested."),
    _meaning("H₁", "alternative hypothesis", "inference", "Claim supported when the null is rejected."),
    _meaning("p", "probability or p-value", "statistics", "Context decides: event probability or evidence against the null."),
    _meaning("r", "correlation coefficient", "statistics", "Strength and direction of a linear relationship."),
    _meaning("R²", "coefficient of determination", "regression", "Proportion of variance explained by a model."),
    _meaning("OR", "odds ratio", "epidemiology", "Ratio of odds of an outcome between groups."),
    _meaning("RR", "risk ratio", "epidemiology", "Ratio of cumulative incidences between groups."),
    _meaning("HR", "hazard ratio", "survival", "Ratio of instantaneous failure rates under proportional hazards."),
    _meaning("IQR", "interquartile range", "statistics", "Q3 − Q1; spread of the middle 50%."),
    _meaning("Q1", "first quartile", "statistics", "25th percentile."),
    _meaning("Q2", "second quartile", "statistics", "Median; 50th percentile."),
    _meaning("Q3", "third quartile", "statistics", "75th percentile."),
    _meaning("Z", "standard score", "statistics", "Number of standard errors from a mean under a standard normal model."),
    _meaning("t", "Student's t statistic", "inference", "Standardised difference using an estimated standard error."),
    _meaning("χ²", "chi-square statistic", "inference", "Sum of squared standardized deviations for categorical data."),
    _meaning("F", "F statistic", "inference", "Ratio of variances used in ANOVA and regression."),
    _meaning("df", "degrees of freedom", "statistics", "Number of independent pieces of information."),
    _meaning("β₀", "intercept", "regression", "Predicted outcome when all predictors are zero."),
    _meaning("β₁", "slope", "regression", "Expected change in outcome per unit change in predictor."),
    _meaning("ŷ", "predicted value", "regression", "Model-fitted outcome."),
]


def _formula(
    name: str,
    expression: str,
    variables: dict[str, str],
    inputs: list[str],
    assumptions: list[str],
    applications: list[str],
    example: str,
    interpretation: str,
    domain: str,
    tags: list[str],
    references: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "expression": expression,
        "variables": variables,
        "required_inputs": inputs,
        "assumptions": assumptions,
        "applications": applications,
        "worked_example": example,
        "interpretation": interpretation,
        "domain": domain,
        "tags": tags,
        "references": references or ["NIST Engineering Statistics Handbook", "OpenIntro Statistics"],
    }


FORMULAS: list[dict[str, Any]] = [
    _formula("mean", r"\bar{x}=\frac{1}{n}\sum_{i=1}^{n}x_i",
             {"x_i": "observation i", "n": "sample size"},
             ["numeric observations"], ["Observations are quantitative."],
             ["summarising centre"], "Mean of 2,4,6 is 4.", "Arithmetic centre; sensitive to outliers.", "statistics", ["mean", "average"]),
    _formula("median", r"\tilde{x}=x_{(\frac{n+1}{2})}\text{ for odd }n",
             {"x_(i)": "sorted observation i", "n": "sample size"},
             ["sorted numeric observations"], ["At least ordinal data."],
             ["robust centre"], "Median of 2,5,9 is 5.", "Middle value; resistant to outliers.", "statistics", ["median"]),
    _formula("interquartile range", r"IQR=Q_3-Q_1",
             {"Q_1": "25th percentile", "Q_3": "75th percentile"},
             ["Q1", "Q3", "quartile convention"], ["Quartile method must be stated."],
             ["spread of middle 50%"], "If Q1=7.25 and Q3=16.5, IQR=9.25.", "Wider IQR means greater middle-spread.", "statistics", ["iqr", "quartile", "quartiles"]),
    _formula("sample variance", r"s^2=\frac{\sum (x_i-\bar{x})^2}{n-1}",
             {"s^2": "sample variance", "n": "sample size"},
             ["numeric observations"], ["Independent sampled observations."],
             ["measuring dispersion"], "For 2,4,6: s²=4.", "Uses n−1 to reduce bias for a sample.", "statistics", ["variance"]),
    _formula("sample standard deviation", r"s=\sqrt{\frac{\sum (x_i-\bar{x})^2}{n-1}}",
             {"s": "sample standard deviation"},
             ["numeric observations"], ["Same scale and units as the mean."],
             ["dispersion"], "For 2,4,6: s=2.", "Typical deviation from the sample mean.", "statistics", ["sd", "standard deviation"]),
    _formula("standard error of mean", r"SE_{\bar{x}}=\frac{s}{\sqrt{n}}",
             {"s": "sample standard deviation", "n": "sample size"},
             ["s", "n"], ["Approximate independence; finite variance."],
             ["uncertainty of a mean"], "s=10, n=25 gives SE=2.", "Smaller SE means a more precise mean estimate.", "statistics", ["se", "standard error"]),
    _formula("confidence interval for mean", r"\bar{x}\pm t_{\alpha/2,df}\frac{s}{\sqrt{n}}",
             {"t": "critical t value", "df": "n−1"},
             ["mean", "s", "n", "confidence level"], ["Approximately normal sampling distribution."],
             ["estimation"], "95% CI for a sample mean.", "Repeated sampling would capture the true mean about 95% of the time.", "inference", ["ci", "confidence interval"]),
    _formula("one-sample t test", r"t=\frac{\bar{x}-\mu_0}{s/\sqrt{n}}",
             {"μ₀": "hypothesised population mean"},
             ["mean", "s", "n", "μ₀"], ["Approximate normality of the sample mean."],
             ["testing a mean"], "Test whether mean Hb differs from 12.", "Compare |t| with a t critical value or use its p-value.", "inference", ["t test", "t-test"]),
    _formula("chi-square statistic", r"\chi^2=\sum \frac{(O_i-E_i)^2}{E_i}",
             {"O_i": "observed count", "E_i": "expected count under H₀"},
             ["contingency table"], ["Expected counts usually ≥5 for the asymptotic test."],
             ["categorical association", "goodness of fit"], "2x2 treatment outcome table.", "Large χ² indicates disagreement with the null.", "inference", ["chi-square", "chisquare"]),
    _formula("Bayes theorem", r"P(A\mid B)=\frac{P(B\mid A)P(A)}{P(B)}",
             {"P(A|B)": "posterior probability"},
             ["prior", "likelihood", "evidence"], ["Events must be well defined."],
             ["diagnostic reasoning"], "Positive test after known prevalence and sensitivity.", "Updates a prior belief using observed evidence.", "probability", ["bayes", "conditional probability"]),
    _formula("binomial probability", r"P(X=k)=\binom{n}{k}p^k(1-p)^{n-k}",
             {"n": "trials", "p": "success probability"},
             ["n", "p", "k"], ["Fixed independent Bernoulli trials."],
             ["count data"], "Probability of 3 successes in 10 trials.", "Probability of exactly k successes.", "probability", ["binomial"]),
    _formula("Poisson probability", r"P(X=k)=\frac{e^{-\lambda}\lambda^k}{k!}",
             {"λ": "rate × exposure"},
             ["λ", "k"], ["Events independent at a constant rate."],
             ["counts over time"], "Number of deliveries per clinic day.", "Probability of k events in a fixed exposure.", "probability", ["poisson"]),
    _formula("odds ratio", r"OR=\frac{ad}{bc}",
             {"a,b,c,d": "2x2 table cells"},
             ["2x2 table"], ["Case-control or cohort data with defined reference group."],
             ["epidemiology"], "Exposure and outcome table.", "OR>1 suggests higher odds in the exposed group.", "epidemiology", ["or", "odds ratio"]),
    _formula("risk ratio", r"RR=\frac{a/(a+b)}{c/(c+d)}",
             {"a,b,c,d": "2x2 table cells"},
             ["cohort counts"], ["Cumulative incidence is measurable."],
             ["cohort studies"], "RR of disease in exposed vs unexposed.", "RR>1 indicates increased risk.", "epidemiology", ["rr", "risk ratio", "relative risk"]),
    _formula("number needed to treat", r"NNT=\frac{1}{|ARR|}",
             {"ARR": "absolute risk reduction"},
             ["ARR"], ["Risk difference must be defined and nonzero."],
             ["clinical interpretation"], "ARR=0.10 gives NNT=10.", "Average number of patients treated to avoid one event.", "epidemiology", ["nnt"]),
    _formula("sensitivity", r"Sensitivity=\frac{a}{a+c}",
             {"a": "true positives", "c": "false negatives"},
             ["2x2 diagnostic table"], ["Reference standard is valid."],
             ["diagnostic accuracy"], "Test identifies 80 of 100 true cases.", "Proportion of true cases detected by the test.", "epidemiology", ["sensitivity"]),
    _formula("specificity", r"Specificity=\frac{d}{b+d}",
             {"d": "true negatives", "b": "false positives"},
             ["2x2 diagnostic table"], ["Reference standard is valid."],
             ["diagnostic accuracy"], "Test correctly excludes 90 of 100 non-cases.", "Proportion of non-cases correctly identified.", "epidemiology", ["specificity"]),
    _formula("Pearson correlation", r"r=\frac{\sum(x_i-\bar{x})(y_i-\bar{y})}{\sqrt{\sum(x_i-\bar{x})^2\sum(y_i-\bar{y})^2}}",
             {"r": "correlation coefficient"},
             ["paired x and y"], ["Linear relationship; interval/ratio scale."],
             ["association"], "Correlation of Hb and gestational age.", "Measures linear association, not causation.", "statistics", ["correlation", "pearson"]),
    _formula("simple linear regression", r"\hat{y}=\beta_0+\beta_1 x",
             {"β₀": "intercept", "β₁": "slope"},
             ["paired x and y"], ["Linearity, independent errors, roughly constant variance."],
             ["prediction"], "Predict birth weight from gestational age.", "Slope is expected change in outcome per unit x.", "regression", ["regression", "ols"]),
    _formula("sample size for a proportion", r"n=\frac{Z_{\alpha/2}^2 p(1-p)}{d^2}",
             {"d": "absolute precision", "p": "expected proportion"},
             ["confidence level", "p", "precision"], ["Simple random sampling."],
             ["study design"], "Estimate prevalence with 5% precision.", "Minimum sample size before design-effect adjustment.", "epidemiology", ["sample size"]),
]

def lookup_symbol(symbol: str, context: str = "") -> MathResult | None:
    """Look up context-sensitive meanings of a mathematical symbol."""
    key = str(symbol or "").strip()
    matches = [item for item in SYMBOLS if item["symbol"] == key]
    if not matches:
        lowered = key.casefold()
        matches = [item for item in SYMBOLS if item["symbol"].casefold() == lowered]
    if not matches:
        return None
    context_folded = context.casefold()
    ranked = sorted(
        matches,
        key=lambda item: any(word in context_folded for word in item["domain"].casefold().replace("/", " ").split()),
        reverse=True,
    )
    return MathResult(
        operation="symbol_meaning",
        domain=ranked[0]["domain"],
        method="structured registry lookup",
        status="concept",
        inputs={"symbol": key, "context": context},
        steps=["Interpret the symbol using the surrounding mathematical or scientific context."],
        values={"meanings": ranked},
        interpretation=ranked[0]["meaning"],
    )


def search_formulas(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search the formula registry by name, tag or application."""
    terms = [term.casefold() for term in str(query or "").split() if len(term) > 1]
    if not terms:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for formula in FORMULAS:
        haystack = " ".join([
            formula["name"], " ".join(formula["tags"]), " ".join(formula["applications"]),
            formula["expression"],
        ]).casefold()
        score = sum(1 for term in terms if term in haystack)
        if score:
            scored.append((score, formula))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [formula for _, formula in scored[:limit]]


def _normalise_formula_key(value: str) -> str:
    """Strip question scaffolding without inventing a formula match."""
    key = str(value or "").casefold().strip()
    key = re.sub(r"^(?:please\s+)?(?:what\s+is|what's|give\s+me|show\s+me|show|state|explain|define)\s+", "", key)
    key = re.sub(r"\b(?:formula|equation)\s+(?:for|of)\b", " ", key)
    for _ in range(3):
        key = re.sub(r"^(?:the|a|an)\s+", "", key)
    key = re.sub(r"\s+(?:in\s+simple\s+terms|please)$", "", key)
    return re.sub(r"\s+", " ", key).strip(" ?.!:;,")


def formula_result(name_or_query: str) -> MathResult | None:
    """Return a registry entry only for an unambiguous name or tag match.

    Fuzzy matching over shared words such as "risk" or "the" can return a
    confident but wrong formula. A lookup is curated knowledge, so ambiguous
    wording must return to the normal language path instead of being presented
    as an authoritative computation record.
    """
    key = _normalise_formula_key(name_or_query)
    if not key:
        return None
    for formula in FORMULAS:
        names = [formula["name"].casefold()] + [tag.casefold() for tag in formula["tags"]]
        if key in names:
            return MathResult(
                operation="formula_lookup",
                domain=formula["domain"],
                method="structured formula registry lookup",
                status="concept",
                inputs={"query": name_or_query, "resolved_name": formula["name"]},
                steps=["Select the formula whose assumptions match the described problem."],
                values={"formula": formula},
                latex={"expression": formula["expression"]},
                interpretation=formula["interpretation"],
            )
    return None
