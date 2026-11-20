"""Deterministic computation routing for CRARA.

This module decides whether a conversational turn is a computational question,
selects a narrow operation, supplies only explicitly available inputs, and
returns a structured proof record. It never guesses missing data and never
delegates arithmetic to a language model.
"""
from __future__ import annotations

import ast
import copy
import re
from typing import Any

from . import datasets, descriptive, epidemiology, inference, mathsdrill, parsing, probability, regression, symbolic
from .registry import formula_result, lookup_symbol
from .results import MathResult, blocked_result

_CAPABILITIES: dict[str, list[str]] = {
    "pure_mathematics": [
        "arithmetic", "algebra", "equations and inequalities", "calculus", "matrix and vector algebra",
        "coordinate geometry", "trigonometry", "complex numbers", "combinatorics",
        "numerical roots and optimisation", "differential equations", "curated quadratic-formula derivation",
    ],
    "probability": [
        "Bayes theorem", "probability rules", "binomial", "Poisson", "normal", "t", "chi-square",
        "F", "exponential", "uniform", "central limit theorem",
    ],
    "statistics": [
        "descriptive statistics with explicit quartile conventions", "frequency tables",
        "confidence intervals", "one-sample, independent and paired t tests", "chi-square tests",
        "ANOVA", "Mann–Whitney, Wilcoxon and Kruskal–Wallis tests", "multiple-comparison correction",
        "power analysis", "correlation and regression",
    ],
    "biostatistics": [
        "odds, risk and hazard ratios", "NNT/NNH", "sensitivity, specificity and predictive values",
        "ROC/AUC", "sample size", "effect sizes", "Kaplan–Meier survival", "Cox regression",
        "Poisson and negative-binomial regression",
    ],
    "data_support": ["pasted CSV or Markdown tables", "uploaded CSV/Excel document passages", "column-level missingness and duplicate checks"],
    "knowledge_registry": ["context-sensitive symbol meanings", "formulas with inputs, assumptions, applications and examples"],
    "mathsdrill_complement": [
        "school sequences", "coordinate transformations", "mensuration", "circle geometry", "similarity",
        "loci", "bearings", "linear programming", "linear modelling", "graph reading", "curated step justifications",
    ],
}

_MATH_CUE = re.compile(
    r"\b(?:calculate|compute|evaluate|solve|simplify|expand|factor|differentiate|derivative|integrate|integral|limit|"
    r"determinant|inverse|eigenvalue|eigenvalues|eigenvector|matrix|vector|dot\s+product|"
    r"cross\s+product|magnitude|distance|midpoint|slope|gradient|permutation|combination|"
    r"factorial|probability|chance|bayes|binomial|poisson|normal\s+distribution|percentile|"
    r"quantile|mean|median|mode|variance|standard\s+deviation|quartile|iqr|confidence\s+interval|"
    r"t[-\s]?test|chi[-\s]?square|anova|mann[-\s]?whitney|wilcoxon|kruskal|multiple\s+comparison|"
    r"holm|bonferroni|fdr|power|correlation|regression|odds\s+ratio|risk\s+ratio|relative\s+risk|"
    r"hazard\s+ratio|nn[ht]|sensitivity|specificity|predictive\s+value|roc|auc|sample\s+size|"
    r"effect\s+size|cohen|kaplan|survival|cox|summarise|summarize|descriptive\s+statistics|root|"
    r"optimise|optimize|minimum|maximum|formula|symbol)\b",
    re.I,
)
_FOLLOWUP = re.compile(r"^(?:and|also|then|what about|now)\b", re.I)
_SYMBOL_TOKEN = re.compile(
    r"[≈≠≤≥±√∑∏∞∂∇∫∮Δπθαβλμσρℝℤℚℕ∈∉⊂⊆∩∪∅∴∵]|"
    r"\b(?:OR|RR|HR|IQR|SE|CI|df|NNT|H₀|H₁|x̄|s²|σ²|β₀|β₁|ŷ|p|r|t|Z|F|Q1|Q2|Q3)\b"
)
_SYMBOL_QUESTION = re.compile(r"\b(?:what does|meaning of|means|mean of|interpret|symbol|stands? for|tanthauzo)\b", re.I)
_FORMULA_QUESTION = re.compile(r"\b(?:formula|equation)\b", re.I)
_AMBIGUOUS_SYMBOLS = {"OR", "RR", "HR", "p", "r", "t", "Z", "F", "Q1", "Q2", "Q3", "SE", "CI", "df", "n", "s"}
_SYMBOL_DOMAIN_CONTEXT = re.compile(
    r"\b(?:math\w*|statistic\w*|probabilit\w*|epidemiolog\w*|clinical|trial|research|"
    r"regression|survival|diagnostic|hypothesis|dataset|data|table|odds|risk|hazard|"
    r"sensitivity|specificity|confidence|quartile|sample)\b",
    re.I,
)
_EXPLICIT_CALCULATION = re.compile(
    r"\b(?:calculate|compute|evaluate|work\s+out|solve|find|derive|fit|plot|construct|test)\b", re.I,
)
_SCHOOL_MATH_CUE = re.compile(
    r"\b(?:nth\s+term|arithmetic\s+(?:sequence|progression)|geometric\s+(?:sequence|progression)|"
    r"common\s+difference|common\s+ratio|reflect\w*|rotat\w*|translat\w*|enlarg\w*|"
    r"locus|perpendicular\s+bisector|equidistant\s+from|\bbearing\b|navigation|mensuration|"
    r"(?:area|perimeter|circumference|volume|surface\s+area)\s+of\s+(?:a|an|the)?\s*"
    r"(?:rectangle|triangle|circle|trapezium|trapezoid|cylinder|cone|sphere|cuboid)|"
    r"(?:rectangle|circle|trapezium|cylinder|cone|sphere|cuboid)\s+(?:with|of)\s+"
    r"(?:radius|length|width|height|base)|chord|tangent|arc\s+length|sector\s+area|"
    r"similarity|similar\s+(?:figures?|triangles?|shapes?)|linear\s+program\w*|linear\s+model|"
    r"subject\s+to|"
    r"fixed\s+cost|depreciat\w*|read\s+off|equation\s+of\s+the\s+line)\b",
    re.I,
)
_CLINICAL_CONTEXT = re.compile(
    r"\b(?:patient|diagnos\w*|symptom\w*|treat\w*|management|prescri\w*|medication|"
    r"dose|blood\s+pressure|arterial\s+pressure|what\s+should\s+i\s+do|should\s+i)\b", re.I,
)
_DATA_PLACEHOLDER = re.compile(
    r"\b(?:these|those|the\s+following|given|provided|supplied|following)\s+"
    r"(?:numeric\s+|numerical\s+)?(?:observations?|values?|data|numbers?|scores?|counts?|table|sample)\b",
    re.I,
)
_NUMERIC_DATA_HINT = re.compile(
    r"\b(?:values?|observations?|data|numbers?|scores?|times?|events?|x|y|before|after|group)\b", re.I,
)


