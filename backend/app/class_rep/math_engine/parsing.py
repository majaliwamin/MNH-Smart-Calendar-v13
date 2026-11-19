"""Safe extraction of numbers, datasets, expressions and method choices."""
from __future__ import annotations

import re
from typing import Any

_NUMBER = r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?%?"
_NUMBER_RE = re.compile(_NUMBER)

_DATA_LABELS = (
    "values", "data", "observations", "numbers", "scores", "hb", "haemoglobin",
    "hemoglobin", "weights", "heights", "ages", "sample", "dataset", "x",
)

_QUARTILE_ALIASES = {
    "linear": "linear",
    "numpy": "linear",
    "r7": "linear",
    "type7": "linear",
    "inclusive": "linear",
    "excel_inc": "linear",
    "median_of_halves": "median_halves_exclusive",
    "median-halves": "median_halves_exclusive",
    "tukey": "median_halves_exclusive",
    "exclusive_halves": "median_halves_exclusive",
    "moore": "median_halves_inclusive",
    "median_of_halves_inclusive": "median_halves_inclusive",
    "excel_exc": "exclusive",
    "nearest": "nearest_rank",
    "nearest_rank": "nearest_rank",
}


def _to_float(token: str) -> tuple[float | None, str]:
    raw = token.strip()
    is_percent = raw.endswith("%")
    if is_percent:
        raw = raw[:-1]
    cleaned = raw.replace(",", "")
    try:
        value = float(cleaned)
    except (TypeError, ValueError):
        return None, raw
    if is_percent:
        return value / 100.0, token.strip()
    return value, token.strip()


def extract_numbers(text: str, *, limit: int = 200) -> list[float]:
    """Extract numeric tokens, preserving order and supporting grouped commas."""
    values: list[float] = []
    for token in _NUMBER_RE.findall(str(text or "")):
        value, _ = _to_float(token)
        if value is not None:
            values.append(value)
            if len(values) >= limit:
                break
    return values


def parse_dataset(text: str) -> tuple[list[float], dict[str, Any]]:
    """Extract the most plausible numeric dataset from free text or CSV/table input.

    Returns (values, metadata). Metadata records exactly what was excluded so the
    assistant can explain exclusions instead of silently discarding observations.
    """
    source = str(text or "")
    meta: dict[str, Any] = {"source": "direct text", "excluded": [], "columns": {}}

    # CSV / Markdown table: prefer the numeric column with the most observations.
    rows: list[list[str]] = []
    for line in source.splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells):
                continue
            rows.append(cells)
        elif "," in line:
            rows.append([c.strip() for c in line.split(",")])
        elif "\t" in line:
            rows.append([c.strip() for c in line.split("\t")])

    if len(rows) >= 2:
        columns: dict[int, list[float]] = {}
        for row in rows:
            for idx, cell in enumerate(row):
                value, _ = _to_float(cell)
                if value is not None:
                    columns.setdefault(idx, []).append(value)
        if columns:
            meta["source"] = "table or CSV"
            meta["columns"] = {f"column_{i + 1}": vals for i, vals in sorted(columns.items())}
            best = max(columns.values(), key=len)
            if len(best) >= 2:
                return best, meta

    # Labelled inline dataset: only use the segment after a dataset label.
    labelled: str | None = None
    lower = source.casefold()
    for label in _DATA_LABELS:
        match = re.search(rf"\b{re.escape(label)}\b\s*(?:is|are|=|:)?\s*(.+)", lower)
        if match:
            candidate = source[match.start(1):match.end(1)]
            if len(extract_numbers(candidate)) >= 2:
                labelled = candidate
                break
    segment = labelled if labelled is not None else source
    tokens = _NUMBER_RE.findall(segment)
    values: list[float] = []
    for token in tokens:
        value, original = _to_float(token)
        if value is None:
            continue
        # A bare 4-digit year next to no other context is unlikely to be an observation.
        if re.fullmatch(r"(?:19|20)\d{2}", original) and len(tokens) > 4 and labelled is None:
            meta["excluded"].append(original)
            continue
        values.append(value)
    if len(values) >= 2:
        return values, meta
    return [], {**meta, "excluded": meta["excluded"] + tokens}


