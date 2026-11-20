"""MathsDrill-derived deterministic school-mathematics complement for CRARA.

Provenance
----------
Algorithm inventory informed by https://github.com/majaliwamin/mathsdrill
at commit 67e170f478be5383ad1fbdb2a0112121b2b1811d. The routines below are
independently implemented from standard mathematical formulae; no source code
from that repository is copied. CRARA's existing SymPy,
NumPy, SciPy, pandas and statsmodels engine remains the primary calculation
engine; this module is an additive fallback for school topics that engine does
not already route.

Excluded by design
------------------
Epidemiology, biostatistics, clinical inference, survival analysis, diagnostic
accuracy, sample-size/power calculations and medical statistics are NOT
implemented here. Those requests stay on CRARA's existing biomedical/statistical paths. This
module returns ``None`` whenever those contexts are detected.
"""
from __future__ import annotations

import math
import re
from typing import Any, Callable

from .results import MathResult, blocked_result

_SOURCE_URL = "https://github.com/majaliwamin/mathsdrill"
_SOURCE_COMMIT = "67e170f478be5383ad1fbdb2a0112121b2b1811d"

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

_EXCLUDED_CONTEXT = re.compile(
    r"\b(?:epidemiolog\w*|biostatistic\w*|clinical|patient|diagnos\w*|disease|outbreak|"
    r"prevalen\w*|inciden\w*|sensitiv\w*|specific\w*|predictive\s+value|likelihood\s+ratio|"
    r"odds\s+ratio|risk\s+ratio|relative\s+risk|hazard\s+ratio|survival|kaplan|cox|"
    r"\broc\b|\bauc\b|sample\s+size|statistical\s+power|hypothesis\s+test|p[-\s]?value|"
    r"confidence\s+interval|clinical\s+trial|cohort|case[-\s]control|mortality|morbidity|"
    r"treat\w*|medication|prescri\w*|symptom\w*)\b",
    re.I,
)

_SEQUENCE_CUE = re.compile(r"\b(?:sequence|progression)\b|\bnth\b|\bterm\s+number\b", re.I)
_ARITHMETIC_CUE = re.compile(r"arithmetic\s+(?:sequence|progression)|common\s+difference|\b[au]_?n\b|\bd\s*=\s*[-+]?\d", re.I)
_GEOMETRIC_CUE = re.compile(r"geometric\s+(?:sequence|progression)|common\s+ratio|\br\s*=\s*[-+]?\d", re.I)
_SUM_CUE = re.compile(r"\b(?:sum|total)\b.{0,40}\bterms?\b|\bS_?n\b", re.I | re.S)
_TRANSFORM_CUE = re.compile(r"\b(?:reflect|reflection|rotate|rotation|translate|translation|enlarge|enlargement)\b", re.I)
_MENSURATION_CUE = re.compile(
    r"\b(?:area|perimeter|circumference|surface\s+area|volume)\b.{0,60}"
    r"\b(?:rectangle|triangle|circle|trapezium|trapezoid|cylinder|cone|sphere|cuboid)\b|"
    r"\b(?:rectangle|triangle|circle|trapezium|trapezoid|cylinder|cone|sphere|cuboid)\b.{0,60}"
    r"\b(?:area|perimeter|circumference|surface\s+area|volume)\b",
    re.I | re.S,
)
_LOCUS_CUE = re.compile(r"\blocus\b|perpendicular\s+bisector|equidistant\s+from", re.I)
_BEARING_CUE = re.compile(r"\bbearing\b|\bnavigation\b", re.I)
_LINEAR_PROGRAM_CUE = re.compile(r"\blinear\s+program\w*\b|\bsubject\s+to\b|\bconstraints?\b", re.I)
_CIRCLE_GEOMETRY_CUE = re.compile(
    r"\bchord\b|\btangent\b|\barc\s+length\b|\bsector\b|\bangle\s+at\s+the\s+centre\b|"
    r"\bcyclic\s+quadrilateral\b|\bthales\b",
    re.I,
)
_SIMILARITY_CUE = re.compile(r"\bsimilar(?:ity|ities|(?:\s+(?:figures?|triangles?|shapes?)))\b|\bscale\s+factor\b", re.I)
_LINEAR_MODEL_CUE = re.compile(
    r"\b(?:fixed\s+cost|base\s+cost|call[-\s]?out|initial\s+(?:value|amount|cost)|starting\s+value|"
    r"depreciat\w*|appreciat\w*|growth|decay|rate\s+(?:of|per)|charge\s+per|cost\s+per)\b",
    re.I,
)
_GRAPH_READ_CUE = re.compile(
    r"\bread\s+(?:off|the\s+value)|equation\s+of\s+the\s+line|value\s+of\s+y\s+when|find\s+y\s+when",
    re.I,
)

