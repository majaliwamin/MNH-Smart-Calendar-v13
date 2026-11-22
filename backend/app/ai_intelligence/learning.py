"""Relevance-scoped retrieval of verified corrections for future answers."""
from __future__ import annotations

import re
from collections import Counter

from app.ai_intelligence import corrections

_WORD_RE = re.compile(r"[a-z0-9]{3,}")
_MAX_CANDIDATES = 120


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(str(text or "").casefold()))


def relevant_examples(query: str, category: str | None = None, limit: int = 6) -> list[dict]:
    """Return only the most relevant accepted examples, never the full history."""
    wanted = _tokens(query)
    entity = set(_WORD_RE.findall(str(category or "").casefold()))
    scored = []
    for item in corrections._read_all(corrections.COL_EXAMPLES, _MAX_CANDIDATES):
        if item.get("verification_status") != "verified" or item.get("learning_status") not in (None, "accepted"):
            continue
        haystack = " ".join(str(item.get(key, "")) for key in ("question", "expected_response", "date_or_entity"))
        overlap = len(wanted & _tokens(haystack))
        if entity and str(item.get("category", "")) == str(category).strip().casefold():
            overlap += 3
        if overlap <= 0:
            continue
        scored.append((overlap, item))
    scored.sort(key=lambda pair: (-pair[0], str(pair[1].get("created_at", ""))), reverse=False)
    return [
        {
            "question": str(item.get("question", ""))[:1000],
            "expected_response": str(item.get("expected_response", ""))[:2000],
            "category": str(item.get("category", "other")),
            "verification_status": "verified",
            "date_or_entity": str(item.get("date_or_entity", ""))[:200],
        }
        for _, item in scored[:max(1, min(int(limit), 10))]
    ]


def operational_rules() -> list[str]:
    """Convert repeated verified corrections into short, bounded answer rules."""
    feedback = corrections._read_all(corrections.COL_FEEDBACK, _MAX_CANDIDATES)
    counts = Counter(
        (str(item.get("category", "other")), str(item.get("date_or_entity", "")))
        for item in feedback
        if item.get("verification_status") == "verified" and item.get("recurring")
    )
    rules = []
    for (category, entity), count in counts.most_common(8):
        label = entity or "this timetable"
        rules.append(
            f"This correction has recurred {count} times for {label} ({category}); "
            "state every retrieved session and never omit a scheduled item."
        )
    return rules