def capabilities() -> dict[str, list[str]]:
    return copy.deepcopy(_CAPABILITIES)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _has(text: str, pattern: str) -> bool:
    return re.search(pattern, text, re.I | re.S) is not None


def _numbers(text: str) -> list[float]:
    return parsing.extract_numbers(str(text or ""), limit=120)


def _val(text: str, names: tuple[str, ...]) -> float | None:
    for name in names:
        pattern = rf"(?:^|[\s,(])(?:{re.escape(name)})\b\s*(?:is|=|:|of)?\s*({parsing._NUMBER})"
        match = re.search(pattern, str(text or ""), re.I)
        if match:
            value, _ = parsing._to_float(match.group(1))
            if value is not None:
                return value
    return None


def _line_value(text: str, label: str) -> list[float]:
    for line in str(text or "").splitlines():
        match = re.search(rf"\b{re.escape(label)}\b\s*(?:values?|scores?|times?|data)?\s*(?:[:=]|is|are)?\s*(.+)", line, re.I)
        if match:
            segment = re.split(r"(?:,|;)\s*[A-Za-z_]\w*\s*[:=]", match.group(1), maxsplit=1)[0]
            values = _numbers(segment)
            if values:
                return values
    return []


def _labelled_vector(text: str, label: str) -> list[float]:
    match = re.search(rf"\b{re.escape(label)}\b\s*(?:[:=]|is|are)?\s*(\[[^\]]+\]|\([^\)]+\))", str(text or ""), re.I)
    if match:
        return _vector(match.group(1))
    return _line_value(text, label)


def _vector(text: str) -> list[float]:
    raw = str(text or "").strip()
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, (list, tuple)):
            return [float(v) for v in parsed]
    except (ValueError, SyntaxError, TypeError):
        pass
    return _numbers(raw)


def _matrix(text: str) -> list[list[float]]:
    match = re.search(r"\[\s*\[[^\]]+\]\s*(?:,\s*\[[^\]]+\]\s*)*\]", str(text or ""))
    if match:
        try:
            parsed = ast.literal_eval(match.group(0))
            return [[float(v) for v in row] for row in parsed]
        except (ValueError, SyntaxError, TypeError):
            pass
    if ";" in str(text):
        rows = []
        for part in str(text).split(";"):
            values = _numbers(part)
            if values:
                rows.append(values)
        if rows and len({len(row) for row in rows}) == 1:
            return rows
    values = _numbers(text)
    size = int(len(values) ** 0.5)
    if size >= 2 and size * size == len(values) and len(values) >= 4:
        return [values[i * size:(i + 1) * size] for i in range(size)]
    return []


def _points(text: str) -> list[tuple[float, float]]:
    pairs = re.findall(r"\(\s*(" + parsing._NUMBER + r")\s*,\s*(" + parsing._NUMBER + r")\s*\)", str(text or ""))
    result = []
    for first, second in pairs:
        x, _ = parsing._to_float(first)
        y, _ = parsing._to_float(second)
        if x is not None and y is not None:
            result.append((x, y))
    return result


def _contingency(text: str) -> dict[str, int] | None:
    parsed = parsing.parse_two_by_two(text)
    if parsed:
        return parsed
    # Only an explicit grid is safe. Four bare integers in prose have no
    # reliable a/b/c/d ordering and must not be silently promoted to a table.
    source = str(text or "")
    explicit_grid = bool(re.search(
        r"\[\s*\[[^\]]+\]\s*,\s*\[[^\]]+\]\s*\]|\[\s*[-\d.,\s]+\s*\]\s*[;,]\s*\[\s*[-\d.,\s]+\s*\]",
        source,
    )) or bool(re.search(r"^\s*[-\d.,\s]+\s*[;,]\s*[-\d.,\s]+\s*$", source))
    if not explicit_grid:
        return None
    matrix = _matrix(text)
    if len(matrix) == 2 and all(len(row) == 2 for row in matrix):
        return {"a": int(matrix[0][0]), "b": int(matrix[0][1]), "c": int(matrix[1][0]), "d": int(matrix[1][1])}
    return None