SCHOOL_MATH_REASONS: dict[str, str] = {
    "arithmetic_sequence_term": "Arithmetic sequence rule: u_n = u_1 + (n - 1)d.",
    "arithmetic_sequence_sum": "Arithmetic series rule: S_n = n/2 [2u_1 + (n - 1)d].",
    "geometric_sequence_term": "Geometric sequence rule: u_n = u_1 r^(n - 1).",
    "geometric_sequence_sum": "Geometric series rule: S_n = u_1(1 - r^n)/(1 - r), with S_n = n u_1 when r = 1.",
    "geometric_transformation": "Apply the stated coordinate transformation rule to every coordinate.",
    "mensuration": "Use the standard perimeter, area or volume formula for the named shape.",
    "locus": "A point equidistant from two fixed points lies on their perpendicular bisector.",
    "bearing": "Bearings are measured clockwise from north; distance uses Pythagoras' theorem.",
    "linear_program": "A linear objective on a convex polygonal feasible region attains its optimum at a vertex.",
    "circle_geometry": "Apply the circle theorem or standard circle formula named by the construction.",
    "similarity": "Similar figures have proportional corresponding lengths, area ratio k² and volume ratio k³.",
    "linear_model": "A linear model has the form y = initial value ± rate × quantity.",
    "graph_reading": "A straight line has constant gradient; y = mx + c allows a value to be read at a given x.",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _finite(value: float | None) -> bool:
    return value is not None and math.isfinite(float(value))


def _round(value: float, digits: int = 12) -> float:
    rounded = round(float(value), digits)
    return 0.0 if abs(rounded) < 10 ** (-digits) else rounded


def _fmt(value: float) -> str:
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else f"{numeric:g}"


def _extract_number(text: str, labels: tuple[str, ...]) -> float | None:
    for label in labels:
        pattern = (
            r"(?<![\w.])" + re.escape(label) + r"\b\s*"
            r"(?:is|=|:|equals?|of)?\s*(" + _NUMBER + r")"
        )
        match = re.search(pattern, text, re.I)
        if match:
            try:
                value = float(match.group(1))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                return value
    return None


def _extract_int(text: str, labels: tuple[str, ...]) -> int | None:
    value = _extract_number(text, labels)
    if _finite(value) and float(value).is_integer() and value is not None and value >= 1:
        return int(value)
    return None


def _term_number(text: str) -> int | None:
    ordinal = re.search(r"\b(\d+)(?:st|nd|rd|th)\s+term\b", text, re.I)
    if ordinal:
        return int(ordinal.group(1))
    explicit = re.search(r"(?:\bn\b|\bterm\s+number\b|\bfirst\s+n\b)\s*(?:is|=|:|of)?\s*(\d+)", text, re.I)
    if explicit:
        return int(explicit.group(1))
    return None


def _sum_count(text: str) -> int | None:
    match = re.search(r"\b(?:sum|total)\s+of\s+(?:the\s+)?first\s+(\d+)\s+terms?\b", text, re.I)
    return int(match.group(1)) if match else None


def _explicit_terms(text: str) -> list[float]:
    match = re.search(
        r"\b(?:sequence|progression|terms?)\b\s*(?:is|are|:|=)?\s*"
        r"((?:" + _NUMBER + r"\s*,\s*){1,}" + _NUMBER + r")",
        text, re.I,
    )
    if not match:
        return []
    values = []
    for token in re.findall(_NUMBER, match.group(1)):
        value = float(token)
        if math.isfinite(value):
            values.append(value)
    return values


def _pair_numbers(raw: str) -> tuple[float, float] | None:
    values = re.findall(_NUMBER, str(raw))
    if len(values) < 2:
        return None
    try:
        first, second = float(values[0]), float(values[1])
    except (TypeError, ValueError):
        return None
    return (first, second) if math.isfinite(first) and math.isfinite(second) else None


def _point(text: str, label: str | None = None) -> tuple[float, float] | None:
    if label:
        pattern = (
            r"\b" + re.escape(label) + r"\b\s*(?:point)?\s*(?:is|=|:)?\s*"
            r"\(?\s*(" + _NUMBER + r")\s*,\s*(" + _NUMBER + r")\s*\)?"
        )
        match = re.search(pattern, text, re.I)
        return _pair_numbers(match.group(0)) if match else None
    match = re.search(r"\(\s*(" + _NUMBER + r")\s*,\s*(" + _NUMBER + r")\s*\)", text)
    return _pair_numbers(match.group(0)) if match else None


def _pair_after(text: str, keywords: tuple[str, ...]) -> tuple[float, float] | None:
    for keyword in keywords:
        pattern = (
            r"\b" + re.escape(keyword) + r"\b.{0,30}?"
            r"(\(?\s*" + _NUMBER + r"\s*,\s*" + _NUMBER + r"\s*\)?|"
            r"\[\s*" + _NUMBER + r"\s*,\s*" + _NUMBER + r"\s*\])"
        )
        match = re.search(pattern, text, re.I | re.S)
        if match:
            pair = _pair_numbers(match.group(1))
            if pair:
                return pair
    return None


def _sequence_handler(operation: str, reasons: list[str]) -> Callable[[str], MathResult | None]:
    def handler(text: str) -> MathResult | None:
        if not _SEQUENCE_CUE.search(text):
            return None
        arithmetic_match = _ARITHMETIC_CUE.search(text)
        geometric_match = _GEOMETRIC_CUE.search(text)
        if arithmetic_match is None and geometric_match is None:
            if _SUM_CUE.search(text) or re.search(r"\bnth\b|\bterm\s+number\b", text, re.I):
                return blocked_result(
                    "sequence",
                    "State whether the sequence is arithmetic (constant difference) or geometric (constant ratio).",
                    domain="mathematics",
                )
            return None
        arithmetic = arithmetic_match is not None
        geometric = geometric_match is not None
        if arithmetic and geometric:
            return blocked_result(
                "sequence",
                "The sequence type is ambiguous; state whether the common difference or common ratio is intended.",
                domain="mathematics",
            )
        wants_sum = bool(_SUM_CUE.search(text))
        if operation.endswith("_sum") and not wants_sum:
            return None
        if operation.endswith("_term") and wants_sum:
            return None
        if arithmetic != (operation.startswith("arithmetic")):
            return None
        if geometric != (operation.startswith("geometric")):
            return None

        terms = _explicit_terms(text)
        first = _extract_number(text, ("first term", "first number", "starting value", "u1", "a1"))
        step = (
            _extract_number(text, ("common difference", "difference"))
            if arithmetic else _extract_number(text, ("common ratio", "ratio"))
        )
        if arithmetic and step is None:
            step = _extract_number(text, ("d",))
        if geometric and step is None:
            step = _extract_number(text, ("r",))
        if len(terms) >= 2:
            if first is None:
                first = terms[0]
            if step is None:
                if arithmetic:
                    differences = [b - a for a, b in zip(terms, terms[1:])]
                    if differences and all(math.isclose(item, differences[0], rel_tol=1e-9, abs_tol=1e-9) for item in differences):
                        step = differences[0]
                elif terms[0] != 0:
                    ratios = [b / a for a, b in zip(terms, terms[1:]) if a != 0]
                    if ratios and all(math.isclose(item, ratios[0], rel_tol=1e-9, abs_tol=1e-9) for item in ratios):
                        step = ratios[0]

        n = _sum_count(text) if wants_sum else _term_number(text)
        if n is None:
            n = _extract_int(text, ("n", "term number", "number of terms"))
        if not all(_finite(item) for item in (first, step)) or n is None:
            missing = "the first term, the " + ("common difference" if arithmetic else "common ratio") + " and the term number"
            return blocked_result(
                operation,
                "Provide " + missing + " explicitly; this complement does not infer missing sequence parameters.",
                domain="mathematics",
            )
        assert first is not None and step is not None
        nth = _round(first + (n - 1) * step if arithmetic else first * (step ** (n - 1)))
        if arithmetic:
            total = _round(n * (2 * first + (n - 1) * step) / 2)
        elif math.isclose(step, 1.0, rel_tol=0.0, abs_tol=1e-12):
            total = _round(n * first)
        else:
            total = _round(first * (1 - step ** n) / (1 - step))
        parameter_name = "common_difference" if arithmetic else "common_ratio"
        latex = (
            {"nth": r"u_n=u_1+(n-1)d", "sum": r"S_n=\frac{n}{2}\left[2u_1+(n-1)d\right]"}
            if arithmetic else
            {"nth": r"u_n=u_1r^{n-1}", "sum": r"S_n=\frac{u_1(1-r^n)}{1-r}"}
        )
        return MathResult(
            operation=operation,
            domain="mathematics",
            method="MathsDrill school sequence complement",
            inputs={"first_term": first, parameter_name: step, "n": n},
            assumptions=["The sequence type and parameters were supplied or consistently shown by explicit terms."],
            steps=[
                reasons[0],
                f"Use u_1 = {first}, {parameter_name} = {step} and n = {n}.",
                f"The {n}{'th' if n % 10 != 1 or n % 100 == 11 else 'st'} term is {nth}.",
                f"The sum of the first {n} terms is {total}.",
            ],
            values={
                "first_term": first,
                parameter_name: step,
                "n": n,
                "nth_term": nth,
                "sum_first_n": total,
                "step_reasons": reasons,
                "source": _SOURCE_URL,
            },
            latex=latex,
            code=(
                "a, step, n = " + repr(first) + ", " + repr(step) + ", " + repr(n) + "\n"
                + ("nth = a + (n - 1) * step\n total = n * (2 * a + (n - 1) * step) / 2\n"
                   if arithmetic else
                   "nth = a * step ** (n - 1)\n"
                   "total = n * a if step == 1 else a * (1 - step ** n) / (1 - step)\n")
                + "print(nth, total)"
            ),
            interpretation=f"For this {('arithmetic' if arithmetic else 'geometric')} sequence, the {n}th term is {nth} and the first {n} terms sum to {total}.",
        )

    return handler


def _arithmetic_term(text: str) -> MathResult | None:
    return _sequence_handler(
        "arithmetic_sequence_term",
        [SCHOOL_MATH_REASONS["arithmetic_sequence_term"]],
    )(text)


def _arithmetic_sum(text: str) -> MathResult | None:
    return _sequence_handler(
        "arithmetic_sequence_sum",
        [SCHOOL_MATH_REASONS["arithmetic_sequence_sum"]],
    )(text)


def _geometric_term(text: str) -> MathResult | None:
    return _sequence_handler(
        "geometric_sequence_term",
        [SCHOOL_MATH_REASONS["geometric_sequence_term"]],
    )(text)


def _geometric_sum(text: str) -> MathResult | None:
    return _sequence_handler(
        "geometric_sequence_sum",
        [SCHOOL_MATH_REASONS["geometric_sequence_sum"]],
    )(text)


def _format_line_equation(slope: float, intercept: float) -> str:
    if math.isclose(slope, 0.0, abs_tol=1e-12):
        return f"y = {_round(intercept)}"
    sign = "-" if intercept < 0 else "+"
    return f"y = {_round(slope)}x {sign} {_round(abs(intercept))}"


def _transform(text: str) -> MathResult | None:
    if not _TRANSFORM_CUE.search(text):
        return None
    original = _point(text, "point") or _point(text, "P") or _point(text)
    if original is None:
        return blocked_result(
            "geometric_transformation",
            "Provide the point to transform, for example point P(3, -4).",
            domain="mathematics",
        )
    x, y = original
    reason = SCHOOL_MATH_REASONS["geometric_transformation"]
    transformation = ""
    image: tuple[float, float] | None = None
    latex = ""

    if re.search(r"\btranslat\w*\b", text, re.I):
        vector = _pair_after(text, ("vector", "by", "translation"))
        if vector is None:
            return blocked_result(
                "geometric_transformation",
                "Provide the translation vector, for example by vector [2, -3].",
                domain="mathematics",
            )
        h, k = vector
        image = (_round(x + h), _round(y + k))
        transformation = f"translation by ({h}, {k})"
        latex = r"(x,y)\mapsto(x+h,y+k)"
    elif re.search(r"\breflect\w*\b", text, re.I):
        if re.search(r"y\s*=\s*-\s*x", text, re.I):
            image = (_round(-y), _round(-x))
            transformation = "reflection in the line y = -x"
            latex = r"(x,y)\mapsto(-y,-x)"
        elif re.search(r"y\s*=\s*x", text, re.I):
            image = (_round(y), _round(x))
            transformation = "reflection in the line y = x"
            latex = r"(x,y)\mapsto(y,x)"
        elif re.search(r"\by[-\s]?axis\b", text, re.I):
            image = (_round(-x), _round(y))
            transformation = "reflection in the y-axis"
            latex = r"(x,y)\mapsto(-x,y)"
        elif re.search(r"\bx[-\s]?axis\b", text, re.I):
            image = (_round(x), _round(-y))
            transformation = "reflection in the x-axis"
            latex = r"(x,y)\mapsto(x,-y)"
        elif re.search(r"\borigin\b", text, re.I):
            image = (_round(-x), _round(-y))
            transformation = "reflection in the origin"
            latex = r"(x,y)\mapsto(-x,-y)"
        else:
            return blocked_result(
                "geometric_transformation",
                "State the mirror line or centre: x-axis, y-axis, origin, y = x or y = -x.",
                domain="mathematics",
            )
    elif re.search(r"\brotat\w*\b", text, re.I):
        angle = _extract_number(text, ("angle", "degrees", "θ", "theta"))
        if angle is None:
            degrees = re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:°|degrees?)\b", text, re.I)
            angle = float(degrees[0]) if degrees else None
        if angle is None:
            return blocked_result(
                "geometric_transformation",
                "Provide the rotation angle in degrees and the centre of rotation.",
                domain="mathematics",
            )
        if not re.search(r"\borigin\b|\(0\s*,\s*0\)", text, re.I):
            return blocked_result(
                "geometric_transformation",
                "Only rotations about the origin are supported by this complement; state the centre explicitly.",
                domain="mathematics",
            )
        anticlockwise = bool(re.search(r"\banti[-\s]?clock\w*\b|\bcounter[-\s]?clock\w*\b", text, re.I))
        clockwise = bool(re.search(r"\bclock\w*\b", text, re.I)) and not anticlockwise
        radians = math.radians(-abs(angle) if clockwise else abs(angle))
        cosine, sine = math.cos(radians), math.sin(radians)
        image = (_round(x * cosine - y * sine), _round(x * sine + y * cosine))
        direction = "clockwise" if clockwise else "anticlockwise"
        transformation = f"rotation of {angle}° {direction} about the origin"
        latex = r"\begin{pmatrix}x'\\y'\end{pmatrix}=\begin{pmatrix}\cos\theta&-\sin\theta\\\sin\theta&\cos\theta\end{pmatrix}\begin{pmatrix}x\\y\end{pmatrix}"
    elif re.search(r"\benlarg\w*\b", text, re.I):
        scale = _extract_number(text, ("scale factor", "factor", "k"))
        if scale is None:
            return blocked_result(
                "geometric_transformation",
                "Provide the enlargement scale factor and state that the centre is the origin.",
                domain="mathematics",
            )
        if not re.search(r"\borigin\b|\(0\s*,\s*0\)", text, re.I):
            return blocked_result(
                "geometric_transformation",
                "Only enlargements about the origin are supported by this complement; state the centre explicitly.",
                domain="mathematics",
            )
        image = (_round(scale * x), _round(scale * y))
        transformation = f"enlargement with scale factor {scale} about the origin"
        latex = r"(x,y)\mapsto(kx,ky)"
    else:
        return None
    assert image is not None
    return MathResult(
        operation="geometric_transformation",
        domain="mathematics",
        method="MathsDrill coordinate-transformation complement",
        inputs={"point": {"x": x, "y": y}, "transformation": transformation},
        assumptions=["Coordinates use the standard Cartesian x-y convention."],
        steps=[
            reason,
            f"Start with ({x}, {y}).",
            f"Apply the {transformation}.",
            f"The image is ({image[0]}, {image[1]}).",
        ],
        values={
            "original": {"x": x, "y": y},
            "image": {"x": image[0], "y": image[1]},
            "transformation": transformation,
            "step_reasons": [reason],
            "source": _SOURCE_URL,
        },
        latex={"mapping": latex},
        interpretation=f"The point ({x}, {y}) maps to ({image[0]}, {image[1]}) under a {transformation}.",
    )


