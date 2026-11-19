"""Independent language and communication-mode detection for CRARA.

This module deliberately uses observable evidence in the user's message and the
recent conversation rather than asking the language model to judge its own
output. It answers two separate questions:

1. Which language is the user writing in (EN, CH, or a mix)?
2. What is the user trying to do (converse, translate, explain, follow up, ...)?

The result is used to select the response language and the relevant prompt
contract. It is intentionally conservative: uncertain input falls back to the
user's explicit selection rather than triggering a Chichewa answer by guesswork.
"""
import re

from app.class_rep.expressive_style import casual_style_block
from app.class_rep.language import (
    DEFAULT_RESPONSE_LANGUAGE,
    SUPPORTED_RESPONSE_LANGUAGES,
    normalize_response_language,
)

# High-confidence markers. Scores are based on *distinct* tokens so repetition
# cannot push an English message into Chichewa (or the reverse).
_STRONG_CHICHEWA = {
    "bwanji", "bwanj", "chani", "chiyani", "chan", "ndi", "nanga", "chifukwa",
    "kodi", "zikomo", "moni", "tadzuka", "mwadzuka", "mwauka", "mwaswera",
    "ndaswera", "bwino", "chonde", "pitiriza", "fotokozani", "amatanthauza",
    "tanthauzo", "zikutanthauza", "inde", "iyayi", "ayi", "eya", "chabwino",
    "pepani", "mwana", "munthu", "anthu", "ana", "malungo", "matenda", "lero",
    "mawa", "tsopano", "pano", "apo", "kuti", "zingati", "pang'ono", "pang'ono",
    "yang'ana", "kuwopsya", "ndani", "bwera", "ichi", "icho",
}
_MEDIUM_CHICHEWA = {
    "koma", "kapena", "ndipo", "komabe", "ine", "iwe", "iye", "ife", "inu",
    "iwo", "kaya", "liti", "pafupi", "patali", "posachedwa", "tsalani",
    "dzina", "langa", "lako", "lanu", "ndithu", "gawo", "lotsatira",
    "m'chichewa", "mchingerezi", "chichewa", "zingati", "mudzi", "mawu",
    "akuti", "bwino",
}
_STRONG_ENGLISH = {
    "the", "is", "are", "was", "were", "what", "does", "do", "mean", "means",
    "meaning", "please", "explain", "translate", "translation", "how", "why",
    "can", "could", "would", "your", "this", "that", "these", "those", "about",
    "with", "from", "which", "where", "when", "who", "have", "has", "had",
    "will", "should", "understand", "because", "want", "need", "tell",
}
_MEDIUM_ENGLISH = {
    "a", "an", "and", "or", "but", "in", "to", "of", "for", "on", "at", "it",
    "its", "my", "we", "you", "your", "i", "me", "us", "they", "them", "not",
    "english", "next", "continue", "yes", "no", "sorry", "thanks", "hello",
}

_TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)

# Typo/abbreviation patterns seen in real messages. They carry strong evidence
# even though the individual token is not a standard dictionary headword.
_TYPO_CHICHEWA = (
    (re.compile(r"\bnd\s+(?:chani|chiyani|chan)\b", re.I), 3),
    (re.compile(r"\b(?:mwaswera|mwadzuka|mwauka)\s+bwanj(?:i)?\b", re.I), 4),
    (re.compile(r"\bnd\s+[\w'-]{2,}\s+(?:nanga|chani|chiyani)\b", re.I), 3),
)