def _groups(text: str, minimum: int = 2) -> list[list[float]]:
    bracketed = re.findall(r"\[\s*[-\d.,\s]+\]", str(text or ""))
    if len(bracketed) >= minimum:
        groups = [_vector(item) for item in bracketed]
        if all(len(group) >= 2 for group in groups):
            return groups
    rows = []
    for line in str(text or "").splitlines():
        match = re.search(r"\b(?:group|arm)\s*([A-Za-z0-9]+)?\b[:\-]?\s*(.+)", line, re.I)
        if match:
            values = _numbers(match.group(2))
            if len(values) >= 2:
                rows.append(values)
    if len(rows) >= minimum:
        return rows
    return []


def _looks_tabular(text: str) -> bool:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    return sum(1 for line in lines if "," in line or "|" in line or "\t" in line) >= 2


def _structured_source(text: str) -> bool:
    """True only for passages shaped like data, not narrative prose with numbers."""
    source = str(text or "")
    if _looks_tabular(source):
        return True
    return bool(re.search(
        r"\[[^\]]*\d[^\]]*\]|\b(?:values?|observations?|scores?|counts?)\s*[:=]\s*[\d,\s.]+",
        source, re.I,
    ))


def _dataset(message: str, context: str) -> tuple[list[float], dict[str, Any]]:
    prompt = str(message or "")
    prompt = re.sub(r"\b\d+(?:\.\d+)?\s*%\s+(?=(?:confidence\s+interval|ci)\b)", "", prompt, flags=re.I)
    cleaned = re.sub(
        r"^(?:please\s+)?(?:can\s+you\s+)?(?:calculate|compute|find|give|show|what\s+is|what's|determine|report)\s+"
        r"(?:the\s+)?(?:full\s+)?(?:descriptive\s+statistics?|summary\s+statistics?|mean|median|mode|variance|"
        r"standard\s+deviation|quartiles?|iqr|range|coefficient\s+of\s+variation|five[-\s]number\s+summary|"
        r"confidence\s+interval|ci)\s+"
        r"(?:of|for|from|on)?\s*",
        "", prompt, flags=re.I,
    )
    values, meta = parsing.parse_dataset(cleaned)
    if len(values) < 2 and context and context != prompt:
        values, meta = parsing.parse_dataset(context)
    return values, meta


def _context_text(message: str, history: list[dict] | None, source_text: str | None) -> str:
    """Only pass data-bearing source passages into the computation parser.

    Retrieved documents and old turns are untrusted context. They are included
    only when this turn explicitly asks about uploaded data, or when a short
    follow-up refers back to a clearly labelled numeric list in recent history.
    This prevents unrelated years, percentages or sample sizes from becoming
    invented observations.
    """
    text = str(message or "")
    pieces: list[str] = []
    data_request = re.search(
        r"\b(?:csv|excel|workbook|spreadsheet|uploaded|dataset|data|table|document|attached|summarise|summarize)\b",
        text, re.I,
    )
    if source_text and data_request and _structured_source(source_text):
        pieces.append(str(source_text))
    pieces.append(text)
    if not re.search(r"\d", text) and history and _FOLLOWUP.search(text):
        for item in history[-2:]:
            if item.get("role") != "user":
                continue
            previous = str(item.get("content", ""))
            if _NUMERIC_DATA_HINT.search(previous) and len(re.findall(r"\d", previous)) >= 2:
                pieces.append(previous)
    return "\n".join(piece for piece in pieces if piece.strip())


