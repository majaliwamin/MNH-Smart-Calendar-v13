"""Deterministic presentation of verified computation records.

The language layer may translate the surrounding prose, but these helpers are
the authoritative fallback: they can answer a computational turn without any
model, preserving every number, symbol and formula exactly as computed.
"""
from __future__ import annotations

import json
from typing import Any

from .results import MathResult


def _display(value: Any) -> Any:
    if isinstance(value, float):
        return float(f"{value:.10g}")
    if isinstance(value, dict):
        return {str(key): _display(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_display(item) for item in value]
    return value


def _blocked_text(reason: str, chichewa: bool) -> str:
    if chichewa:
        # Reasons are generated in English inside the engine. Appending them to
        # a Chichewa refusal would break the response-language contract, so use
        # a complete Chichewa request for the missing information instead.
        return (
            "Pepani, sindingathe kuwerengera izi molondola chifukwa deta yofunikira "
            "sinaperekedwe kapena siyovomerezeka. Chonde perekani miyezo, tebulo kapena "
            "njira yowerengera yomwe mukufuna."
        )
    return (
        "I cannot calculate this reliably because the required information is "
        "missing or invalid. " + reason + " Please provide the required values "
        "or state the convention you want to use."
    )


def blocked_math_answer(result: MathResult, response_language: str = "EN") -> str:
    """Return a truthful refusal without calling a language model."""
    reason = result.interpretation or (result.warnings[0] if result.warnings else "The input is incomplete.")
    return _blocked_text(reason, str(response_language).upper() == "CH")


def deterministic_math_answer(result: MathResult, response_language: str = "EN", *, include_code: bool = True) -> str:
    """Render a complete, model-independent answer for a verified result."""
    if result.status == "blocked":
        return blocked_math_answer(result, response_language)
    chichewa = str(response_language).upper() == "CH"
    heading = "## Verified calculation" if not chichewa else "## Zotsatira za kuwerengera zotsimikizika"
    method_label = "**Method**" if not chichewa else "**Njira**"
    steps_label = "**Steps**" if not chichewa else "**Masitepe**"
    values_label = "**Key values**" if not chichewa else "**Zotsatira zazikulu**"
    interpretation_label = "**Interpretation**" if not chichewa else "**Tanthauzo**"
    assumptions_label = "**Assumptions**" if not chichewa else "**Zongoganizira**"
    warning_label = "**Limits and cautions**" if not chichewa else "**Malire ndi machenjerero**"
    code_label = "**Reproducible code**" if not chichewa else "**Khodi yobwerezabwereza**"

    lines = [heading, "", f"{method_label}: {result.method or result.operation}"]
    if result.steps:
        lines += ["", steps_label]
        lines += [f"{index}. {step}" for index, step in enumerate(result.steps, start=1)]
    if result.values:
        payload = json.dumps(_display(result.values), ensure_ascii=False, indent=2, sort_keys=True)
        lines += ["", values_label, "", "```json", payload, "```"]
    if result.interpretation:
        lines += ["", f"{interpretation_label}: {result.interpretation}"]
    if result.assumptions:
        lines += ["", assumptions_label]
        lines += [f"- {item}" for item in result.assumptions]
    if result.warnings:
        lines += ["", warning_label]
        lines += [f"- {item}" for item in result.warnings]
    if result.chart:
        chart_title = str(result.chart.get("title", "Chart"))
        chart = json.dumps(_display(result.chart), ensure_ascii=False, indent=2, sort_keys=True)
        lines += ["", chart_title, "", "```chart", chart, "```"]
    if include_code and result.code:
        lines += ["", code_label, "", "```python", result.code.rstrip(), "```"]
    return "\n".join(lines).strip() + "\n"


def math_contract_instruction(result: MathResult) -> str:
    """Tell the language layer how to use an authoritative computation block."""
    return (
        "VERIFIED COMPUTATION CONTRACT\n"
        "- The computation record in this prompt is authoritative numeric source data, not a suggestion.\n"
        "- Do not recompute, correct, round away, or replace any value in the record.\n"
        "- Preserve all headline values, units, precision, inequality direction and formula notation exactly.\n"
        "- Explain the supplied intermediate steps and state the stated assumptions and cautions.\n"
        "- Use valid \\( ... \\) and \\[ ... \\] LaTeX for symbols and equations.\n"
        "- If the record contains a chart, reproduce the chart block exactly when a visual helps.\n"
        "- If the record is blocked, ask for the exact missing information; never produce a guessed number.\n"
        "- Do not cite literature, p-values, sample sizes or guidelines that are not in the record or retrieved evidence."
    )
