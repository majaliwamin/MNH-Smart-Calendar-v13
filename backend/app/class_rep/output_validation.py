"""Rule-based validation of CRARA replies using independent evidence.

Validation never asks the same model whether its own Chichewa is correct. It
uses deterministic checks plus the language/mode evidence computed from the
user's message and the references actually retrieved for this turn. Failures
trigger one bounded regeneration with a corrective contract; if that also
fails, the user receives an honest, language-appropriate limitation rather
than a fabricated answer.
"""
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

from app.class_rep.language_intelligence import detect_language
from app.class_rep.math_engine.results import MathResult

_BANNED_PHRASES = (
    "ndife crara",
    "i am crara",
    "as crara",
    "i am an academic coordination assistant",
    "crara service error",
    "providererror",
    "all_providers_failed",
    "not_configured",
)
_VERIFICATION_CLAIM = (
    "dictionary verified",
    "dictionary confirms",
    "verified by the dictionary",
    "according to the dictionary",
    "mlw dictionary verified",
)
_MATH_OPEN = ("\\(", "\\[")
_MATH_CLOSE = ("\\)", "\\]")


@dataclass
class ValidationResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)

    def repair_instruction(self) -> str:
        if self.ok:
            return ""
        items = "; ".join(self.reasons[:4])
        return (
            "OUTPUT VALIDATION FAILED for this draft: " + items + ". "
            "Rewrite the answer from the retrieved evidence, in the selected response "
            "language, addressing the user's actual latest message. Remove the defect; "
            "do not add a generic introduction, service menu, disclaimer or invented "
            "terminology. If the evidence is insufficient, say so naturally and ask one "
            "focused clarification."
        )


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in text.split("\n\n") if len(part.strip()) > 40]


_NUMBER_TOKEN = re.compile(r"(?<![\w.])([-+]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*(%)?", re.I)

_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "mean": ("arithmetic mean", "sample mean", "mean", "average", "x̄"),
    "median": ("median", "x̃"),
    "q1": ("first quartile", "25th percentile", "q1"),
    "q3": ("third quartile", "75th percentile", "q3"),
    "iqr": ("interquartile range", "iqr"),
    "standard_deviation_sample": ("sample standard deviation", "standard deviation", "sd", "s"),
    "p_value": ("p-value", "p value", "p"),
    "t_statistic": ("t-statistic", "t statistic", "t"),
    "chi2": ("chi-square statistic", "chi-square", "χ²", "χ2"),
    "cohens_d": ("cohen's d", "cohens d", "effect size", "d"),
    "solutions": ("solution", "solutions", "root", "roots", "x =", "x="),
    "result": ("result", "value", "answer"),
    "coefficient": ("correlation coefficient", "coefficient", "r"),
    "r_squared": ("r squared", "r²", "coefficient of determination"),
    "auc": ("auc", "area under the curve"),
    "n_required": ("required sample size", "sample size", "n"),
    "median_survival": ("median survival", "median"),
    "odds_ratio": ("odds ratio", "or"),
    "risk_ratio": ("risk ratio", "relative risk", "rr"),
    "sensitivity": ("sensitivity",),
    "specificity": ("specificity",),
    "ppv": ("positive predictive value", "ppv"),
    "npv": ("negative predictive value", "npv"),
    "bin_width": ("bin width", "class width"),
    "distance": ("distance",),
    "midpoint": ("midpoint", "mid-point"),
    "slope": ("slope", "gradient"),
    "selected": ("chosen", "selected", "optimum", "optimum value"),
    "solution": ("solution", "answer"),
    "union": ("union",),
    "intersection": ("intersection",),
    "conditional": ("conditional probability",),
    "pmf": ("pmf", "probability mass", "P(X", "P(X="),
    "pdf": ("pdf", "density"),
    "cdf": ("cdf", "cumulative probability"),
    "survival": ("survival probability", "survival"),
    "between": ("between probability", "interval probability"),
    "quantile": ("quantile", "percentile", "critical value"),
    "central_interval": ("central interval", "credible interval"),
    "z": ("z score", "z-score", "z statistic", "z"),
    "probability": ("probability",),
    "cohens_dz": ("cohen's dz", "cohens dz", "standardised effect size"),
    "h_statistic": ("H statistic", "kruskal-wallis H", "H"),
    "adjusted_p_values": ("adjusted p-values", "adjusted p values", "corrected p-values"),
    "cohens_h": ("cohen's h", "cohens h"),
    "power": ("statistical power", "power"),
    "adj_r_squared": ("adjusted r squared", "adjusted r²"),
    "f_statistic": ("F statistic", "F-statistic", "F"),
    "log_likelihood": ("log likelihood", "log-likelihood"),
    "aic": ("AIC",),
    "deviance": ("deviance",),
    "coefficients": ("coefficients", "beta coefficients"),
    "n_per_group": ("per group", "sample size per group", "n per group"),
    "effect_size": ("effect size", "cohen's d", "cohens d"),
}
_ALL_LABEL_ALIASES = sorted(
    {alias for aliases in _LABEL_ALIASES.values() for alias in aliases},
    key=len,
    reverse=True,
)