def detect_quartile_method(text: str) -> tuple[str, str]:
    """Map natural-language convention names to a canonical method key."""
    folded = str(text or "").casefold().replace(" ", "_").replace("-", "_")
    for alias, canonical in _QUARTILE_ALIASES.items():
        if alias in folded:
            return canonical, alias
    return "linear", "default_linear_interpolation"


def extract_expression(text: str, keywords: tuple[str, ...]) -> str | None:
    """Return the text following the first matching computation keyword."""
    folded = str(text or "")
    for keyword in keywords:
        match = re.search(rf"\b{re.escape(keyword)}\b\s*(.*)", folded, flags=re.IGNORECASE)
        if match:
            expression = match.group(1).strip(" \n\r\t:?")
            expression = re.split(r"\?|^(?:in|using|with|for)\s+", expression, maxsplit=1, flags=re.IGNORECASE)[0]
            return expression.strip() or None
    return None


def parse_two_by_two(text: str) -> dict[str, int] | None:
    """Parse a 2x2 table only from explicit semantics or an explicit grid.

    Silently treating the first four integers in prose as a,b,c,d can invert an
    odds ratio or risk ratio, so unlabelled counts are rejected.
    """
    source = str(text or "")
    folded = source.casefold()
    labelled = re.search(
        r"a\s*=\s*(\d+).*?b\s*=\s*(\d+).*?c\s*=\s*(\d+).*?d\s*=\s*(\d+)",
        folded, flags=re.DOTALL,
    )
    if labelled:
        return dict(zip(("a", "b", "c", "d"), [int(value) for value in labelled.groups()]))

    semantic_patterns = {
        "a": (
            r"(\d+)\s+exposed\s+cases?\b", r"(\d+)\s+cases?\s+exposed\b",
            r"exposed\s+cases?\s*(?:=|:)\s*(\d+)", r"cases?\s+exposed\s*(?:=|:)\s*(\d+)",
        ),
        "b": (
            r"(\d+)\s+exposed\s+(?:non[-\s]?cases?|controls?|without\s+outcome)\b",
            r"exposed\s+(?:non[-\s]?cases?|controls?)\s*(?:=|:)\s*(\d+)",
        ),
        "c": (
            r"(\d+)\s+unexposed\s+cases?\b", r"(\d+)\s+cases?\s+unexposed\b",
            r"unexposed\s+cases?\s*(?:=|:)\s*(\d+)", r"cases?\s+unexposed\s*(?:=|:)\s*(\d+)",
        ),
        "d": (
            r"(\d+)\s+unexposed\s+(?:non[-\s]?cases?|controls?|without\s+outcome)\b",
            r"unexposed\s+(?:non[-\s]?cases?|controls?)\s*(?:=|:)\s*(\d+)",
        ),
    }
    cells: dict[str, int] = {}
    for name, patterns in semantic_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, folded)
            if match:
                cells[name] = int(match.group(1))
                break
    if len(cells) == 4:
        return cells

    numbers = [int(v) for v in extract_numbers(source) if float(v).is_integer() and v >= 0]
    explicit_grid = bool(re.search(r"\[\s*\[[^\]]+\]\s*,\s*\[[^\]]+\]\s*\]|\b2\s*[x×]\s*2\b", folded))
    explicit_table = explicit_grid or bool(re.search(r"\b(?:contingency|2x2)\b.*\btable\b|\btable\b.*\b(?:contingency|2x2)\b", folded))
    if len(numbers) >= 4 and explicit_grid:
        return {"a": numbers[0], "b": numbers[1], "c": numbers[2], "d": numbers[3]}
    return None