def _mensuration(text: str) -> MathResult | None:
    if not _MENSURATION_CUE.search(text):
        return None
    shape_match = re.search(r"\b(rectangle|triangle|circle|trapezium|trapezoid|cylinder|cone|sphere|cuboid)\b", text, re.I)
    if not shape_match:
        return None
    shape = shape_match.group(1).lower()
    if shape == "trapezoid":
        shape = "trapezium"
    measure = "surface_area" if re.search(r"surface\s+area", text, re.I) else (
        "circumference" if re.search(r"circumference", text, re.I) else (
            "area" if re.search(r"\barea\b", text, re.I) else (
                "volume" if re.search(r"\bvolume\b", text, re.I) else "perimeter"
            )
        )
    )
    labels = {
        "length": ("length", "long side", "longer side"),
        "width": ("width", "breadth", "short side", "shorter side"),
        "height": ("height", "depth"),
        "base": ("base",),
        "radius": ("radius", "r"),
        "diameter": ("diameter",),
        "parallel_a": ("first parallel side", "parallel side a", "upper parallel side"),
        "parallel_b": ("second parallel side", "parallel side b", "lower parallel side"),
        "side_a": ("side a", "first side", "side 1"),
        "side_b": ("side b", "second side", "side 2"),
        "side_c": ("side c", "third side", "side 3"),
        "slant": ("slant height", "slant", "l"),
    }
    dims = {key: _extract_number(text, aliases) for key, aliases in labels.items()}
    if dims.get("radius") is None and dims.get("diameter") is not None:
        dims["radius"] = dims["diameter"] / 2

    value: float | None = None
    exact = ""
    latex = ""
    used: dict[str, float] = {}
    if shape == "rectangle" and measure in ("area", "perimeter"):
        if not all(_finite(dims.get(key)) for key in ("length", "width")):
            return blocked_result("mensuration", "A rectangle needs its length and width.", domain="mathematics")
        length, width = float(dims["length"]), float(dims["width"])
        used = {"length": length, "width": width}
        value = length * width if measure == "area" else 2 * (length + width)
        latex = r"A=lw" if measure == "area" else r"P=2(l+w)"
    elif shape == "triangle" and measure in ("area", "perimeter"):
        needed = ("base", "height") if measure == "area" else ("side_a", "side_b", "side_c")
        if not all(_finite(dims.get(key)) for key in needed):
            return blocked_result(
                "mensuration",
                "A triangle needs its base and perpendicular height for area, or all three sides for perimeter.",
                domain="mathematics",
            )
        if measure == "area":
            base, height = float(dims["base"]), float(dims["height"])
            used = {"base": base, "height": height}
            value = base * height / 2
            latex = r"A=\frac{1}{2}bh"
        else:
            sides = [float(dims[key]) for key in needed]
            used = {key: float(dims[key]) for key in needed}
            if any(a + b <= c for a, b, c in [(sides[0], sides[1], sides[2]), (sides[0], sides[2], sides[1]), (sides[1], sides[2], sides[0])]):
                return blocked_result("mensuration", "The supplied side lengths do not form a triangle.", domain="mathematics")
            value = sum(sides)
            latex = r"P=a+b+c"
    elif shape == "circle" and measure in ("area", "circumference"):
        if not _finite(dims.get("radius")):
            return blocked_result("mensuration", "A circle needs its radius or diameter.", domain="mathematics")
        radius = float(dims["radius"])
        used = {"radius": radius}
        value = math.pi * radius ** 2 if measure == "area" else 2 * math.pi * radius
        exact = f"{_fmt(radius ** 2)}π" if measure == "area" else f"{_fmt(2 * radius)}π"
        latex = r"A=\pi r^2" if measure == "area" else r"C=2\pi r"
    elif shape == "trapezium" and measure == "area":
        if not all(_finite(dims.get(key)) for key in ("parallel_a", "parallel_b", "height")):
            return blocked_result("mensuration", "A trapezium needs both parallel sides and the perpendicular height.", domain="mathematics")
        first, second, height = (float(dims[key]) for key in ("parallel_a", "parallel_b", "height"))
        used = {"parallel_side_a": first, "parallel_side_b": second, "height": height}
        value = (first + second) * height / 2
        latex = r"A=\frac{1}{2}(a+b)h"
    elif shape == "cylinder" and measure in ("volume", "surface_area"):
        if not all(_finite(dims.get(key)) for key in ("radius", "height")):
            return blocked_result("mensuration", "A cylinder needs its radius and height.", domain="mathematics")
        radius, height = float(dims["radius"]), float(dims["height"])
        used = {"radius": radius, "height": height}
        if measure == "volume":
            value = math.pi * radius ** 2 * height
            exact = f"{_fmt(radius ** 2 * height)}π"
            latex = r"V=\pi r^2h"
        else:
            value = 2 * math.pi * radius * (height + radius)
            exact = f"{_fmt(2 * radius * (height + radius))}π"
            latex = r"S=2\pi r(h+r)"
    elif shape == "cone" and measure in ("volume", "surface_area"):
        if not all(_finite(dims.get(key)) for key in ("radius", "height")):
            return blocked_result("mensuration", "A cone needs its radius and perpendicular height.", domain="mathematics")
        radius, height = float(dims["radius"]), float(dims["height"])
        used = {"radius": radius, "height": height}
        if measure == "volume":
            value = math.pi * radius ** 2 * height / 3
            exact = f"({_fmt(radius ** 2 * height)}/3)π"
            latex = r"V=\frac{1}{3}\pi r^2h"
        else:
            slant = float(dims["slant"]) if _finite(dims.get("slant")) else math.hypot(radius, height)
            used["slant_height"] = slant
            value = math.pi * radius * (slant + radius)
            exact = f"{_fmt(radius * (slant + radius))}π"
            latex = r"S=\pi r(l+r)"
    elif shape == "sphere" and measure in ("volume", "surface_area"):
        if not _finite(dims.get("radius")):
            return blocked_result("mensuration", "A sphere needs its radius.", domain="mathematics")
        radius = float(dims["radius"])
        used = {"radius": radius}
        if measure == "volume":
            value = 4 * math.pi * radius ** 3 / 3
            exact = f"({_fmt(4 * radius ** 3)}/3)π"
            latex = r"V=\frac{4}{3}\pi r^3"
        else:
            value = 4 * math.pi * radius ** 2
            exact = f"{_fmt(4 * radius ** 2)}π"
            latex = r"S=4\pi r^2"
    elif shape == "cuboid" and measure in ("volume", "surface_area"):
        if not all(_finite(dims.get(key)) for key in ("length", "width", "height")):
            return blocked_result("mensuration", "A cuboid needs its length, width and height.", domain="mathematics")
        length, width, height = (float(dims[key]) for key in ("length", "width", "height"))
        used = {"length": length, "width": width, "height": height}
        if measure == "volume":
            value = length * width * height
            latex = r"V=lwh"
        else:
            value = 2 * (length * width + length * height + width * height)
            latex = r"S=2(lw+lh+wh)"
    else:
        return blocked_result(
            "mensuration",
            f"This complement does not support {measure} for a {shape}. State a supported measure explicitly.",
            domain="mathematics",
        )
    assert value is not None
    value = _round(value)
    reason = SCHOOL_MATH_REASONS["mensuration"]
    unit_note = {
        "area": "square units", "surface_area": "square units", "circumference": "units",
        "perimeter": "units", "volume": "cubic units",
    }[measure]
    return MathResult(
        operation="mensuration",
        domain="mathematics",
        method="MathsDrill mensuration complement",
        inputs={"shape": shape, "measure": measure, "dimensions": used},
        assumptions=["Dimensions are positive and use one consistent unit system."],
        steps=[
            reason,
            f"Shape: {shape}; required measure: {measure.replace('_', ' ')}.",
            f"Substitute the supplied dimensions: {used}.",
            f"The result is {value} ({unit_note})" + (f", exactly {exact}." if exact else "."),
        ],
        values={
            "shape": shape,
            "measure": measure,
            "value": value,
            "exact_form": exact,
            "dimensions": used,
            "step_reasons": [reason],
            "source": _SOURCE_URL,
        },
        latex={"formula": latex},
        interpretation=f"The {measure.replace('_', ' ')} of the {shape} is {value} {unit_note}.",
    )


