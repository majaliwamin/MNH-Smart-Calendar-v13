"""Casual-only expressive style for CRARA.

Emojis, clean jokes and informal phrasing are layered on *only* for short
social conversation. Academic, translation, meaning-explanation, biomedical,
maternal/neonatal medical answers and distressed users never receive this layer.
The Chichewa informal forms below are limited to forms printed in the curated
Lesson 1–2 greeting material; no regional slang, jokes or medical idiom is
invented. Jokes are English-only and drawn from a fixed non-clinical library.
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

# Short, clean, non-clinical jokes. They are candidates for a playful English
# social turn only — never for medical, academic, distressing or Chichewa turns.
CURATED_JOKES_EN = (
    "Why did the notebook blush? It saw the teacher's red pen. 📝",
    "I told my pencil to relax. It said it was feeling a little blunt. ✏️",
    "Why did the library book get promoted? It had a glowing review. 📚",
    "I tried to write a joke about stationery, but it came out a little dull. 📝",
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
_JOKE_REQUEST = re.compile(
    r"\b(?:tell|share|make|give|know|hear)\b.*\bjokes?\b|^\s*jokes?\b|"
    r"\bnthabwala\b",
    re.I,
)


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


def casual_joke_answer(message: str, response_language: str = "EN") -> str | None:
    """Deterministic answer for an explicit joke request in a casual turn."""
    if not _JOKE_REQUEST.search(message or ""):
        return None
    if str(response_language).upper() == "CH":
        return "Pepani, sindikudziwa nthabwala za Chichewa. Moni! 😊"
    return CURATED_JOKES_EN[0]


def casual_style_block(mode: str, tone: str, response_language: str = "EN") -> str:
    """Return the system-prompt layer, or an empty string when it must not apply."""
    if not is_casual_turn(mode, tone):
        return ""
    language = str(response_language or "EN").upper()
    informal = "\n".join("- " + form + " — " + note for form, note in VERIFIED_INFORMAL_CHICHEWA)
    header = (
        "CASUAL SOCIAL STYLE (active for this turn only):\n"
        "- The user is making small talk. Be warm, brief and natural. You may use one "
        "or two emojis that match the mood and topic. Available facial expressions "
        "include 😊 🙂 😄 😂 🤣 😜 😐 😶 🥳 😎; topic emojis include 🦠 🧬 🔬 🧫 "
        "🤰 👶 🍼 🩺 📝 📚.\n"
        "- Never use this style for academic, translation, meaning-explanation or "
        "medical answers, and never joke about illness, pregnancy, babies, bodies, "
        "death, identity or a user's distress.\n"
    )
    if language == "CH":
        return (
            header +
            "- Do NOT tell jokes in Chichewa. Do not invent slang, idioms or humour. "
            "Use only the verified warm forms below when a social phrase is useful.\n\n"
            "VERIFIED STANDARD-INFORMAL CHICHEWA FORMS:\n" + informal
        )
    jokes = "\n".join("- " + item for item in CURATED_JOKES_EN)
    return (
        header +
        "- If the exchange is clearly playful, use at most ONE clean short line from "
        "the curated list below. Never write your own joke.\n"
        "- English informal warmth is fine.\n\n"
        "CURATED SOCIAL LINES:\n" + jokes + "\n\n"
        "VERIFIED STANDARD-INFORMAL CHICHEWA FORMS:\n" + informal
    )
