"""Speech planning for CRARA voice replies.

This module turns display text into a speech script with mode-aware pacing,
pauses, and optional lightweight conversational cues. It deliberately treats
speech rendering as a presentation concern: it must not add facts, diagnoses,
or clinical advice.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_SPEECH_MODES = {"chat", "presentation"}
_SPEECH_STYLES = {"natural", "clear", "expressive"}

_SENSITIVE_RE = re.compile(
    r"\b(diagnos(?:e|is)|prescrib(?:e|ing)|dose|dosage|treat(?:ment)? plan|"
    r"emergency|suicid(?:e|al)|self-harm|chest pain|bleeding|seizure|"
    r"call (?:a )?doctor|seek (?:urgent|immediate)|overdose)\b",
    re.I,
)

_FILLERS = {
    "EN": ["Hmm...", "Let me think...", "Right..."],
    "NY": ["Hmm...", "Tiyeni tiwone...", "Chabwino..."],
}

_TRANSITIONS = {
    "EN": {
        "presentation": ["Let's walk through this.", "Here's the key point.", "To summarize,"],
        "chat": ["Okay.", "So,", "Here's the thing,"],
    },
    "NY": {
        "presentation": ["Tiyeni tidutse izi.", "Mfundo yaikulu ndi iyi.", "Mwachidule,"],
        "chat": ["Chabwino.", "Choncho,", "Tiyeni tiwone,"],
    },
}


@dataclass
class SpeechPlan:
    text: str
    mode: str
    style: str
    language: str
    ssml: str
    cues: list[dict]
    plain_fallback: str


def normalize_speech_mode(value: str | None, *, default: str = "chat") -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in _SPEECH_MODES else default


def normalize_speech_style(value: str | None, *, default: str = "natural") -> str:
    style = str(value or "").strip().lower()
    return style if style in _SPEECH_STYLES else default


def plain_speech_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]*)\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.M)
    text = re.sub(r"\*\*|__|~~|\*", "", text)
    text = re.sub(r"\\\(|\\\)|\\\[|\\\]", " ", text)
    text = re.sub(r"\$\$?[^$]+\$\$?", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1800]


def _sensitive(text: str) -> bool:
    return bool(_SENSITIVE_RE.search(text or ""))


def _sentence_chunks(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _pause_ms(mode: str, style: str, index: int, total: int) -> int:
    if style == "clear":
        base = 420 if mode == "presentation" else 280
    elif style == "expressive":
        base = 360 if mode == "presentation" else 220
    else:
        base = 320 if mode == "presentation" else 180
    if index == 0 and mode == "presentation":
        base += 120
    if index == total - 1:
        base += 80 if mode == "presentation" else 40
    return min(base, 700)


def _maybe_prefix(text: str, *, mode: str, style: str, language: str) -> tuple[str, list[dict]]:
    cues: list[dict] = []
    if style == "clear" or _sensitive(text):
        return text, cues
    chunks = _sentence_chunks(text)
    if len(chunks) < 2:
        return text, cues
    lang = "NY" if str(language).upper() == "NY" else "EN"
    # Very light, infrequent cues. Never add to sensitive content.
    if mode == "chat" and style == "expressive":
        filler = _FILLERS[lang][0]
        cues.append({"type": "filler", "value": filler, "at": "start"})
        return f"{filler} {text}", cues
    if mode == "presentation":
        lead = _TRANSITIONS[lang]["presentation"][0] if lang in _TRANSITIONS else ""
        if lead and not text.lower().startswith(lead.lower()):
            cues.append({"type": "transition", "value": lead, "at": "start"})
            return f"{lead} {text}", cues
    return text, cues


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def build_speech_plan(text: str, *, mode: str = "chat", style: str = "natural",
                      language: str = "EN") -> SpeechPlan:
    mode = normalize_speech_mode(mode)
    style = normalize_speech_style(style)
    language = "NY" if str(language or "EN").upper() == "NY" else "EN"
    plain = plain_speech_text(text)
    if not plain:
        return SpeechPlan(text="", mode=mode, style=style, language=language,
                          ssml="", cues=[], plain_fallback="")

    rendered, cues = _maybe_prefix(plain, mode=mode, style=style, language=language)
    chunks = _sentence_chunks(rendered)
    if not chunks:
        chunks = [rendered]

    ssml_parts = ["<speak>"]
    rate = "92%" if mode == "presentation" else "96%"
    pitch = "-1st" if mode == "presentation" else "+0st"
    ssml_parts.append(f'<prosody rate="{rate}" pitch="{pitch}">')
    for i, chunk in enumerate(chunks):
        ssml_parts.append(_xml_escape(chunk))
        if i < len(chunks) - 1:
            pause = _pause_ms(mode, style, i, len(chunks))
            ssml_parts.append(f'<break time="{pause}ms"/>')
            cues.append({"type": "pause", "ms": pause, "after": i})
    ssml_parts.append("</prosody>")
    ssml_parts.append("</speak>")
    ssml = "".join(ssml_parts)

    return SpeechPlan(
        text=rendered,
        mode=mode,
        style=style,
        language=language,
        ssml=ssml,
        cues=cues,
        plain_fallback=plain,
    )