def _locus(text: str) -> MathResult | None:
    if not _LOCUS_CUE.search(text):
        return None
    first = _point(text, "A") or _point(text, "first")
    second = _point(text, "B") or _point(text, "second")
    if first is None or second is None:
        pairs = re.findall(r"\(\s*(" + _NUMBER + r")\s*,\s*(" + _NUMBER + r")\s*\)", text)
        parsed = [pair for item in pairs if (pair := _pair_numbers(f"({item[0]}, {item[1]})"))]
        if len(parsed) >= 2:
            first, second = parsed[0], parsed[1]
    if first is None or second is None:
        return blocked_result(
            "locus",
            "Provide two fixed points, for example A(1, 2) and B(5, 6).",
            domain="mathematics",
        )
    x1, y1 = first
    x2, y2 = second
    if math.isclose(x1, x2, abs_tol=1e-12) and math.isclose(y1, y2, abs_tol=1e-12):
        return blocked_result("locus", "The two fixed points must be distinct.", domain="mathematics")
    mid_x, mid_y = _round((x1 + x2) / 2), _round((y1 + y2) / 2)
    dx, dy = x2 - x1, y2 - y1
    if math.isclose(dx, 0.0, abs_tol=1e-12):
        equation = f"y = {mid_y}"
        perpendicular_slope = 0.0
    elif math.isclose(dy, 0.0, abs_tol=1e-12):
        equation = f"x = {mid_x}"
        perpendicular_slope = None
    else:
        perpendicular_slope = _round(-dx / dy)
        equation = _format_line_equation(perpendicular_slope, mid_y - perpendicular_slope * mid_x)
    reason = SCHOOL_MATH_REASONS["locus"]
    return MathResult(
        operation="locus",
        domain="mathematics",
        method="MathsDrill perpendicular-bisector complement",
        inputs={"point_a": {"x": x1, "y": y1}, "point_b": {"x": x2, "y": y2}},
        assumptions=["A locus is the set of all points satisfying the stated equidistance condition."],
        steps=[
            reason,
            f"Midpoint of A({x1}, {y1}) and B({x2}, {y2}) is ({mid_x}, {mid_y}).",
            f"Gradient of AB is {_round(dy / dx) if not math.isclose(dx, 0.0, abs_tol=1e-12) else 'undefined'}.",
            f"The perpendicular bisector is {equation}.",
        ],
        values={
            "midpoint": {"x": mid_x, "y": mid_y},
            "equation": equation,
            "perpendicular_slope": perpendicular_slope,
            "step_reasons": [reason],
            "source": _SOURCE_URL,
        },
        latex={"condition": r"(x-x_1)^2+(y-y_1)^2=(x-x_2)^2+(y-y_2)^2"},
        interpretation=f"The locus of points equidistant from A and B is the perpendicular bisector {equation}.",
    )