_TRANSLATE_INTO_CHICHEWA = re.compile(
    r"\b(?:translate|translation|render|convert|say)\b.{0,80}"
    r"\b(?:into|to|in)\s+(?:chichewa|chinyanja|chewa)\b"
    r"|\b(?:m'?chichewa|mu\s+chichewa|chichewa\s+translation)\b",
    re.I | re.S,
)
_TRANSLATE_INTO_ENGLISH = re.compile(
    r"\b(?:translate|translation|interpret|meaning|means|render)\b.{0,80}"
    r"\b(?:into|to|in)\s+english\b"
    r"|\b(?:in\s+english|into\s+english|english\s+translation|english\s+meaning)\b",
    re.I | re.S,
)
_EXPLAIN_EXPRESSION = re.compile(
    r"\b(?:ndi\s+(?:chani|chiyani|chan)|amatanthauza|tanthauzo\s+la|"
    r"zikutanthauza\s+chiyani|mawu\s+akuti|what\s+does\s+.{1,80}?\s+mean|"
    r"meaning\s+of|explain\s+the\s+meaning)\b",
    re.I | re.S,
)
_FOLLOWUPS = {
    "eya", "inde", "ayi", "iyayi", "next", "pitiriza", "continue", "why",
    "why?", "chifukwa chiyani", "that", "that one", "this one", "that's it", "ok", "okay",
    "chabwino", "correct", "wrong", "no", "yes", "more", "and then",
}
_ACADEMIC = re.compile(
    r"\b(?:research|method|statistics|statistical|analysis|assignment|"
    r"dissertation|thesis|lecture|module|examination|biomedical|clinical|"
    r"medical|maternal|neonatal|preeclampsia|malaria|physiology|anatomy|"
    r"microbiology|epidemiology|data|study|evidence|literature)\b",
    re.I,
)
# A short social mention of a topic ("just finished microbiology lab 🦠") is
# conversation, not an academic question. It must not weaken real task markers.
_CASUAL_TOPIC_MENTION = re.compile(
    r"\b(?:microb\w*|bacteri\w*|virus\w*|germ\w*|lab|pregnan\w*|newborn|"
    r"neonat\w*|baby|babies|maternal|malaria|midwif\w*|notes?|revision|"
    r"book|class)\b",
    re.I,
)
_ACADEMIC_TASK = re.compile(
    r"\b(?:explain|define|describe|compare|contrast|analyse|analyze|discuss|"
    r"evaluate|calculate|interpret|what\s+(?:is|are)|why|how\s+does|method|"
    r"statistics|assignment|thesis|dissertation|research|evidence|literature)\b",
    re.I,
)
_PLAYFUL = re.compile(r"\b(?:haha+|hehe+|hihi+|lol+|lmao|joke|joking|kidding)\b|🤣|😂|😜", re.I)
_DISTRESSED = re.compile(
    r"\b(?:sad|depressed|anxious|anxiety|worried|stressed|crying|upset|lonely|scared|afraid)\b|😭|😢|😔",
    re.I,
)
_CASUAL_SOCIAL = re.compile(
    r"^(?:moni|hello|hi|hey|muli\s+bwanj\w*|mwadzuka\s+bwanj\w*|mwaswera\s+bwanj\w*|"
    r"good\s+morning|how(?:'s|\s+is)\s+it\s+going|how\s+are\s+you|thanks|zikomo|chabwino)\b",
    re.I,
)
_MODE_CONVERSE = "converse"
_MODE_FOLLOWUP = "followup"
_MODE_EXPLAIN = "explain"
_MODE_TRANSLATE_CH = "translate_into_chichewa"
_MODE_TRANSLATE_EN = "translate_into_english"
_MODE_ACADEMIC = "academic"
MODES = {
    _MODE_CONVERSE, _MODE_FOLLOWUP, _MODE_EXPLAIN,
    _MODE_TRANSLATE_CH, _MODE_TRANSLATE_EN, _MODE_ACADEMIC,
}


def _normalise_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold().replace("’", "'"))


def _score(text: str) -> tuple[int, int]:
    tokens = set(_TOKEN_RE.findall(text))
    ch = sum(2 for token in tokens if token in _STRONG_CHICHEWA)
    ch += sum(1 for token in tokens if token in _MEDIUM_CHICHEWA and token not in _STRONG_CHICHEWA)
    en = sum(2 for token in tokens if token in _STRONG_ENGLISH)
    en += sum(1 for token in tokens if token in _MEDIUM_ENGLISH and token not in _STRONG_ENGLISH)
    for pattern, weight in _TYPO_CHICHEWA:
        if pattern.search(text):
            ch += weight
    return ch, en


def detect_language(message: str) -> str:
    """Return CH, EN or MIXED from lexical evidence in ``message``.

    Default is EN: detection only overrides when there is a clear preponderance
    of Chichewa markers, so an English academic sentence with one Chichewa term
    is not silently answered in Chichewa.
    """
    text = _normalise_text(message)
    if not text:
        return "EN"
    ch, en = _score(text)
    if ch >= 3 and ch >= en * 2:
        return "CH"
    if ch >= 2 and ch > en:
        return "CH"
    if en >= 3 and en >= ch * 2:
        return "EN"
    if ch >= 2 and en >= 2:
        return "MIXED"
    return "EN"


