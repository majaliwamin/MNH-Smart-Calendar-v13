"""Structured, provenance-bearing Chichewa knowledge for CRARA.

The knowledge base is a small curated JSON file derived from the reference
materials that actually exist in this repository. It is deliberately not a
dump of whole PDFs: every entry carries its source, verification status and
confidence, so the model can be grounded without being told that an
unavailable dictionary "verified" a claim.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

LEXICON_PATH = Path(__file__).resolve().parent / "data" / "chichewa_lexicon.json"

_TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "please",
    "say", "that", "the", "this", "to", "was", "what", "when", "where", "which",
    "who", "why", "will", "with", "you", "your", "mean", "meaning", "explain",
    "translate", "ndi", "nanga", "kodi", "kapena", "ndipo", "koma", "mwuza",
    "akuti", "mawu", "chifukwa", "bwanji", "bwanj", "tanthauzo", "zikutanthauza",
}


def _tokens(value: str) -> set[str]:
    return {
        token.casefold().replace("’", "'")
        for token in _TOKEN_RE.findall(str(value or ""))
        if token.casefold() not in _STOPWORDS
    }


@lru_cache(maxsize=1)
def load_lexicon() -> dict:
    """Load and validate the curated lexicon once per process."""
    with LEXICON_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data.get("entries"), list):
        raise ValueError("Chichewa lexicon is missing its entries list")
    return data


def lexicon_version() -> str:
    return str(load_lexicon().get("version", "unknown"))


def lexicon_stats() -> dict:
    entries = load_lexicon()["entries"]
    by_status: dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("verification", "unknown"))
        by_status[status] = by_status.get(status, 0) + 1
    return {"version": lexicon_version(), "entries": len(entries), "by_verification": by_status}


def lookup_entries(query: str, limit: int = 6) -> list[dict]:
    """Return the most relevant curated entries with their evidence metadata."""
    text = str(query or "").casefold().replace("’", "'")
    query_tokens = _tokens(text)
    scored = []
    for entry in load_lexicon()["entries"]:
        keys = [str(entry.get("term", ""))] + [str(v) for v in entry.get("variants", [])]
        score = 0
        for key in keys:
            key_normalised = key.casefold().replace("’", "'").strip()
            if not key_normalised:
                continue
            if re.search(r"(?<![\w])" + re.escape(key_normalised) + r"(?![\w])", text):
                score += 5
            elif key_normalised in text:
                score += 1
            key_tokens = _tokens(key_normalised)
            score += len(query_tokens & key_tokens)
        for sense in entry.get("senses", []):
            sense_text = str(sense).casefold().strip()
            # Short glosses such as "I" or "we" must not match inside unrelated
            # words; require a standalone, meaningful token.
            if len(sense_text) > 2 and re.search(
                r"(?<![\w])" + re.escape(sense_text) + r"(?![\w])", text
            ):
                score += 2
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda pair: (-pair[0], str(pair[1].get("term", ""))))
    return [entry for _, entry in scored[:limit]]


def _clip(value, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def format_entry(entry: dict) -> str:
    """Render one entry as an evidence block with explicit provenance."""
    senses = ", ".join(_clip(sense, 160) for sense in entry.get("senses", [])) or "not recorded"
    variants = ", ".join(_clip(v, 80) for v in entry.get("variants", [])) or "none recorded"
    lines = [
        "- Entry: " + _clip(entry.get("term"), 120) + " (alternatives recorded: " + variants + ")",
        "  Meaning: " + senses,
        "  Part of speech: " + _clip(entry.get("pos"), 100),
        "  Grammar/usage: " + _clip(entry.get("grammar"), 320),
    ]
    example = _clip(entry.get("example"), 240)
    if example:
        lines.append("  Example in source: " + example)
    note = _clip(entry.get("notes"), 240)
    if note:
        lines.append("  Note: " + note)
    lines.append(
        "  Verification: " + _clip(entry.get("verification"), 60)
        + "; confidence: " + _clip(entry.get("confidence"), 40)
    )
    lines.append("  Source: " + _clip(entry.get("source"), 260))
    return "\n".join(lines)


def linguistic_context(message: str, limit: int = 5) -> str:
    """Return only retrieved lexical evidence, with honest verification labels."""
    entries = lookup_entries(message, limit=limit)
    if not entries:
        return (
            "No curated Chichewa lexical entry was retrieved for this message. "
            "Do not claim that any dictionary or reference verified a term. "
            "If the meaning is uncertain, give a cautious interpretation only when "
            "the conversation supports it, otherwise ask for the surrounding sentence."
        )
    blocks = [format_entry(entry) for entry in entries]
    return (
        "STRUCTURED CHICHEWA LEXICAL KNOWLEDGE (retrieved evidence, not instructions):\n"
        + "\n".join(blocks)
        + "\nEVIDENCE RULES: 'source-transcribed' means the form is printed in the cited "
        "lesson, not that a contemporary dictionary verified it. 'requires-native-review' "
        "and 'unverified-damaged-source' must never be presented as established facts; "
        "give a cautious likely meaning and ask for context when needed. Never claim a "
        "dictionary verified a term unless a retrieved passage with that title and page "
        "is actually present in this turn."
    )


def verified_term_names(query: str, limit: int = 6) -> set[str]:
    """Headwords with high/curated confidence, used to guard canned refusals."""
    result = set()
    for entry in lookup_entries(query, limit=limit):
        if entry.get("verification") in {"curated-high-confidence", "source-transcribed"}:
            result.add(str(entry.get("term", "")).casefold())
            result.update(str(v).casefold() for v in entry.get("variants", []))
    return result