def _bearing(text: str) -> MathResult | None:
    if not _BEARING_CUE.search(text):
        return None
    start = _point(text, "from") or _point(text, "A") or _point(text, "start")
    end = _point(text, "to") or _point(text, "B") or _point(text, "end")
    if start is None or end is None:
        pairs = re.findall(r"\(\s*(" + _NUMBER + r")\s*,\s*(" + _NUMBER + r")\s*\)", text)
        parsed = [pair for item in pairs if (pair := _pair_numbers(f"({item[0]}, {item[1]})"))]
        if len(parsed) >= 2:
            start, end = parsed[0], parsed[1]
    if start is None or end is None:
        return blocked_result(
            "bearing",
            "Provide the start and destination as Cartesian points, for example from (0, 0) to (3, 4).",
            domain="mathematics",
        )
    delta_east, delta_north = end[0] - start[0], end[1] - start[1]
    distance = _round(math.hypot(delta_east, delta_north))
    angle = (math.degrees(math.atan2(delta_east, delta_north)) + 360) % 360
    bearing = _round(angle)
    reason = SCHOOL_MATH_REASONS["bearing"]
    return MathResult(
        operation="bearing",
        domain="mathematics",
        method="MathsDrill navigation complement",
        inputs={"start": {"x": start[0], "y": start[1]}, "destination": {"x": end[0], "y": end[1]}},
        assumptions=["The first coordinate is easting and the second coordinate is northing; bearings are measured clockwise from north."],
        steps=[
            reason,
            f"Change in easting = {_round(delta_east)}; change in northing = {_round(delta_north)}.",
            f"Distance = sqrt(({_round(delta_east)})² + ({_round(delta_north)})²) = {distance}.",
            f"Bearing = atan2(Δeasting, Δnorthing) = {bearing}°.",
        ],
        values={
            "distance": distance,
            "bearing_degrees": bearing,
            "delta_east": _round(delta_east),
            "delta_north": _round(delta_north),
            "step_reasons": [reason],
            "source": _SOURCE_URL,
        },
        latex={"bearing": r"\theta=\operatorname{atan2}(\Delta E,\Delta N)\pmod{360^\circ}"},
        interpretation=f"The destination is {distance} units from the start on a true bearing of {bearing:06.1f}°.",
    )