def detect_mode(message: str, history: list[dict] | None = None) -> str:
    """Classify the communicative intent of the current message."""
    text = _normalise_text(message)
    if not text:
        return _MODE_CONVERSE
    # Explicit direction wins over a generic "meaning" cue: "nd rickets in
    # english" is a translation request, not an English academic question.
    if _TRANSLATE_INTO_CHICHEWA.search(text):
        return _MODE_TRANSLATE_CH
    if _TRANSLATE_INTO_ENGLISH.search(text):
        return _MODE_TRANSLATE_EN
    if text in _FOLLOWUPS and history:
        return _MODE_FOLLOWUP
    if _EXPLAIN_EXPRESSION.search(text):
        return _MODE_EXPLAIN
    # Short social mentions keep their topic flavour without becoming a lecture.
    if (len(text) <= 100 and "?" not in text
            and _CASUAL_TOPIC_MENTION.search(text)
            and not _ACADEMIC_TASK.search(text)):
        return _MODE_CONVERSE
    if _ACADEMIC.search(text):
        return _MODE_ACADEMIC
    return _MODE_CONVERSE


def detect_tone(message: str, history: list[dict] | None = None) -> str:
    """Return distress, playful, warm or neutral using observable markers."""
    text = _normalise_text(message)
    if not text:
        return "neutral"
    if _DISTRESSED.search(text):
        return "distressed"
    if _PLAYFUL.search(text):
        return "playful"
    is_short_task = len(text) <= 40 and not _ACADEMIC_TASK.search(text) and not _ACADEMIC.search(text)
    if _CASUAL_SOCIAL.search(text) or is_short_task:
        return "warm"
    return "neutral"


def resolve_response_language(
    requested: str | None,
    message: str,
    persisted_preference: str | None = None,
    explicit_preference: bool = False,
    history: list[dict] | None = None,
) -> str:
    """Select the reply language from explicit choice, intent and evidence.

    A user who has explicitly saved EN or CH keeps that choice. Otherwise a
    clearly Chichewa message is answered in Chichewa even when a client sends
    the schema default ``EN``; translation requests follow their target.
    """
    requested_language = normalize_response_language(requested)
    mode = detect_mode(message, history)
    if mode == _MODE_TRANSLATE_CH:
        return "CH"
    if mode == _MODE_TRANSLATE_EN:
        return "EN"
    if explicit_preference and persisted_preference in SUPPORTED_RESPONSE_LANGUAGES:
        return str(persisted_preference).upper()
    if detect_language(message) == "CH":
        return "CH"
    return requested_language or DEFAULT_RESPONSE_LANGUAGE


def mode_instruction(mode: str) -> str:
    """Return a short, mode-specific contract (never a generic service menu)."""
    instructions = {
        _MODE_FOLLOWUP: (
            "CURRENT TASK: This is a short follow-up. Resolve it against the most "
            "recent exchange, continue that task, and do not restart the "
            "conversation or list services."
        ),
        _MODE_EXPLAIN: (
            "CURRENT TASK: Explain the meaning of the expression in the message. "
            "Use retrieved reference entries when available, distinguish what a "
            "source actually says from inference, and ask for the surrounding "
            "sentence only when the expression is genuinely ambiguous."
        ),
        _MODE_TRANSLATE_CH: (
            "CURRENT TASK: Produce a natural Malawian Chichewa rendering. Return "
            "the Chichewa first; add only a brief usage note when needed."
        ),
        _MODE_TRANSLATE_EN: (
            "CURRENT TASK: Render the source text in clear natural English. "
            "Preserve quoted Chichewa separately and explain it, do not translate "
            "the request itself."
        ),
        _MODE_ACADEMIC: (
            "CURRENT TASK: Answer the academic or biomedical question directly "
            "with precise terminology and no fabricated statistics or citations."
        ),
        _MODE_CONVERSE: (
            "CURRENT TASK: Respond naturally to the user's message in the "
            "selected language. Keep the exchange contextual and concise."
        ),
    }
    return instructions.get(mode, instructions[_MODE_CONVERSE])


def tone_style_instruction(tone: str, mode: str, response_language: str = "EN") -> str:
    """Return the casual-only style layer; empty for serious or non-social turns."""
    return casual_style_block(mode, tone, response_language)


def language_profile(message: str, history: list[dict] | None = None) -> dict:
    """Diagnostic summary used by /status and tests; never shown to end users."""
    return {
        "detected_language": detect_language(message),
        "mode": detect_mode(message, history),
        "tone": detect_tone(message, history),
    }