def detect_math_request(
    message: str,
    history: list[dict] | None = None,
    source_text: str | None = None,
) -> tuple[bool, str]:
    """Conservatively classify a turn as computational.

    A computation is detected only when a task cue is present together with an
    explicit number, variable, symbol, or supplied dataset. Ordinary academic
    discussion stays on the normal language-model path.
    """
    text = _clean(message)
    if not text:
        return False, "none"
    if _SYMBOL_QUESTION.search(text):
        symbol_tokens = _SYMBOL_TOKEN.findall(text)
        if symbol_tokens and (
            _SYMBOL_DOMAIN_CONTEXT.search(text)
            or any(token not in _AMBIGUOUS_SYMBOLS for token in symbol_tokens)
        ):
            return True, "symbol"
    if _FORMULA_QUESTION.search(text) and _MATH_CUE.search(text):
        return True, "formula"
    cue = bool(_MATH_CUE.search(text) or _SCHOOL_MATH_CUE.search(text))
    explicit_calculation = bool(_EXPLICIT_CALCULATION.search(text))
    has_value = bool(re.search(r"\d|[A-Za-z]\s*=|π|√|∫|∑|[μσλθαβρ]", text))
    if _FOLLOWUP.search(text) and history:
        has_value = True
    arithmetic_only = re.fullmatch(
        r"(?:(?:what\s+is|what's|calculate|compute|evaluate|find)\s+)?[\d\s+\-*/().,%^]+[?.!]*",
        text, re.I,
    ) is not None and bool(re.search(r"\d", text))
    if arithmetic_only:
        return True, "arithmetic"
    source_available = bool(re.search(r"\d", str(source_text or ""))) and bool(re.search(
        r"\b(?:csv|excel|workbook|spreadsheet|uploaded|dataset|data|table|document|attached)\b", text, re.I,
    ))
    if cue and source_available:
        return True, "source-computation"
    # Clinical or patient-facing questions must stay on the biomedical language
    # path unless the user clearly asks for a deterministic computation.
    if _CLINICAL_CONTEXT.search(text) and not explicit_calculation:
        return False, "none"
    # A missing-input refusal is narrow: an explicit calculation verb combined
    # with a placeholder such as "these observations", or an explicit request
    # for a design calculation with no inputs. Ordinary questions that merely
    # mention a mean, study or odds ratio are conceptual/retrieval turns.
    design_placeholder = bool(re.search(
        r"\b(?:sample\s+size|statistical\s+power|power\s+analysis)\b", text, re.I
    )) and not has_value
    missing_values_request = explicit_calculation and (
        bool(_DATA_PLACEHOLDER.search(text)) or design_placeholder
    )
    if missing_values_request:
        return True, "missing-input-computation"
    if not explicit_calculation and re.search(
            r"\b(?:explain|describe|discuss|why|how)\b", text, re.I
    ):
        return False, "none"
    return (cue and has_value), "computation" if cue and has_value else "none"