class _LinearExpression:
    __slots__ = ("coefficients", "constant")

    def __init__(self, coefficients: dict[str, float], constant: float):
        self.coefficients = coefficients
        self.constant = constant


def _linear_expression(raw: str) -> _LinearExpression:
    expression = re.sub(r"\s+", "", str(raw or "")).replace("−", "-")
    if not expression:
        raise ValueError("empty linear expression")
    coefficients = {"x": 0.0, "y": 0.0}
    constant = 0.0
    position = 0
    while position < len(expression):
        match = re.match(r"([+-]?)(?:\d+(?:\.\d*)?|\.\d+)?([xy])?", expression[position:])
        if not match:
            raise ValueError(f"unsupported term near {expression[position:position + 12]!r}")
        sign, variable = match.group(1), match.group(2)
        number_text = match.group(0)[len(sign):]
        number_text = number_text[:-1] if variable and number_text.endswith(variable) else number_text
        if not variable and not number_text:
            raise ValueError("empty term")
        magnitude = float(number_text) if number_text else 1.0
        signed = -magnitude if sign == "-" else magnitude
        if variable:
            coefficients[variable] += signed
        else:
            constant += signed
        position += len(match.group(0))
    return _LinearExpression(coefficients, constant)


def _constraints(text: str) -> tuple[list[tuple[list[float], float]], list[tuple[list[float], float]], list[str]]:
    parts = [part.strip(" .;,") for part in re.split(r"[,;]|\band\b", text, flags=re.I) if part.strip(" .;,")]
    upper: list[tuple[list[float], float]] = []
    equal: list[tuple[list[float], float]] = []
    labels: list[str] = []
    for part in parts:
        match = re.match(r"(.+?)\s*(<=|>=|≤|≥|=)\s*(.+)", part)
        if not match:
            raise ValueError(f"unsupported constraint {part!r}")
        left = _linear_expression(match.group(1))
        right = _linear_expression(match.group(3))
        coefficients = [left.coefficients["x"] - right.coefficients["x"], left.coefficients["y"] - right.coefficients["y"]]
        bound = right.constant - left.constant
        operator = match.group(2)
        if operator in (">=", "≥"):
            coefficients, bound = [-item for item in coefficients], -bound
        labels.append(part)
        if operator == "=":
            equal.append((coefficients, bound))
        else:
            upper.append((coefficients, bound))
    return upper, equal, labels


def _linear_program(text: str) -> MathResult | None:
    if not _LINEAR_PROGRAM_CUE.search(text):
        return None
    sense_match = re.search(r"\b(maximi[sz]e|minimi[sz]e)\b", text, re.I)
    if not sense_match:
        return None
    sense = "maximum" if sense_match.group(1).lower().startswith("max") else "minimum"
    objective_match = re.search(
        r"\b(?:maximi[sz]e|minimi[sz]e)\s+(.+?)(?=\s+subject\s+to\b|\s+such\s+that\b|\s+with\s+constraints\b|$)",
        text, re.I | re.S,
    )
    constraint_match = re.search(
        r"\b(?:subject\s+to|such\s+that|with\s+constraints)\b\s*(.+)", text, re.I | re.S
    )
    if not objective_match or not constraint_match:
        return blocked_result(
            "linear_program",
            "State a linear objective and its constraints, for example maximise 3x + 2y subject to x + y <= 4, x <= 3, y <= 2.",
            domain="mathematics",
        )
    try:
        objective = _linear_expression(objective_match.group(1))
        upper, equal, constraint_labels = _constraints(constraint_match.group(1))
    except ValueError as exc:
        return blocked_result("linear_program", f"The linear program could not be parsed safely: {exc}", domain="mathematics")
    if not upper and not equal:
        return blocked_result("linear_program", "Provide at least one linear constraint.", domain="mathematics")
    try:
        from scipy.optimize import linprog
    except ImportError:
        return blocked_result("linear_program", "SciPy is required for linear programming.", domain="mathematics")

    objective_vector = [objective.coefficients["x"], objective.coefficients["y"]]
    solver_objective = [-item for item in objective_vector] if sense == "maximum" else objective_vector
    result = linprog(
        solver_objective,
        A_ub=[row for row, _ in upper] or None,
        b_ub=[bound for _, bound in upper] or None,
        A_eq=[row for row, _ in equal] or None,
        b_eq=[bound for _, bound in equal] or None,
        bounds=(0, None),
        method="highs",
    )
    if not result.success:
        return blocked_result("linear_program", f"No bounded optimum was found: {result.message}", domain="mathematics")
    x_value, y_value = (_round(item, 9) for item in result.x)
    optimal_value = _round(-result.fun if sense == "maximum" else result.fun, 9)
    feasible = all(a * x_value + b * y_value <= bound + 1e-8 for (a, b), bound in upper) and all(
        math.isclose(a * x_value + b * y_value, bound, abs_tol=1e-8) for (a, b), bound in equal
    )
    if not feasible:
        return blocked_result("linear_program", "The solver result did not satisfy the stated constraints.", domain="mathematics")
    reason = SCHOOL_MATH_REASONS["linear_program"]
    return MathResult(
        operation="linear_program",
        domain="mathematics",
        method="MathsDrill linear-programming complement",
        inputs={
            "objective": {"x": objective.coefficients["x"], "y": objective.coefficients["y"], "sense": sense},
            "constraints": constraint_labels,
        },
        assumptions=["Both decision variables are non-negative and all relationships are linear."],
        steps=[
            reason,
            f"Objective: {sense} {objective.coefficients['x']}x + {objective.coefficients['y']}y.",
            f"Constraints: {'; '.join(constraint_labels)}; x >= 0, y >= 0.",
            f"The optimum occurs at x = {x_value}, y = {y_value}.",
            f"The optimum value is {optimal_value}.",
        ],
        values={
            "optimal_point": {"x": x_value, "y": y_value},
            "optimal_value": optimal_value,
            "sense": sense,
            "constraints": constraint_labels,
            "step_reasons": [reason],
            "source": _SOURCE_URL,
        },
        latex={"objective": r"z=c_1x+c_2y", "optimum": r"(x^*,y^*)=\arg\max/\min\;z"},
        interpretation=f"The {sense} value is {optimal_value}, attained at x = {x_value} and y = {y_value}.",
    )


def _angle_value(text: str) -> float | None:
    value = _extract_number(text, ("angle", "theta", "θ"))
    if value is not None:
        return value
    match = re.search(r"\b(" + _NUMBER + r")\s*(?:°|degrees?)\b", text, re.I)
    return float(match.group(1)) if match else None


