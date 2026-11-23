"""Bounded, honest reading of a subscribed external teaching reference.

CRARA can discuss the publisher's bibliographic record and table of contents
for the bundled Springer reference. The licensed chapter text is not stored,
fetched or reproduced, and every answer says so explicitly. No user code is
executed and no internet request is made.
"""
from __future__ import annotations

import re
from typing import Any

from app.class_rep import local_knowledge

PROVIDER = "CRARA bundled reference"
MODEL = "springer-regression-methods-outline-v1"

_READ_INTENT = re.compile(
    r"\b(?:read|reading|open|summari[sz]e|summary|outline|recite|go\s+through|"
    r"show\s+me|teach\s+me|cover|present|werengani|werenga|fotokozani|"
    r"ndandanda|tsegulani)\b",
    re.I,
)
_BOOK_INTENT = re.compile(
    r"\b(?:regression\s+methods\s+in\s+biostatistics|vittinghoff|springer|"
    r"biostatistics\s+(?:book|reference|textbook)|10\.1007/978-1-4614-1353-0|"
    r"978-1-4614-1353-0)\b",
    re.I,
)
_CHAPTER_NUMBER = re.compile(
    r"\b(?:chapter|chaputala|chap\.?)\s*(?:number\s*)?#?\s*(\d{1,2})\b",
    re.I,
)


def _select_chapter(message: str, book: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve an explicit chapter number, otherwise an explicit chapter title."""
    chapters = book.get("chapters", [])
    match = _CHAPTER_NUMBER.search(message)
    if match:
        wanted = int(match.group(1))
        for chapter in chapters:
            if int(chapter.get("number", -1)) == wanted:
                return chapter
    folded = message.casefold()
    titled = [
        chapter for chapter in chapters
        if str(chapter.get("title", "")).casefold() in folded
    ]
    if titled:
        return max(titled, key=lambda item: len(str(item.get("title", ""))))
    return None


def answer_book_chapter(message: str, response_language: str = "EN") -> tuple[str, str, str] | None:
    """Return a complete deterministic chapter-outline answer when requested."""
    if not (_READ_INTENT.search(message) and _BOOK_INTENT.search(message)):
        return None
    books = local_knowledge.knowledge().get("books", [])
    if not books:
        return None
    book = books[0]
    chapter = _select_chapter(message, book)
    if chapter is None:
        # Never invent a chapter when the learner did not identify one.
        return None

    chichewa = str(response_language).upper() == "CH"
    number = chapter.get("number", "")
    title = chapter.get("title", "")
    pages = chapter.get("pages", "")
    authors = ", ".join(book.get("authors", []))
    citation = (
        f"{book.get('title', '')}: {book.get('subtitle', '')} "
        f"({book.get('edition', '')} ed., {book.get('year', '')}), {authors}. "
        f"{book.get('publisher', '')}. DOI: {book.get('doi', '')}."
    )
    url = str(book.get("url", ""))

    if chichewa:
        heading = f"## Chaputala {number} — {title}"
        source = f"**Gwero:** {citation}"
        chichewa_note = (
            f"**Chidule cha CRARA mu Chichewa (masamba {pages}):** "
            f"{chapter.get('scope_ny', '')}"
        )
        publisher_note = (
            f"**Zomwe zili m'bukuli malinga ndi wofalitsa (English, pp. {pages}):** "
            f"{chapter.get('scope_en', '')}"
        )
        about = f"**Za bukuli:** {str(book.get('scope_en', ''))[:420]}"
        link = f"**Pewerengera buku lonse:** {url}"
        honesty = (
            f"{book.get('access_note_ny', '')} CRARA yowerenga mndandanda wokha wa chaputala, "
            "osati malemba onse amene ali m'bukuli."
        )
    else:
        heading = f"## Chapter {number} — {title}"
        source = f"**Source:** {citation}"
        chichewa_note = (
            f"**Publisher's chapter outline (pages {pages}):** "
            f"{chapter.get('scope_en', '')}"
        )
        publisher_note = (
            f"**CRARA Chichewa study note:** {chapter.get('scope_ny', '')}"
        )
        about = f"**About the book:** {str(book.get('scope_en', ''))[:420]}"
        link = f"**Full text:** {url}"
        honesty = (
            f"{book.get('access_note_en', '')} CRARA has read the bundled chapter outline, "
            "not the licensed chapter text."
        )

    answer = "\n\n".join([heading, source, about, chichewa_note, publisher_note, link, honesty])
    return answer, PROVIDER, MODEL