def _dispatch(text: str, context: str, message: str) -> MathResult | None:
    lower = text.casefold()

    # Context-sensitive symbols and formula definitions are deterministic lookups.
    # An unmatched lookup is not a failed computation: it returns to the normal
    # language path rather than producing a false refusal.
    if _SYMBOL_QUESTION.search(text):
        tokens = _SYMBOL_TOKEN.findall(text)
        if tokens:
            for token in tokens:
                result = lookup_symbol(token, text)
                if result is not None:
                    return result
            return None
    # Deterministic derivations are curated fact, not free-form model output.
    # This keeps a common school derivation available during provider outages.
    if re.search(r"\bquadratic\s+formula\b", text, re.I) and re.search(
            r"\b(?:derive|derivation|prove|proof|complete|completing|show|work\s+out)\b", text, re.I):
        return symbolic.quadratic_formula_derivation()

    if "formula" in lower or "equation for" in lower:
        query = re.sub(
            r"^(?:please\s+)?(?:what is|what's|give me|show me|show|state|explain|define)\s+",
            "", text, flags=re.I,
        )
        query = re.sub(r"\b(?:formula|equation)\s+(?:for|of)\b", " ", query, flags=re.I)
        for _ in range(3):
            query = re.sub(r"^(?:the|a|an)\s+", "", query, flags=re.I)
        query = re.sub(r"\s+(?:in simple terms|please)$", "", query, flags=re.I)
        result = formula_result(query.strip(" ?.!;:,"))
        if result is not None:
            return result
        return None

    # Additive MathsDrill complement for school mathematics. It is deliberately
    # narrow and first defers to CRARA's own biomedical/statistical contexts.
    # If a school cue matched but the complement could not parse it safely, the
    # turn returns to the language path instead of becoming a false refusal.
    if _SCHOOL_MATH_CUE.search(text):
        school_result = mathsdrill.solve(text)
        if school_result is not None:
            return school_result
        return None

    # Structured pasted data and uploaded CSV/Excel passages.
    if _has(text, r"\b(?:csv|excel|workbook|spreadsheet|dataset|data\s+table|uploaded\s+data|summarise|summarize)\b"):
        if _looks_tabular(context):
            summary = datasets.inspect_csv(context, name="supplied data")
            if summary.status == "ok":
                return summary

    # Probability rules, Bayes and distribution calculations.
    if _has(text, r"\bbayes\b|conditional\s+probability|posterior"):
        prevalence = _val(text, ("prevalence", "prior"))
        sensitivity = _val(text, ("sensitivity", "true positive rate", "likelihood"))
        specificity = _val(text, ("specificity", "true negative rate"))
        fpr = _val(text, ("false positive rate", "fpr", "false alarm rate"))
        evidence = _val(text, ("evidence", "test positive rate"))
        positive = _has(text, r"\bpositive\b|\bsensitivity\b")
        if prevalence is not None and sensitivity is not None and (fpr is not None or specificity is not None):
            false_positive = fpr if fpr is not None else 1.0 - specificity
            if false_positive is not None:
                evidence = sensitivity * prevalence + false_positive * (1 - prevalence)
                likelihood = sensitivity if positive else 1 - sensitivity
                return probability.bayes(prevalence, likelihood, evidence, event="disease", test="positive result")
        if prevalence is None or sensitivity is None or evidence is None:
            return blocked_result(
                "bayes", "Bayes calculation needs a prior, the relevant conditional probability and the total evidence probability.",
                domain="probability",
            )
        return probability.bayes(prevalence, sensitivity if positive else 1 - sensitivity, evidence)

    distribution_name = None
    for key, candidate in (
        ("binomial", r"\bbinomial\b|\btrials\b|\bsuccesses\b"), ("poisson", r"\bpoisson\b"),
        ("normal", r"\bnormal\b|\bgaussian\b"), ("t", r"\bt[-\s]?distribution\b|\bstudent'?s t\b"),
        ("chi-square", r"\bchi[-\s]?square\b"), ("f", r"\bf[-\s]?distribution\b"),
        ("exponential", r"\bexponential\b"), ("uniform", r"\buniform\b"),
    ):
        if re.search(candidate, text, re.I):
            distribution_name = key
            break
    if distribution_name and not _has(text, r"\btest\b|\banova\b|contingency|goodness\s+of\s+fit"):
        kind = "pmf"
        if _has(text, r"\b(?:percentile|quantile|critical value|z[\s_-]?score)\b"):
            kind = "quantile"
        elif _has(text, r"\bbetween\b"):
            kind = "between"
        elif _has(text, r"\b(?:at most|less than|cdf|cumulative|no more than)\b"):
            kind = "cdf"
        elif _has(text, r"\b(?:at least|greater than|survival|upper tail)\b"):
            kind = "sf"
        elif _has(text, r"\bdensity\b|\bpdf\b"):
            kind = "pdf"
        point = _val(text, ("x", "k", "value", "score"))
        quantile = _val(text, ("quantile", "percentile", "probability"))
        if quantile is not None and quantile > 1:
            quantile /= 100.0
        numbers = _numbers(context)
        if point is None and distribution_name == "binomial":
            trials = _val(text, ("n", "trials"))
            p_value = _val(text, ("p", "probability of success"))
            successes = _val(text, ("k", "successes"))
            if trials is None or p_value is None or successes is None:
                fractions = [v for v in numbers if 0 < v < 1]
                integers = sorted({int(v) for v in numbers if float(v).is_integer() and v >= 1})
                if fractions and len(integers) >= 2:
                    p_value = fractions[0]
                    trials = trials or integers[-1]
                    successes = successes or integers[0]
            if trials is not None and p_value is not None and successes is not None:
                return probability.distribution(distribution_name, kind=kind, x=successes, n=int(trials), p=p_value)
        if point is None and distribution_name == "poisson":
            lam = _val(text, ("lambda", "λ", "mean rate", "rate"))
            if lam is None and numbers:
                lam = numbers[0]
            if lam is not None:
                point = _val(text, ("k", "x", "value"))
                if point is None and len(numbers) > 1:
                    point = numbers[-1]
                return probability.distribution(distribution_name, kind=kind, x=point, lam=lam)
        return probability.distribution(
            distribution_name, kind=kind, x=point, quantile=quantile,
            n=int(_val(text, ("n", "trials"))) if _val(text, ("n", "trials")) else None,
            p=_val(text, ("p", "probability")),
            mu=_val(text, ("mu", "μ", "mean")), sigma=_val(text, ("sigma", "σ", "sd", "standard deviation")),
            lam=_val(text, ("lambda", "λ", "rate")), df=_val(text, ("df", "degrees of freedom")),
            df2=_val(text, ("df2", "denominator degrees of freedom")),
            low=_val(text, ("low", "minimum", "a")), high=_val(text, ("high", "maximum", "b")),
        )

    if _has(text, r"\bcentral limit theorem\b|\bsample mean\b.*probability"):
        population_mean = _val(text, ("population mean", "mean", "μ"))
        population_sd = _val(text, ("population sd", "population standard deviation", "σ"))
        sample_n = _val(text, ("n", "sample size"))
        target = _val(text, ("target", "threshold", "cutoff"))
        if population_mean is None or population_sd is None or sample_n is None or target is None:
            return blocked_result(
                "central_limit_theorem",
                "CLT approximation needs the population mean, population SD, sample size and target value.",
                domain="probability",
            )
        return probability.central_limit_theorem(population_mean, population_sd, int(sample_n), target)

    # Pure mathematics.
    if _has(text, r"\b(?:determinant|inverse|transpose|eigenvalues?|eigenvectors?|rref|reduced row)\b"):
        matrix = _matrix(context)
        if not matrix:
            return blocked_result("matrix", "Provide the matrix explicitly, for example [[1,2],[3,4]].", domain="mathematics")
        operation = next((name for name in ("eigen", "inverse", "determinant", "transpose", "rref") if name in lower), "determinant")
        return symbolic.matrix_operation(matrix, operation)
    if _has(text, r"\bdot\s+product\b|\bcross\s+product\b|\bvector\b|\bmagnitude\b|\bunit\s+vector\b"):
        vectors = re.findall(r"\[\s*[-\d.,\s]+\]", str(context))
        if len(vectors) >= 2 and _has(text, r"dot|cross"):
            return symbolic.vector_operation(_vector(vectors[0]), _vector(vectors[1]), "cross" if "cross" in lower else "dot")
        if vectors:
            return symbolic.vector_operation(_vector(vectors[0]), operation="unit" if "unit" in lower else "norm")
        return blocked_result("vector", "Provide the vector(s) explicitly, for example [1,2,3].", domain="mathematics")
    if _has(text, r"\bdistance\b|\bmidpoint\b|\bmid-point\b|\bslope\b.*line|\bgradient\b.*line"):
        points = _points(context)
        if len(points) < 2:
            return blocked_result("coordinate_geometry", "Two Cartesian points are needed.", domain="mathematics")
        operation = "midpoint" if "mid" in lower else "slope" if "slope" in lower or "gradient" in lower else "distance"
        return symbolic.coordinate_geometry(points[0], points[1], operation)
    if _has(text, r"\bfactorial\b|permutation|\bcombination\b|\bnpr\b|\bncr\b|\bways to (?:arrange|choose|select)\b"):
        nums = [int(v) for v in _numbers(context) if float(v).is_integer()]
        if len(nums) < 1:
            return blocked_result("combinatorics", "Provide n and, for arrangements or selections, r.", domain="mathematics")
        n = nums[0]
        r = nums[1] if len(nums) > 1 else None
        if "permutation" in lower or "arrange" in lower:
            operation = "permutation"
        elif "combination" in lower or "choose" in lower or "select" in lower:
            operation = "combination"
        else:
            operation = "factorial"
        return symbolic.combinatorics(n, r, operation)
    if _has(text, r"\b(?:modulus|argument|conjugate)\b.*\bcomplex\b|\bcomplex\s+number\b"):
        expression = parsing.extract_expression(text, ("modulus of", "argument of", "conjugate of", "simplify")) or text
        operation = "modulus" if "modulus" in lower else "argument" if "argument" in lower else "conjugate" if "conjugate" in lower else "simplify"
        return symbolic.complex_operation(expression.replace("i", "I"), operation)
    if _has(text, r"\bderivative\b|\bdifferentiate\b"):
        expression = parsing.extract_expression(text, ("derivative of", "differentiate")) or text
        order = 2 if "second derivative" in lower else 1
        return symbolic.differentiate(expression, variable=_variable_from(text), order=order)
    if _has(text, r"\bintegral\b|\bintegrate\b"):
        expression = parsing.extract_expression(text, ("integral of", "integrate")) or text
        bounds = re.findall(parsing._NUMBER, text)
        if _has(text, r"\bfrom\b.*\bto\b") and len(bounds) >= 2:
            return symbolic.integrate(expression, variable=_variable_from(text), lower=bounds[-2], upper=bounds[-1])
        return symbolic.integrate(expression, variable=_variable_from(text))
    if _has(text, r"\blimit\b"):
        expression = parsing.extract_expression(text, ("limit of", "limit")) or text
        tends = re.search(r"(?:as|at|to)\s+(" + parsing._NUMBER + r"|x)\s*(?:→|->|approaches|tends to)?", text, re.I)
        return symbolic.limit(expression, variable=_variable_from(text), tends_to=tends.group(1) if tends else "0")

    # Descriptive statistics.
    if _has(text, r"\bmean\b|\bmedian\b|\bmode\b|\bvariance\b|standard\s+deviation|\bquartile|\biqr\b|"
                  r"\brange\b|five[-\s]number|descriptive\s+statistics|\bsummarise\b|\bsummarize\b|"
                  r"frequency\s+distribution|confidence\s+interval|\bci\b"):
        values, meta = _dataset(message, context)
        if len(values) < 2:
            return blocked_result("descriptive_statistics", "At least two numeric observations are required.", domain="statistics", source=meta.get("source"))
        method, _alias = parsing.detect_quartile_method(text)
        confidence = _val(text, ("confidence", "confidence level"))
        if confidence is None:
            match = re.search(r"\b(\d{2,3})\s*%", text)
            confidence = float(match.group(1)) / 100.0 if match else 0.95
        if confidence and confidence > 1:
            confidence /= 100.0
        return descriptive.describe(values, quartile_method=method, confidence=confidence,
                                    data_name=str(meta.get("source", "observations")))
    if _has(text, r"\bgrouped\s+(?:data|frequency)|grouped\s+summary"):
        values, _meta = _dataset(message, context)
        return descriptive.grouped_summary(values)

    # Inferential statistics.
    if _has(text, r"\bmann[-\s]?whitney\b|\bwilcoxon\b|\bkruskal\b"):
        name = "mann_whitney" if "mann" in lower else "wilcoxon" if "wilcoxon" in lower else "kruskal"
        if name == "kruskal":
            groups = _groups(context)
            return inference.nonparametric(name, groups[0] if groups else [], groups[1:] if len(groups) > 1 else [])
        first, second = _labelled_vector(text, "before"), _labelled_vector(text, "after")
        if not first or not second:
            groups = _groups(context)
            first = groups[0] if groups else []
            second = groups[1] if len(groups) > 1 else []
        return inference.nonparametric(name, first, second)
    if _has(text, r"\banova\b|\bf[-\s]?test\b"):
        groups = _groups(context)
        if len(groups) < 2:
            return blocked_result("anova", "Provide at least two groups with two or more observations each.", domain="inference")
        return inference.anova(groups)
    if _has(text, r"\bchi[-\s]?square\b|contingency\s+table|\bcram[eé]r\b"):
        table = _contingency(context)
        if not table:
            return blocked_result("chi_square", "Provide a contingency table, for example [[10,20],[20,10]].", domain="inference")
        return inference.chi_square([[table["a"], table["b"]], [table["c"], table["d"]]], correction=not _has(text, r"no\s+(?:yates\s+)?correction|uncorrected"))
    if _has(text, r"\bpaired\s+t[-\s]?test\b|\bbefore\b.*\bafter\b"):
        before, after = _labelled_vector(text, "before"), _labelled_vector(text, "after")
        if not before or not after:
            groups = _groups(context)
            before = groups[0] if groups else []
            after = groups[1] if len(groups) > 1 else []
        return inference.paired_t(before, after)
    if _has(text, r"\b(?:independent|unpaired|two[-\s]sample|welch)\s+t[-\s]?test\b"):
        groups = _groups(context)
        if len(groups) < 2:
            return blocked_result("independent_t", "Provide two independent groups with their observations.", domain="inference")
        return inference.independent_t(groups[0], groups[1], equal_var=_has(text, r"equal\s+variance|pooled"))
    if _has(text, r"\bt[-\s]?test\b|test whether.*mean|test if.*mean|one[-\s]sample"):
        values, _meta = _dataset(message, context)
        mu0 = _val(text, ("mu0", "μ0", "hypothesised mean", "hypothesized mean", "null value"))
        if mu0 is None:
            candidates = [v for v in _numbers(context) if v not in values]
            if candidates:
                mu0 = candidates[-1]
        if not values or mu0 is None:
            return blocked_result("one_sample_t", "Provide the observations and the hypothesised population mean μ₀.", domain="inference")
        alternative = "greater" if _has(text, r"greater than|increase") else "less" if _has(text, r"less than|decrease") else "two-sided"
        return inference.one_sample_t(values, mu0, alternative)
    if _has(text, r"multiple\s+comparison|multiple\s+testing|bonferroni|\bholm\b|\bfdr\b|benjamini"):
        p_values = _numbers(context)
        p_values = [p for p in p_values if 0 <= p <= 1]
        if not p_values:
            return blocked_result("multiple_comparisons", "Provide the p-values to adjust.", domain="inference")
        method = "bonferroni" if "bonferroni" in lower else "fdr_bh" if "fdr" in lower or "benjamini" in lower else "holm"
        return inference.multiple_comparisons(p_values, method)
    if _has(text, r"\bpower\b.*\bproportion\b|\bpower\b.*\btwo[-\s]?proportion"):
        return inference.power_two_proportions(
            _val(text, ("p1", "proportion 1", "group 1 proportion")) or 0.0,
            _val(text, ("p2", "proportion 2", "group 2 proportion")) or 0.0,
            int(_val(text, ("n", "n per group", "sample size per group")) or 0),
        )

    # Regression, correlation and survival.
    if _has(text, r"\bkaplan[-\s–—]?meier\b|survival\s+curve|product[-\s]?limit"):
        times = _labelled_vector(text, "time") or _labelled_vector(text, "times")
        events = _labelled_vector(text, "event") or _labelled_vector(text, "status")
        return regression.kaplan_meier(times, events)
    if _has(text, r"\bcox\b|proportional\s+hazards|hazard\s+ratio.*regression"):
        times = _labelled_vector(text, "time") or _labelled_vector(text, "times")
        events = _labelled_vector(text, "event") or _labelled_vector(text, "status")
        predictors = _labelled_vector(text, "x") or _labelled_vector(text, "predictor")
        return regression.cox_regression(predictors, times, events)
    if _has(text, r"\blogistic\s+regression\b|\bodds\s+ratio\b.*regression|\boutcome\b.*binary"):
        y = _labelled_vector(text, "y") or _labelled_vector(text, "outcome")
        x = _labelled_vector(text, "x") or _labelled_vector(text, "predictor")
        return regression.logistic_regression(x, y, multinomial=_has(text, r"multinomial|more than two (?:categories|outcomes)"))
    if _has(text, r"\bpoisson\s+regression\b|negative\s+binomial\s+regression|count\s+regression|\brate\s+ratio\b.*regression"):
        y = _labelled_vector(text, "y") or _labelled_vector(text, "count")
        x = _labelled_vector(text, "x") or _labelled_vector(text, "predictor")
        return regression.count_regression(x, y, "negative_binomial" if "negative binomial" in lower else "poisson")
    if _has(text, r"\blinear\s+regression\b|\bol\b|regress\b"):
        y = _labelled_vector(text, "y") or _labelled_vector(text, "outcome")
        x = _labelled_vector(text, "x") or _labelled_vector(text, "predictor")
        if not x:
            matrix = _matrix(context)
            x = matrix[0] if matrix else []
        return regression.linear_regression(x, y)
    if _has(text, r"\bcorrelation\b|\bpearson\b|\bspearman\b|\bkendall\b"):
        x, y = _labelled_vector(text, "x"), _labelled_vector(text, "y")
        method = "spearman" if "spearman" in lower else "kendall" if "kendall" in lower else "pearson"
        return regression.correlation(x, y, method)

    # Epidemiology, diagnostic accuracy and study design.
    if _has(text, r"\broc\b|\bauc\b"):
        labels = _labelled_vector(text, "label") or _labelled_vector(text, "outcome")
        scores = _labelled_vector(text, "score") or _labelled_vector(text, "prediction")
        return epidemiology.roc_auc(labels, scores)
    if _has(text, r"\bsensitivity\b|\bspecificity\b|predictive\s+value|likelihood\s+ratio|diagnostic\s+accuracy"):
        table = _contingency(context)
        if not table:
            return blocked_result("diagnostic_accuracy", "Provide a diagnostic 2x2 table a=TP, b=FP, c=FN, d=TN.", domain="epidemiology")
        prevalence = _val(text, ("prevalence", "prior probability"))
        return epidemiology.diagnostic_accuracy(table, prevalence)
    if _has(text, r"\bodds\s+ratio\b|risk\s+ratio|relative\s+risk|\bnn[ht]\b|attributable|2x2|contingency.*ratio"):
        table = _contingency(context)
        if not table:
            return blocked_result("epidemiological_measures", "Provide a 2x2 table a=exposed cases, b=exposed non-cases, c=unexposed cases, d=unexposed non-cases.", domain="epidemiology")
        return epidemiology.contingency_measures(table)
    if _has(text, r"sample\s+size.*(?:proportion|prevalence)|prevalence.*sample\s+size"):
        return epidemiology.sample_size_proportion(
            _val(text, ("expected proportion", "p", "prevalence")) or 0.0,
            _val(text, ("precision", "margin of error", "d")) or 0.0,
            _val(text, ("confidence", "confidence level")) or 0.95,
            int(_val(text, ("population", "N"))) if _val(text, ("population", "N")) else None,
        )
    if _has(text, r"sample\s+size.*means|sample\s+size.*difference|detect.*difference"):
        return epidemiology.sample_size_two_means(
            _val(text, ("delta", "difference", "effect")) or 0.0,
            _val(text, ("sd", "standard deviation")) or 0.0,
            _val(text, ("power",)) or 0.8,
        )
    if _has(text, r"effect\s+size|cohen'?s\s+d|\bd\s*=\s*\d"):
        value = _val(text, ("cohen's d", "cohens d", "effect size", "d"))
        if value is None:
            numbers = _numbers(context)
            value = numbers[-1] if numbers else None
        if value is None:
            return blocked_result("effect_size", "Provide the effect-size estimate.", domain="epidemiology")
        return epidemiology.effect_size_interpretation(value, "cohens_d")

    # Numerical methods.
    if _has(text, r"\b(?:root|zero)\b.*\bequation\b|newton.?raphson|numerical\s+root"):
        expression = parsing.extract_expression(text, ("root of", "zero of", "solve")) or text
        return symbolic.numerical_root(expression, _val(text, ("guess", "starting value", "x0")) or 0.0)
    if _has(text, r"\bminimi[sz]e\b|\bmaximi[sz]e\b|\boptimi[sz]\b|\bminimum\b|\bmaximum\b"):
        expression = parsing.extract_expression(text, ("minimise", "minimize", "maximise", "maximize", "optimise", "optimize")) or text
        return symbolic.optimize(expression, variable=_variable_from(text), kind="maximum" if "max" in lower else "minimum")

    # Equations, inequalities and generic simplification/arithmetic.
    if re.search(r"[<>≤≥]", text) and (_has(text, r"\bsolve\b|\binequality\b") or "=" not in text):
        expression = parsing.extract_expression(text, ("solve", "inequality")) or text
        return symbolic.inequality(expression, _variable_from(text))
    if "=" in text and _has(text, r"\bsolve\b|\bequation\b|\bunknown\b"):
        expression = parsing.extract_expression(text, ("solve", "equation")) or text
        return symbolic.solve(expression, variable=_variable_from(text))
    if _has(text, r"\bsimplify\b|\bexpand\b|\bfactor\b"):
        expression = parsing.extract_expression(text, ("simplify", "expand", "factor")) or text
        return symbolic.simplify(expression)
    expression = _arithmetic_expression(message)
    if expression:
        return symbolic.simplify(expression)
    if _SCHOOL_MATH_CUE.search(text) and not _EXPLICIT_CALCULATION.search(text):
        return None
    return blocked_result("mathematics", "No deterministic computation could be identified from the supplied information.", domain="mathematics")


