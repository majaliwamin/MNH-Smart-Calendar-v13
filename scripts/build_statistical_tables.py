"""Generate CRARA's statistical reference tables from SciPy distributions.

The generated JSON is committed with the app so the interactive lab works
offline. Values are produced by validated SciPy CDF/PPF functions, not copied
from an unverified web source. Run with:

    python scripts/build_statistical_tables.py
"""
from __future__ import annotations

import json
from pathlib import Path

import scipy
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "resources" / "data" / "statistical-tables.json"


def _alpha_key(value: float) -> str:
    return f"{value:g}"


def _z_section() -> dict:
    rows = [round(-3.4 + index * 0.1, 1) for index in range(69)]
    columns = [round(index * 0.01, 2) for index in range(10)]
    cumulative = {
        f"{row:.1f}": [round(float(stats.norm.cdf(row + column)), 4) for column in columns]
        for row in rows
    }
    alphas = [0.10, 0.05, 0.025, 0.01, 0.005]
    return {
        "rows": [f"{row:.1f}" for row in rows],
        "columns": [f"{column:.2f}" for column in columns],
        "cumulative": cumulative,
        "critical_values": {
            "one_tailed": {
                _alpha_key(alpha): round(float(stats.norm.ppf(1 - alpha)), 6) for alpha in alphas
            },
            "two_tailed": {
                _alpha_key(alpha): round(float(stats.norm.ppf(1 - alpha / 2)), 6) for alpha in alphas
            },
        },
        "worked_lookup": {
            "row": "2.0",
            "column": "0.00",
            "cumulative": 0.9772,
            "upper_tail": 0.0228,
            "two_tailed_p_from_table": 0.0456,
            "two_tailed_p_full_precision": round(2 * float(stats.norm.sf(2.0)), 6),
        },
    }


def _t_section() -> dict:
    dfs = list(range(1, 31)) + [40, 60, 120]
    one_alphas = [0.10, 0.05, 0.025, 0.01, 0.005]
    two_alphas = [0.10, 0.05, 0.025, 0.01, 0.005]
    return {
        "degrees_of_freedom": [str(value) for value in dfs],
        "one_tailed_alpha": [_alpha_key(value) for value in one_alphas],
        "two_tailed_alpha": [_alpha_key(value) for value in two_alphas],
        "one_tailed": {
            str(df): [round(float(stats.t.ppf(1 - alpha, df)), 4) for alpha in one_alphas]
            for df in dfs
        },
        "two_tailed": {
            str(df): [round(float(stats.t.ppf(1 - alpha / 2, df)), 4) for alpha in two_alphas]
            for df in dfs
        },
        "required_df": [1, 5, 10, 15, 20, 24, 25, 28, 30, 40, 60, 120],
    }


def _chi2_section() -> dict:
    dfs = list(range(1, 31)) + [40, 50, 60, 120]
    alphas = [0.10, 0.05, 0.025, 0.01, 0.005]
    return {
        "degrees_of_freedom": [str(value) for value in dfs],
        "right_tail_alpha": [_alpha_key(value) for value in alphas],
        "values": {
            str(df): [round(float(stats.chi2.ppf(1 - alpha, df)), 4) for alpha in alphas]
            for df in dfs
        },
    }


def _f_section() -> dict:
    dfs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 24, 30, 40, 60, 120]
    alphas = [0.10, 0.05, 0.025, 0.01, 0.005]
    return {
        "numerator_df": [str(value) for value in dfs],
        "denominator_df": [str(value) for value in dfs],
        "right_tail_alpha": [_alpha_key(value) for value in alphas],
        "values": {
            f"{df1}:{df2}": [round(float(stats.f.ppf(1 - alpha, df1, df2)), 4) for alpha in alphas]
            for df1 in dfs
            for df2 in dfs
        },
    }


def build() -> dict:
    return {
        "metadata": {
            "generated_by": f"scipy {scipy.__version__}",
            "purpose": "CRARA manual-first hypothesis-testing tables",
            "method": "SciPy norm/t/chi2/f CDF and PPF functions; four-decimal table values",
            "note": "Generated offline and committed for offline PWA use. Values are reference tables, not patient data.",
        },
        "z": _z_section(),
        "t": _t_section(),
        "chi2": _chi2_section(),
        "f": _f_section(),
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
