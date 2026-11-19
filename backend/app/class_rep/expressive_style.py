"""Casual-only expressive style for CRARA.

Emojis, clean jokes and informal phrasing are layered on *only* for short
social conversation. Academic, translation, meaning-explanation, biomedical,
maternal/neonatal medical answers and distressed users never receive this layer.
The Chichewa informal forms below are limited to forms printed in the curated
Lesson 1–2 greeting material; no regional slang or medical idiom is invented.
"""
from __future__ import annotations

import re

FACE_EMOJIS = (
    "😀", "😃", "😄", "😁", "😆", "😅", "🤣", "😂", "🙂", "🙃", "😉", "😊",
    "😇", "🥰", "😍", "🤩", "😘", "😋", "😛", "😜", "🤪", "😝", "🤗", "🤭",
    "🤫", "🤔", "🤐", "🤨", "😐", "😑", "😶", "😏", "😒", "🙄", "😬", "😮",
    "😯", "😲", "😳", "🥺", "😦", "😧", "😨", "😰", "😥", "😢", "😭", "😱",
    "😖", "😣", "😞", "😓", "😩", "😫", "🥱", "😴", "🤯", "🤠", "🥳", "😎",
    "🤓", "🧐",
)
MICROBIOLOGY_EMOJIS = ("🦠", "🧬", "🔬", "🧫", "🧪", "⚕️")
MATERNAL_NEONATAL_EMOJIS = ("🤰", "👶", "🍼", "🩺", "💉", "🩸", "🫀", "🫁")
STUDY_EMOJIS = ("📝", "📚", "📖", "✏️", "🎓", "🔖")
ALL_EMOJIS = FACE_EMOJIS + MICROBIOLOGY_EMOJIS + MATERNAL_NEONATAL_EMOJIS + STUDY_EMOJIS

CASUAL_MODES = frozenset({"converse", "followup"})

# Verified standard-informal forms from the curated Chichewa greeting lessons.
VERIFIED_INFORMAL_CHICHEWA = (
    ("Moni", "hello / hi — standard informal greeting"),
    ("Muli bwanji?", "how are you? — standard greeting"),
    ("Mwadzuka bwanji?", "good morning / how did you wake up? — standard greeting"),
    ("Mwaswera bwanji?", "good afternoon / how has your afternoon been? — standard greeting"),
    ("Eya", "yes — informal confirmation"),
    ("Inde", "yes — standard"),
    ("Chabwino", "OK / fine — standard informal"),
    ("Zikomo", "thank you — standard"),
    ("Pepani", "sorry / excuse me — standard"),
    ("Tsalani bwino", "goodbye — standard"),
)

# Short, clean, non-clinical jokes. They are candidates for a playful social
# turn, never for a medical, academic or distressing exchange.
CURATED_JOKES_EN = (
    "Why did the microscope get promoted? It was always looking at the bigger picture. 🔬",
    "I asked the bacteria to be polite. They said, 'We're still Gram-negative.' 🦠",
    "Why did the baby monitor get a promotion? It was always on call. 🍼",
    "My stethoscope and I have a very listening relationship. 🩺",
    "Why did the notebook blush? It saw the teacher's red pen. 📝",
)

# For Chichewa social turns we use verified warm phrases, not invented jokes.
VERIFIED_LIGHT_CHICHEWA = (
    "Zikomo! 😊",
    "Chabwino 🙂",
    "Eya! 😄",
    "Moni! 👋",
)

_LAUGHTER = re.compile(r"\b(?:haha+|hehe+|hihi+|lol+|lmao|joke|joking|kidding)\b|🤣|😂|😜", re.I)
_TEARS = re.compile(r"\b(?:crying|tears|sobb\w*)\b|😭|😢|😔", re.I)
_MICROBE_TOPIC = re.compile(r"\b(?:microb\w*|bacteri\w*|virus\w*|germ\w*|lab)\b", re.I)
_MOTHER_BABY_TOPIC = re.compile(r"\b(?:pregnan\w*|newborn|neonat\w*|baby|babies|maternal|midwif\w*)\b", re.I)
_STUDY_TOPIC = re.compile(r"\b(?:note\w*|study|studying|exam\w*|book\w*|class|revision|homework)\b", re.I)


def is_casual_turn(mode: str, tone: str) -> bool:
    """Only warm/playful social turns get the expressive layer."""
    return mode in CASUAL_MODES and tone != "distressed"


def _topic_emoji(message: str) -> str:
    if _MICROBE_TOPIC.search(message):
        return "🦠"
    if _MOTHER_BABY_TOPIC.search(message):
        return "🤰👶"
    if _STUDY_TOPIC.search(message):
        return "📝📚"
    return ""


def casual_flourish(answer: str, message: str, response_language: str = "EN") -> str:
    """Append one restrained emoji to a curated social answer."""
    text = str(answer or "").rstrip()
    if not text:
        return text
    if _LAUGHTER.search(message):
        emoji = "🤣"
    elif _TEARS.search(message):
        emoji = "😭"
    else:
        emoji = _topic_emoji(message) or ("🙂" if str(response_language).upper() == "CH" else "😊")
    return text + " " + emoji


def _joke_candidates(response_language: str) -> tuple[str, ...]:
    return VERIFIED_LIGHT_CHICHEWA if str(response_language).upper() == "CH" else CURATED_JOKES_EN


def casual_style_block(mode: str, tone: str, response_language: str = "EN") -> str:
    """Return the system-prompt layer, or an empty string when it must not apply."""
    if not is_casual_turn(mode, tone):
        return ""
    language = str(response_language or "EN").upper()
    jokes = "\n".join("- " + item for item in _joke_candidates(language))
    informal = "\n".join("- " + form + " — " + note for form, note in VERIFIED_INFORMAL_CHICHEWA)
    return (
        "CASUAL SOCIAL STYLE (active for this turn only):\n"
        "- The user is making small talk. Be warm, brief and natural. You may use one "
        "or two emojis that match the mood and topic. Available facial expressions "
        "include 😊 🙂 😄 😂 🤣 😜 😐 😶 🥳 😎; topic emojis include 🦠 🧬 🔬 🧫 "
        "🤰 👶 🍼 🩺 📝 📚.\n"
        "- If the exchange is clearly playful, use at most ONE clean short line from "
        "the curated list below. Never write your own medical, academic or personal joke.\n"
        "- Never joke about illness, pregnancy, babies, bodies, death, identity or a "
        "user's distress. Never use this style for academic, translation, "
        "meaning-explanation or medical answers.\n"
        "- English informal warmth is fine. In Chichewa, use only the verified "
        "standard-informal forms below; do not invent slang, idioms or Chichewa jokes, "
        "and label a form as informal if you comment on register.\n\n"
        "CURATED SOCIAL LINES:\n" + jokes + "\n\n"
        "VERIFIED STANDARD-INFORMAL CHICHEWA FORMS:\n" + informal
    )