def _variable_from(text: str) -> str:
    match = re.search(r"\b(?:with respect to|with respect|wrt|variable|in)\s+([A-Za-z])\b", str(text or ""), re.I)
    if match:
        return match.group(1).lower()
    for candidate in ("x", "t", "n", "y"):
        if re.search(rf"\b{candidate}\b", str(text or ""), re.I):
            return candidate
    return "x"


def _arithmetic_expression(message: str) -> str | None:
    text = str(message or "").strip()
    text = re.sub(r"^(?:please\s+)?(?:can\s+you\s+)?(?:what\s+is|what's|calculate|compute|evaluate|find)\s+", "", text, flags=re.I)
    text = text.rstrip("? .!")
    if len(text) > 200 or not re.search(r"\d", text):
        return None
    if not re.fullmatch(r"[\d\s+\-*/().,%^]+", text):
        return None
    return text.replace(",", "").replace("%", "/100")


def solve(
    message: str,
    history: list[dict] | None = None,
    source_text: str | None = None,
) -> MathResult | None:
    """Return a verified computation record, or None for non-computational turns.

    ``source_text`` may contain retrieved document passages. It is treated as
    untrusted data: only explicit numeric tables or datasets inside it are used.
    """
    text = _clean(message)
    detected, _kind = detect_math_request(text, history, source_text)
    if not detected:
        return None
    context = _context_text(text, history, source_text)
    try:
        return _dispatch(text, context, text)
    except Exception as exc:
        return blocked_result("mathematics", f"The computation could not be completed safely: {exc}", domain="general")
