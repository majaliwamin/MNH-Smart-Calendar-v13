"""Dedicated English <-> Chichewa translation and interpretation engine.

This layer does not pretend to be a trained translation model. It routes bilingual
requests through the shared CRARA reference index, applies source hierarchy and
meaning-preservation rules, and supplies a strict task contract to the language model.
"""
import re
from typing import Callable

_TRANSLATION_INTENT = re.compile(
    r"\b(?:translate|translation|interpret|interpretation|meaning|means|define|"
    r"how\s+do\s+you\s+say|how\s+to\s+say|equivalent|"
    r"translate\s+into|in\s+chichewa|in\s+english|"
    r"english\s+(?:to|into)\s+chichewa|chichewa\s+(?:to|into)\s+english)\b",
    re.I,
)
_CHICHEWA_MEANING = re.compile(
    r"\b(?:ndi\s+chani|ndi\s+chiyani|amatanthauza|tanthauzo\s+la|"
    r"zikutanthauza\s+chiyani|mawu\s+akuti)\b",
    re.I,
)
_LANGUAGE_CUE = re.compile(
    r"\b(?:chichewa|chinyanja|chewa|english|chingerezi)\b", re.I
)

TRANSLATION_ENGINE_INSTRUCTIONS = """
DEDICATED ENGLISH <-> CHICHEWA TRANSLATION AND INTERPRETATION ENGINE
You are handling bilingual language work, not merely answering a general question.

TASK ROUTING
- Identify source language, target language, task (translation, interpretation, explanation,
  terminology lookup, or conversational meaning) and register from the actual request.
- Translate English to natural Malawian Chichewa and Chichewa to clear natural English.
- If the user asks what a Chichewa expression means, explain its meaning in the selected
  response language. If the user asks how to say an English expression in Chichewa, give
  the Chichewa expression first, then a concise literal/back-translation and usage note.
- If direction is not explicit, infer it from the quoted/source text and requested target;
  do not translate the request itself by mistake.
- Preserve the speaker's intent, tense/aspect, negation, modality, politeness, emphasis,
  uncertainty, number, person, and relationships. Do not add or remove meaning.
- Offer both a natural idiomatic rendering and a literal gloss only when that distinction
  helps explain a difficult expression. Label them clearly.
- Preserve names, numbers, dates, units, abbreviations and technical symbols.

SOURCE HIERARCHY AND EVIDENCE
1. Exact entries/passages retrieved from the supplied MLW Medical Terms – Mawu a za
   Chipatala dictionary are the preferred authority for medical and biomedical terminology.
2. Use supplied contemporary Chichewa grammar, dictionaries and Malawi Institute of
   Education syllabuses for general vocabulary, morphology, syntax and register.
3. Treat the 2011 phrase guide and historical Chinyanja dictionary as secondary/historical
   references only. They contain dated, inconsistent or questionable examples; never
   silently promote those examples to standard contemporary usage.
4. Treat CRARA's curated lexical reference as binding for entries it explicitly covers.
5. Model knowledge is a fallback, not evidence. If references conflict, explain the conflict
   and prefer the stronger, more relevant source; do not invent a consensus.

MEDICAL AND BIOMEDICAL TRANSLATION
- Use the MLW dictionary's standard, culturally adapted terminology where a retrieved entry
  supports it. It covers multiple disciplines; do not restrict it to maternal/neonatal health.
- Keep internationally recognised English terms in parentheses when a Chichewa phrase is
  descriptive, potentially ambiguous, or less familiar to the audience.
- Distinguish a disease from a symptom, a procedure from an outcome, and a risk from a
  confirmed event. Preserve diagnostic uncertainty and scientific hedging.
- Do not replace a technical term with an oversimplified phrase that changes its clinical
  meaning. Explain the concept in plain Chichewa when needed.
- For consent, participant information and public engagement, prioritise comprehension,
  cultural appropriateness, respect and non-stigmatising language.
- Do not invent a Chichewa technical equivalent. State that the reference has not verified
  one, retain the English term, and explain it accurately.

QUALITY CONTROL
Before returning a translation, internally check: semantic completeness, grammar,
idiomatic naturalness, register, terminology consistency, negation, tense/aspect, and
whether the target text introduces unsupported claims.
- Distinguish standard, colloquial, regional and historical forms when evidence supports it.
- Do not claim a word is unknown merely because it is absent from one retrieved passage.
  Say that the available reference did not verify it.
- For ambiguous short expressions, give only a cautious likely interpretation if supported;
  otherwise state the ambiguity and ask for the surrounding sentence only when necessary.
- Never fabricate etymology, dialect distribution, cultural history, example sentences or
  dictionary citations.
- Cite retrieved material with its exact title and page when available. Do not invent page
  numbers. Keep original and translated text separate.
- Return the translation itself first. Keep commentary proportionate to the request.
"""

def is_translation_or_interpretation_request(message: str) -> bool:
    """Detect explicit bilingual and meaning requests without hijacking ordinary chat."""
    text = str(message or "").strip()
    if not text:
        return False
    return bool(
        _TRANSLATION_INTENT.search(text)
        or _CHICHEWA_MEANING.search(text)
        or re.search(r"\b(?:what\s+does\s+.+\s+mean|meaning\s+of)\b", text, re.I)
    )


def build_translation_reference_context(
    message: str,
    owner_id: str = "shared",
    search: Callable | None = None,
) -> str:
    """Retrieve bilingual source passages using the existing owner-scoped document index."""
    if not is_translation_or_interpretation_request(message):
        return ""
    if search is None:
        from app.class_rep.documents import search_documents
        search = search_documents

    queries = [str(message or "").strip()[:1000]]
    # Add direction-aware lexical searches so a phrase is not missed just because
    # the source sentence and the dictionary's headword use different word forms.
    if re.search(r"\b(?:medical|clinical|biomedical|research|scientific|health)\b", message, re.I):
        queries.append("English Chichewa medical biomedical terminology " + message[:500])
    if _CHICHEWA_MEANING.search(message):
        queries.append("Chichewa English dictionary meaning " + message[:500])

    collected = []
    seen = set()
    for query in queries[:3]:
        try:
            passages = search(query, limit=4, owner_id=owner_id) or []
        except Exception:
            # Retrieval failure must not break ordinary conversation. The model is
            # explicitly told below that no source passage was verified.
            continue
        for passage in passages:
            if not isinstance(passage, dict):
                continue
            key = (passage.get("title"), passage.get("page"), passage.get("text"))
            if key in seen:
                continue
            seen.add(key)
            collected.append(passage)
            if len(collected) >= 8:
                break
        if len(collected) >= 8:
            break

    if not collected:
        return (
            "No matching passage was retrieved from CRARA's currently indexed reference "
            "documents for this request. Do not claim that a dictionary verified the answer. "
            "Use established language knowledge cautiously and disclose uncertainty."
        )
    lines = []
    for item in collected:
        title = str(item.get("title") or "Untitled reference")[:180]
        page = item.get("page")
        page_label = "page " + str(page) if page is not None else "page not recorded"
        text = str(item.get("text") or "")[:1800]
        lines.append(f"SOURCE: {title}, {page_label}\n{text}")
    return "\n\n".join(lines)
