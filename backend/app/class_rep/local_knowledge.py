"""Read-only grounding in the bundled Python library and verified teaching data.

CRARA must answer programming/statistics questions from the teaching resources
shipped with this application before it falls back to general model knowledge.
The source index is generated at build time by
``scripts/build_statistical_glossary.py`` from:

* the executed bilingual statistical glossary,
* ``frontend/resources/python-command-library.html``, and
* the three fixed simulated teaching CSV files, and
* the publisher outline of one subscribed external reference book.

Nothing in this module executes user code or fetches an internet source. The
external book entry is bundled metadata only; its licensed full text is not
stored, fetched or claimed as read.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT

KNOWLEDGE_PATH = Path(
    os.getenv(
        "MNH_CRARA_LOCAL_KNOWLEDGE",
        str(PROJECT_ROOT / "backend" / "app" / "class_rep" / "data" / "local_teaching_knowledge.json"),
    )
).resolve()
SOURCE_LABEL = "bundled Python Command Library and bilingual statistics glossary"


@lru_cache(maxsize=1)
def knowledge() -> dict[str, Any]:
    """Load the generated source index once per process."""
    try:
        payload = json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("CRARA local teaching knowledge is unavailable") from exc
    if payload.get("schema_version") != 1:
        raise RuntimeError("CRARA local teaching knowledge has an unsupported schema")
    return payload


def build_id() -> str:
    return str(knowledge().get("build", ""))


_STOPWORDS = {
    "about", "after", "again", "before", "being", "between", "class", "classes",
    "could", "current", "dates", "explain", "following", "from", "have", "here",
    "into", "itself", "just", "lecture", "lesson", "local", "might", "monday",
    "next", "notes", "please", "schedule", "session", "should", "since", "some",
    "student", "students", "timetable", "time", "today", "tomorrow", "topic",
    "upcoming", "using", "week", "what", "when", "where", "which", "while", "with",
    "would", "your", "chonde", "kodi", "lero", "muli", "mwathe",
}


def _normalise(text: str) -> str:
    return str(text or "").casefold().replace("’", "'").replace("‘", "'")


def _tokens(text: str) -> set[str]:
    return {item for item in re.findall(r"[a-z]{3,}", _normalise(text)) if len(item) > 2}


def _meaningful_tokens(text: str) -> set[str]:
    return {
        item for item in _tokens(text)
        if len(item) >= 5 and item not in _STOPWORDS and item.casefold() not in _STOPWORDS
    }


def _score_terms(text: str, terms: list[str]) -> int:
    """Score a turn against curated source labels without broad word matching."""
    folded = _normalise(text)
    phrase_score = 0
    for term in terms:
        clean = _normalise(str(term).strip())
        if len(clean) < 4:
            continue
        if clean in folded:
            phrase_score += 12 if " " in clean else 7
    token_hits = sum(1 for token in _meaningful_tokens(text) if token in folded)
    if phrase_score:
        return phrase_score + token_hits
    # Without a term/alias phrase, require two distinctive overlapping tokens.
    return token_hits if token_hits >= 2 else 0


def _term_question(term: str) -> str:
    """Use the short technical name so Chichewa labels sound natural."""
    acronym = re.search(r"\(([A-Za-z0-9]+)\)", term)
    label = acronym.group(1) if acronym else term
    return f"{label} ndi chiyani?"


def glossary_context(message: str, response_language: str = "EN", limit: int = 2) -> str:
    """Return the most relevant executed glossary cards as source evidence."""
    chichewa = str(response_language).upper() == "CH"
    ranked: list[tuple[int, dict[str, Any]]] = []
    for entry in knowledge().get("glossary", []):
        terms = [entry.get("term", ""), entry.get("term_ny", "")]
        terms.extend(entry.get("aliases", []))
        score = _score_terms(message, terms)
        if score:
            ranked.append((score, entry))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked:
        return ""
    lines = [
        "LOCAL PYTHON LIBRARY — VERIFIED STATISTICAL GLOSSARY "
        "(primary source data for programming/statistics questions; not a web result):"
    ]
    for index, (_, entry) in enumerate(ranked[:limit], start=1):
        lines += [
            f"[{index}] {entry['term']} / {entry.get('term_ny', '')}",
            f"Definition: {str(entry.get('definition_en', ''))[:620]}",
        ]
        if chichewa:
            term = str(entry.get("term", ""))
            lines.append(f"{_term_question(term)}: {str(entry.get('explanation_ny', ''))[:620]}")
            lines.append(f"Practical use: {str(entry.get('application_ny', ''))[:360]}")
            lines.append(f"Misconception: {str(entry.get('misconception_ny', ''))[:360]}")
        else:
            lines.append(f"Python/code explanation: {str(entry.get('code_explanation_en', ''))[:520]}")
            lines.append(f"Practical use: {str(entry.get('application_en', ''))[:360]}")
            lines.append(f"Misconception: {str(entry.get('misconception_en', ''))[:360]}")
        if entry.get("output"):
            lines.append(f"Executed fixed-seed teaching output: {str(entry['output'])[:360]}")
    return "\n".join(lines)


def library_context(message: str, limit: int = 2) -> str:
    """Return relevant chapter-level evidence from the Python Command Library."""
    ranked: list[tuple[int, dict[str, Any]]] = []
    for section in knowledge().get("library_sections", []):
        terms = [
            str(section.get("title", "")),
            str(section.get("heading", "")),
            str(section.get("label", "")),
        ]
        terms.extend(str(item) for item in section.get("card_titles", []))
        score = _score_terms(message, terms)
        if score:
            ranked.append((score, section))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked:
        return ""
    lines = [
        "LOCAL PYTHON LIBRARY — CHAPTER EVIDENCE "
        "(bundled teaching resource; cite the chapter id when used):"
    ]
    for index, (_, section) in enumerate(ranked[:limit], start=1):
        intro = str(section.get("intro") or section.get("heading") or "")[:700]
        lines.append(
            f"[{index}] {section.get('title', '')} "
            f"(track: {section.get('track', '')}; source: python-command-library.html#{section.get('id', '')})\n"
            f"Teaching scope: {intro}"
        )
    return "\n".join(lines)


_BOOK_HINT = re.compile(
    r"\b(?:regression\s+methods\s+in\s+biostatistics|vittinghoff|springer|"
    r"biostatistics\s+(?:book|reference|textbook)|10\.1007/978-1-4614-1353-0|"
    r"978-1-4614-1353-0)\b",
    re.I,
)


def book_context(message: str, response_language: str = "EN", limit: int = 3) -> str:
    """Return publisher-outline evidence for the subscribed regression reference.

    This is bundled bibliographic metadata, not the licensed chapter text.
    CRARA may quote the outline and cite the DOI, but must not claim to have
    read the full book.
    """
    if not _BOOK_HINT.search(message):
        return ""
    chichewa = str(response_language).upper() == "CH"
    lines = [
        "CRARA BUNDLED REFERENCE — EXTERNAL BOOK OUTLINE "
        "(publisher bibliographic record and table of contents; the licensed full text is NOT bundled):"
    ]
    matched = False
    for book in knowledge().get("books", []):
        chapter_terms = [str(item.get("title", "")) for item in book.get("chapters", [])]
        score = _score_terms(message, list(book.get("aliases", [])) + chapter_terms)
        if not score:
            continue
        matched = True
        lines += [
            f"Title: {book.get('title', '')}: {book.get('subtitle', '')}",
            f"Authors: {', '.join(book.get('authors', []))}; "
            f"{book.get('edition', '')} ed.; {book.get('year', '')}; {book.get('publisher', '')}",
            f"DOI: {book.get('doi', '')} | ISBN: {book.get('isbn', '')} | URL: {book.get('url', '')}",
            f"Overall scope: {str(book.get('scope_en', ''))[:700]}",
        ]
        chapters = book.get("chapters", [])
        lines.append(
            "Chapters: " + "; ".join(
                f"{item.get('number', '')}. {item.get('title', '')} (pp. {item.get('pages', '')})"
                for item in chapters
            )
        )
        ranked: list[tuple[int, dict[str, Any]]] = []
        for item in chapters:
            title_score = _score_terms(message, [str(item.get("title", ""))])
            number_hit = re.search(
                r"\bchapter\s*#?\s*0*" + re.escape(str(item.get("number", ""))) + r"\b",
                message, re.I,
            )
            if title_score or number_hit:
                ranked.append((title_score + (20 if number_hit else 0), item))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        for _, item in ranked[:limit]:
            scope = item.get("scope_ny", "") if chichewa else item.get("scope_en", "")
            lines.append(
                f"Chapter {item.get('number', '')} — {item.get('title', '')} "
                f"(pp. {item.get('pages', '')}): {str(scope)[:300]}"
            )
        lines.append(
            f"Access: {book.get('access_note_ny', '') if chichewa else book.get('access_note_en', '')}"
        )
    return "\n".join(lines) if matched else ""


def dataset_context(message: str) -> str:
    """Describe the verified local teaching datasets when the request concerns data."""
    if not re.search(
        r"\b(?:data|dataset|csv|sample|simulat|teaching|chart|graph|plot|visuali[sz]|"
        r"distribution|curve|histogram|scatter|survival|statistics?)\b",
        message, re.I,
    ):
        return ""
    lines = [
        "LOCAL VERIFIED TEACHING DATASETS (simulated teaching data, never real patient records):"
    ]
    for name, item in knowledge().get("datasets", {}).items():
        lines.append(
            f"- {name}: {item.get('rows')} rows; columns: {', '.join(item.get('columns', []))}; "
            f"SHA-256 {str(item.get('sha256', ''))[:16]}…; {item.get('label_en', '')}"
        )
    return "\n".join(lines)


def local_teaching_context(message: str, response_language: str = "EN") -> str:
    """Build one bounded local-evidence block for the system prompt."""
    blocks = [
        glossary_context(message, response_language),
        library_context(message),
        book_context(message, response_language),
        dataset_context(message),
    ]
    blocks = [block for block in blocks if block]
    if not blocks:
        return ""
    return "\n\n" + "\n\n".join(blocks)
