"""Safe structured-data inspection for CSV, Excel and pasted tables."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from .descriptive import describe
from .results import MathResult, blocked_result


def _pandas():
    try:
        import pandas as pd
        return pd, None
    except Exception as exc:
        return None, str(exc)


def inspect_csv(text: str, *, name: str = "dataset", quartile_method: str = "linear") -> MathResult:
    pd, error = _pandas()
    if pd is None:
        return blocked_result("dataset_inspection", f"Dataset inspection needs pandas: {error}", domain="data")
    try:
        frame = pd.read_csv(io.StringIO(str(text or "")))
    except Exception as exc:
        return blocked_result("dataset_inspection", f"Could not parse CSV: {exc}", domain="data")
    return _summarize(frame, name, quartile_method, source="CSV text")


def inspect_excel(path: str | Path, *, name: str | None = None, quartile_method: str = "linear") -> MathResult:
    pd, error = _pandas()
    if pd is None:
        return blocked_result("dataset_inspection", f"Excel inspection needs pandas/openpyxl: {error}", domain="data")
    try:
        frame = pd.read_excel(path)
    except Exception as exc:
        return blocked_result("dataset_inspection", f"Could not read workbook: {exc}", domain="data")
    return _summarize(frame, name or str(Path(path).name), quartile_method, source="Excel workbook")


def _summarize(frame: Any, name: str, quartile_method: str, source: str) -> MathResult:
    numeric = {}
    for column in frame.columns:
        series = frame[column].dropna()
        coerced = []
        for value in series.tolist():
            try:
                coerced.append(float(value))
            except (TypeError, ValueError):
                continue
        if coerced:
            numeric[str(column)] = describe(coerced, quartile_method=quartile_method, data_name=str(column)).as_dict()["values"]
    missing = {str(column): int(frame[column].isna().sum()) for column in frame.columns}
    duplicates = int(frame.duplicated().sum())
    return MathResult(
        operation="dataset_inspection", domain="data", method="pandas structural inspection",
        inputs={"name": name, "source": source, "rows": int(len(frame)), "columns": [str(c) for c in frame.columns]},
        assumptions=["Header row is present for CSV input.", "Missing values are reported, never silently imputed."],
        steps=["Parse the table.", "Classify columns, count missing values and duplicates.", "Summarise numeric columns without dropping rows silently."],
        values={
            "shape": [int(frame.shape[0]), int(frame.shape[1])],
            "columns": [{"name": str(c), "dtype": str(frame[c].dtype), "missing": missing[str(c)]} for c in frame.columns],
            "duplicate_rows": duplicates,
            "numeric_summaries": numeric,
            "total_missing_cells": sum(missing.values()),
        },
        warnings=["Categorical columns are reported structurally but not numerically summarised."],
        interpretation="Inspect missingness and duplicates before interpreting any statistical test.",
    )
