"""Rule-based validation of CRARA replies using independent evidence.

Validation never asks the same model whether its own Chichewa is correct. It
uses deterministic checks plus the language/mode evidence computed from the
user's message and the references actually retrieved for this turn. Failures
trigger one bounded regeneration with a corrective contract; if that also
fails, the user receives an honest, language-appropriate limitation rather
than a fabricated answer.
"""
from dataclasses import dataclass, field

from app.class_rep.language_intelligence import detect_language

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


def validate_reply(
    reply: str,
    message: str,
    response_language: str,
    mode: str = "converse",
    evidence_available: bool = False,
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