def _parse_number(match: re.Match[str]) -> float | None:
    try:
        value = float(match.group(1).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if match.group(2):
        value /= 100.0
    return value if math.isfinite(value) else None


def _numbers_close(left: Any, right: Any) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return _numbers_close(left.get("x"), right.get("x")) and _numbers_close(left.get("y"), right.get("y"))
    try:
        left_value, right_value = float(left), float(right)
    except (TypeError, ValueError):
        return left == right
    # Allow conventional rounding to three significant digits (for example
    # 0.333 for 1/3), but reject coarse replacement such as 5 for 4.6.
    return math.isclose(left_value, right_value, rel_tol=2e-3, abs_tol=0.0)


def _label_variants(label: str) -> tuple[str, ...]:
    generated = label.replace("_", " ")
    variants = {generated, generated.replace(" ", "-"), generated.replace(" ", "")}
    variants.update(_LABEL_ALIASES.get(label, ()))
    return tuple(sorted(variants, key=len, reverse=True))


def _label_spans(text: str, label: str) -> list[int]:
    ends: list[int] = []
    for alias in _label_variants(label):
        pattern = r"(?<![\w.])" + re.escape(alias) + r"(?![\w.])"
        ends.extend(match.end() for match in re.finditer(pattern, text, re.I))
    return sorted(ends)


def _window_after_label(text: str, end: int) -> str:
    window = text[end:end + 110]
    cut = len(window)
    all_aliases = sorted(_ALL_LABEL_ALIASES, key=len, reverse=True)
    for alias in all_aliases:
        pattern = r"(?<![\w.])" + re.escape(alias) + r"(?![\w.])"
        match = re.search(pattern, window[1:], re.I)
        if match:
            cut = min(cut, match.start() + 1)
    for separator in ("\n", ";"):
        position = window.find(separator)
        if position >= 0:
            cut = min(cut, position)
    # A full stop ends the value only when it is not a decimal point.
    sentence_end = re.search(r"\.(?=\s|$)", window)
    if sentence_end:
        cut = min(cut, sentence_end.start())
    return window[:cut]


def _claim_present(text: str, label: str, value: float, allow_global: bool = False) -> bool:
    spans = _label_spans(text, label)
    for end in spans:
        window = _window_after_label(text, end)
        for match in _NUMBER_TOKEN.finditer(window):
            parsed = _parse_number(match)
            if parsed is not None and _numbers_close(parsed, value):
                return True
    if spans:
        return False
    if allow_global:
        return any(
            (parsed := _parse_number(match)) is not None and _numbers_close(parsed, value)
            for match in _NUMBER_TOKEN.finditer(text)
        )
    return False


def _chart_matches(actual: Any, expected: dict[str, Any]) -> bool:
    if not isinstance(actual, dict):
        return False
    for key in ("type", "title"):
        if str(actual.get(key, "")) != str(expected.get(key, "")):
            return False
    if [str(item) for item in actual.get("labels", [])] != [str(item) for item in expected.get("labels", [])]:
        return False
    expected_sets, actual_sets = expected.get("datasets", []), actual.get("datasets", [])
    if len(actual_sets) != len(expected_sets):
        return False
    for expected_set, actual_set in zip(expected_sets, actual_sets):
        if str(actual_set.get("label", "")) != str(expected_set.get("label", "")):
            return False
        expected_data, actual_data = expected_set.get("data", []), actual_set.get("data", [])
        if len(actual_data) != len(expected_data) or not all(
                _numbers_close(a, b) for a, b in zip(actual_data, expected_data)):
            return False
    return True


def _validate_math_result(text: str, result: MathResult) -> list[str]:
    """Check that a generated explanation preserves the deterministic record."""
    reasons: list[str] = []
    if result.status == "blocked":
        return reasons
    claims = result.required_claims()
    allow_global = len(claims) == 1
    for label, value in claims:
        if value == 0.0:
            continue
        if not _claim_present(text, label, value, allow_global=allow_global):
            reasons.append(f"the verified result {label} ({value:.6g}) was changed or omitted")
    if result.chart:
        blocks = re.findall(r"```chart(?:-json)?\s*(.*?)```", text, flags=re.I | re.S)
        parsed_blocks: list[dict[str, Any]] = []
        for block in blocks:
            try:
                chart = json.loads(block)
            except (TypeError, json.JSONDecodeError):
                reasons.append("a chart block is not valid JSON")
                continue
            parsed_blocks.append(chart)
        if not blocks or not parsed_blocks:
            reasons.append("the verified chart block is missing")
        elif not all(_chart_matches(chart, result.chart) for chart in parsed_blocks):
            reasons.append("the chart does not match the verified computation")
    return reasons


def validate_reply(
    reply: str,
    message: str,
    response_language: str,
    mode: str = "converse",
    evidence_available: bool = False,
    math_result: MathResult | None = None,
) -> ValidationResult:
    """Apply conservative, independent checks to a generated reply."""
    reasons: list[str] = []
    text = str(reply or "").strip()
    if len(text) < 2:
        return ValidationResult(False, ["the reply is empty"])

    folded = text.casefold()
    for phrase in _BANNED_PHRASES:
        if phrase in folded:
            reasons.append("the reply contains a banned template or internal error phrase: " + phrase)

    if evidence_available:
        for phrase in _VERIFICATION_CLAIM:
            if phrase in folded:
                reasons.append("an unsupported dictionary-verification claim was made")

    if "[source:" in folded and not evidence_available:
        reasons.append("a source citation was produced without a retrieved passage")

    if mode == "translate_into_chichewa" and detect_language(text) == "EN" and len(text) > 40:
        reasons.append("a Chichewa translation request received an English reply")
    elif mode == "translate_into_english" and detect_language(text) == "CH" and len(text) > 40:
        reasons.append("an English translation request received a Chichewa reply")
    elif str(response_language).upper() == "CH" and detect_language(text) == "EN" and len(text) > 60:
        reasons.append("the selected response language was CH but the reply is English")
    elif str(response_language).upper() == "EN" and detect_language(text) == "CH" and len(text) > 60:
        reasons.append("the selected response language was EN but the reply is Chichewa")

    if (str(response_language).upper() == "CH" and mode in ("converse", "followup")
            and ("nthabwala" in folded or "nkhani ya" in folded)):
        reasons.append("a Chichewa social reply invented a joke instead of using verified warm lines")

    if text.count("\\(") != text.count("\\)") or text.count("\\[") != text.count("\\]"):
        reasons.append("LaTeX math delimiters are unbalanced")
    if text.count("```") % 2:
        reasons.append("a fenced code/chart block is unfinished")

    paragraphs = _paragraphs(text)
    if len(paragraphs) != len(set(paragraphs)):
        reasons.append("the reply repeats an identical paragraph")

    if len(text) > 120 and text[-1] in ",;:":
        reasons.append("the reply ends mid-sentence")

    if math_result is not None:
        reasons.extend(_validate_math_result(text, math_result))

    return ValidationResult(not reasons, reasons)


def honest_fallback(response_language: str = "EN") -> str:
    """Return a short, truthful limitation in the selected language."""
    if str(response_language).upper() == "CH":
        return (
            "Pepani, sindinathe kutsimikizira yankho lodalirika kuchokera m’zolemba "
            "zomwe zilipo. Mungandipatse chiganizo chomwe mawuwa agwiritsidwa ntchito, "
            "kapena mufunsenso m’njira ina?"
        )
    return (
        "I could not verify a reliable answer from the available references. Please "
        "share the sentence or context, or rephrase the question so I can help accurately."
    )