def _circle_geometry(text: str) -> MathResult | None:
    if not _CIRCLE_GEOMETRY_CUE.search(text):
        return None
    if re.search(r"\b(?:curve|function|parabola|graph|derivative|differentiate)\b", text, re.I):
        return None
    radius = _extract_number(text, ("radius", "r"))
    distance = _extract_number(text, ("distance from centre", "distance from the centre", "centre distance", "d"))
    chord = _extract_number(text, ("chord length", "chord"))
    angle = _angle_value(text)
    reason = SCHOOL_MATH_REASONS["circle_geometry"]
    quantity = ""
    value: float | None = None
    latex = ""

    if re.search(r"\barc\b", text, re.I):
        if not _finite(radius) or not _finite(angle):
            return blocked_result("circle_geometry", "Arc length needs the radius and the angle at the centre.", domain="mathematics")
        assert radius is not None and angle is not None
        value = 2 * math.pi * radius * angle / 360
        quantity = "arc length"
        latex = r"l=\frac{\theta}{360^\circ}\,2\pi r"
        exact = f"({_fmt(angle * 2 * radius)}/360)π"
    elif re.search(r"\bsector\b", text, re.I):
        if not _finite(radius) or not _finite(angle):
            return blocked_result("circle_geometry", "Sector area needs the radius and the angle at the centre.", domain="mathematics")
        assert radius is not None and angle is not None
        value = math.pi * radius ** 2 * angle / 360
        quantity = "sector area"
        latex = r"A=\frac{\theta}{360^\circ}\,\pi r^2"
        exact = f"({_fmt(angle * radius ** 2)}/360)π"
    elif re.search(r"\btangent\b", text, re.I):
        if not _finite(radius) or not _finite(distance):
            return blocked_result("circle_geometry", "Tangent length needs the radius and the external point's distance from the centre.", domain="mathematics")
        assert radius is not None and distance is not None
        if distance <= radius:
            return blocked_result("circle_geometry", "The external point must be farther from the centre than the radius.", domain="mathematics")
        value = math.sqrt(distance ** 2 - radius ** 2)
        quantity = "tangent length"
        latex = r"t=\sqrt{d^2-r^2}"
        exact = ""
    elif re.search(r"\bchord\b", text, re.I):
        wants_radius = bool(re.search(r"\b(?:find|calculate|what\s+is).{0,40}\bradius\b", text, re.I | re.S))
        if wants_radius and _finite(chord) and _finite(distance):
            assert chord is not None and distance is not None
            value = math.sqrt(distance ** 2 + (chord / 2) ** 2)
            quantity = "radius from chord and centre distance"
            latex = r"r=\sqrt{d^2+\left(\frac{c}{2}\right)^2}"
            exact = ""
        elif _finite(radius) and _finite(distance):
            assert radius is not None and distance is not None
            if radius <= distance:
                return blocked_result("circle_geometry", "The centre-to-chord distance must be smaller than the radius.", domain="mathematics")
            value = 2 * math.sqrt(radius ** 2 - distance ** 2)
            quantity = "chord length"
            latex = r"c=2\sqrt{r^2-d^2}"
            exact = ""
        else:
            return blocked_result(
                "circle_geometry",
                "A chord calculation needs the radius and centre-to-chord distance, or the chord length and centre distance if finding the radius.",
                domain="mathematics",
            )
    else:
        return None
    assert value is not None
    value = _round(value)
    return MathResult(
        operation="circle_geometry",
        domain="mathematics",
        method="MathsDrill circle-geometry complement",
        inputs={"radius": radius, "distance_from_centre": distance, "chord": chord, "angle_degrees": angle},
        assumptions=["Circle dimensions use one consistent unit system and angles are in degrees."],
        steps=[reason, f"Required quantity: {quantity}.", f"Apply {latex.strip('$')}.", f"The result is {value}" + (f", exactly {exact}." if exact else ".")],
        values={
            "value": value,
            "quantity": quantity,
            "exact_form": exact,
            "step_reasons": [reason],
            "source": _SOURCE_URL,
        },
        latex={"formula": latex},
        interpretation=f"The {quantity} is {value} units.",
    )


def _correspondence_pair(text: str) -> tuple[float, float] | None:
    match = re.search(
        r"(?:correspond\w*|sides?|lengths?)\D{0,30}?(" + _NUMBER + r")\s*(?:and|to|,|/|:)\s*(" + _NUMBER + r")",
        text, re.I | re.S,
    )
    if not match:
        return None
    first, second = float(match.group(1)), float(match.group(2))
    return (first, second) if math.isfinite(first) and math.isfinite(second) and first > 0 else None


def _similarity(text: str) -> MathResult | None:
    if not _SIMILARITY_CUE.search(text):
        return None
    scale = _extract_number(text, ("scale factor", "factor", "k"))
    length = _extract_number(text, ("corresponding length", "known length", "given length", "side length", "length", "side"))
    pair = _correspondence_pair(text)
    if scale is None and pair:
        scale = pair[1] / pair[0]
    if re.search(r"\barea\b", text, re.I):
        measure, result = "area_ratio", scale ** 2 if _finite(scale) and scale is not None else None
    elif re.search(r"\bvolume\b", text, re.I):
        measure, result = "volume_ratio", scale ** 3 if _finite(scale) and scale is not None else None
    elif re.search(r"\b(?:length|side)\b", text, re.I):
        measure = "length"
        result = scale * length if _finite(scale) and _finite(length) and scale is not None and length is not None else None
    else:
        measure, result = "scale_factor", scale
    if not _finite(scale) or not _finite(result) or scale is None or result is None:
        return blocked_result(
            "similarity",
            "Provide the scale factor and, for a missing length, the corresponding known length.",
            domain="mathematics",
        )
    reason = SCHOOL_MATH_REASONS["similarity"]
    return MathResult(
        operation="similarity",
        domain="mathematics",
        method="MathsDrill similarity complement",
        inputs={"scale_factor": _round(scale), "known_length": length, "measure": measure},
        assumptions=["The figures are genuinely similar and corresponding parts have been correctly matched."],
        steps=[
            reason,
            f"Linear scale factor k = {_round(scale)}.",
            f"Required measure: {measure}.",
            f"The result is {_round(result)}.",
        ],
        values={
            "scale_factor": _round(scale),
            "result": _round(result),
            "measure": measure,
            "step_reasons": [reason],
            "source": _SOURCE_URL,
        },
        latex={"ratios": r"l_2=kl_1,\quad A_2=k^2A_1,\quad V_2=k^3V_1"},
        interpretation=f"The {measure.replace('_', ' ')} for these similar figures is {_round(result)}.",
    )


def _quantity_value(text: str) -> float | None:
    match = re.search(
        r"\b(?:for|after|over|in)\s+(" + _NUMBER + r")\s*"
        r"(?:hours?|years?|days?|weeks?|months?|units?|items?|questions?)\b",
        text, re.I,
    )
    if match:
        return float(match.group(1))
    return _extract_number(text, ("quantity", "q", "number of units", "number of items"))


def _rate_value(text: str) -> float | None:
    value = _extract_number(text, ("rate", "charge per", "cost per", "rate per"))
    if value is not None:
        return value
    match = re.search(r"\b(?:by|at|of|plus|add)\s+(" + _NUMBER + r")\s*(?:per|each|a\b)", text, re.I)
    return float(match.group(1)) if match else None


def _linear_model(text: str) -> MathResult | None:
    if not _LINEAR_MODEL_CUE.search(text):
        return None
    initial = _extract_number(text, ("fixed cost", "base cost", "call-out", "callout", "initial value", "initial amount", "initial cost", "starting value", "fixed"))
    rate = _rate_value(text)
    quantity = _quantity_value(text)
    decay = bool(re.search(r"\b(?:decay|depreciat\w*|decrease|fall|withdraw)\w*\b", text, re.I))
    growth = bool(re.search(r"\b(?:grow\w*|increas\w*|appreciat\w*|rise|plus|add)\b", text, re.I))
    if not decay and not growth:
        growth = bool(re.search(r"\b(?:charge|cost|rate)\b", text, re.I))
    if not all(_finite(item) for item in (initial, rate, quantity)) or initial is None or rate is None or quantity is None:
        return blocked_result(
            "linear_model",
            "Provide the initial/fixed value, the constant rate, and the quantity or time explicitly.",
            domain="mathematics",
        )
    value = _round(initial - rate * quantity if decay else initial + rate * quantity)
    reason = SCHOOL_MATH_REASONS["linear_model"]
    model = f"y = {initial} {'−' if decay else '+'} {rate}q"
    return MathResult(
        operation="linear_model",
        domain="mathematics",
        method="MathsDrill linear-modelling complement",
        inputs={"initial_value": initial, "rate": rate, "quantity": quantity, "direction": "decrease" if decay else "increase"},
        assumptions=["The rate is constant and applies uniformly to the stated quantity."],
        steps=[reason, f"Form the model {model}.", f"Substitute q = {quantity}.", f"The modelled value is {value}."],
        values={
            "value": value,
            "initial_value": initial,
            "rate": rate,
            "quantity": quantity,
            "model": model,
            "step_reasons": [reason],
            "source": _SOURCE_URL,
        },
        latex={"model": r"y=y_0\pm rq"},
        interpretation=f"Using {model}, the value when q = {quantity} is {value}.",
    )


def _graph_reading(text: str) -> MathResult | None:
    if not _GRAPH_READ_CUE.search(text):
        return None
    matches = re.findall(r"\(\s*(" + _NUMBER + r")\s*,\s*(" + _NUMBER + r")\s*\)", text)
    points = [pair for item in matches if (pair := _pair_numbers(f"({item[0]}, {item[1]})"))]
    if len(points) < 2:
        return blocked_result(
            "graph_reading",
            "Provide two points on the line, for example (1, 3) and (4, 9).",
            domain="mathematics",
        )
    (x1, y1), (x2, y2) = points[0], points[1]
    if math.isclose(x1, x2, abs_tol=1e-12):
        return MathResult(
            operation="graph_reading",
            domain="mathematics",
            method="MathsDrill graph-reading complement",
            inputs={"point_1": {"x": x1, "y": y1}, "point_2": {"x": x2, "y": y2}},
            assumptions=["The graph uses Cartesian coordinates."],
            steps=[SCHOOL_MATH_REASONS["graph_reading"], f"Both points have x = {_round(x1)}.", "The line is vertical."],
            values={
                "gradient": None,
                "y_intercept": None,
                "equation": f"x = {_round(x1)}",
                "step_reasons": [SCHOOL_MATH_REASONS["graph_reading"]],
                "source": _SOURCE_URL,
            },
            latex={"line": f"x={_round(x1)}"},
            interpretation=f"The vertical line through the supplied points is x = {_round(x1)}.",
        )
    gradient = _round((y2 - y1) / (x2 - x1))
    intercept = _round(y1 - gradient * x1)
    target_match = re.search(
        r"\b(?:x\s*=\s*|when\s+x\s*=\s*|at\s+x\s*=\s*|value\s+of\s+y\s+when\s+x\s*=\s*)(" + _NUMBER + r")",
        text, re.I,
    )
    target = float(target_match.group(1)) if target_match else _extract_number(text, ("x", "x-value"))
    value = _round(gradient * target + intercept) if _finite(target) and target is not None else None
    reason = SCHOOL_MATH_REASONS["graph_reading"]
    return MathResult(
        operation="graph_reading",
        domain="mathematics",
        method="MathsDrill graph-reading complement",
        inputs={"point_1": {"x": x1, "y": y1}, "point_2": {"x": x2, "y": y2}, "x": target},
        assumptions=["The graph is a straight line and coordinates are exact."],
        steps=[
            reason,
            f"Gradient m = ({y2} − {y1})/({x2} − {x1}) = {gradient}.",
            f"Intercept c = {intercept}, so y = {gradient}x + {intercept}.",
            (f"At x = {target}, y = {value}." if value is not None else "No x-value was supplied for a read-off."),
        ],
        values={
            "gradient": gradient,
            "y_intercept": intercept,
            "value_at_x": value,
            "equation": _format_line_equation(gradient, intercept),
            "step_reasons": [reason],
            "source": _SOURCE_URL,
        },
        latex={"line": f"y={gradient}x+{intercept}"},
        interpretation=(
            f"The line is {_format_line_equation(gradient, intercept)}"
            + (f", and at x = {target} the value is {value}." if value is not None else ".")
        ),
    )


_HANDLERS: tuple[Callable[[str], MathResult | None], ...] = (
    _linear_program,
    _arithmetic_sum,
    _geometric_sum,
    _arithmetic_term,
    _geometric_term,
    _transform,
    _similarity,
    _circle_geometry,
    _mensuration,
    _graph_reading,
    _linear_model,
    _locus,
    _bearing,
)


def solve(message: str, context: str = "") -> MathResult | None:
    """Return a deterministic school-math result, or ``None`` to defer to CRARA.

    ``context`` is treated as untrusted source data. Parsers here require
    explicit labels or point notation, so unrelated narrative numbers are not
    promoted into a computation.
    """
    message_text = _clean(message)
    context_text = _clean(context)
    if context_text and context_text != message_text and message_text not in context_text:
        text = _clean(f"{message_text} {context_text}")
    else:
        text = message_text
    if not text or _EXCLUDED_CONTEXT.search(text):
        return None
    for handler in _HANDLERS:
        try:
            result = handler(text)
        except Exception as exc:  # defensively never break the main CRARA path
            return blocked_result(
                "school_mathematics",
                f"The school-math complement could not parse this request safely: {exc}",
                domain="mathematics",
            )
        if result is not None:
            return result
    return None


def reasons() -> dict[str, str]:
    """Expose the curated MathsDrill-style step justifications for this subset."""
    return dict(SCHOOL_MATH_REASONS)
