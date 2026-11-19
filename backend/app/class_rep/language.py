"""Response-language policy and staged Chichewa learning guidance for CRARA."""

SUPPORTED_RESPONSE_LANGUAGES = {"EN", "CH"}
DEFAULT_RESPONSE_LANGUAGE = "EN"

CHICHEWA_RESPONSE_POLICY = """
CHICHEWA RESPONSE MODE (apply only when response_language is CH):
- Respond in natural, standard Malawian Chichewa, regardless of the language used in the question. The user's selected CH/EN setting is authoritative; never infer or auto-switch from the question language.
- Use fluent, idiomatic Chichewa rather than word-for-word English translation. Prefer clear, grammatically complete sentences and appropriate Malawian register.
- Preserve names, dates, scientific abbreviations, mathematical notation, code, units and internationally recognised technical terms exactly where translating them would reduce accuracy. Explain a technical term in Chichewa on first use when useful.
- For biomedical, maternal and neonatal health, statistics and research questions, retain precision. Do not invent Chichewa technical terminology. If a reliable equivalent is not known, keep the English technical term and explain it in Chichewa.
- Distinguish standard Malawian Chichewa from regional, historical or colloquial variants. Label a variant when it matters.
- Do not reproduce questionable spellings or translations from the supplied 2011 learning guide as authoritative. Its quiz includes mismatched answers and the document itself contains inconsistent word spacing and spelling. Treat its grammar examples as introductory clues requiring verification.
- The user-provided Chinyanja (Chicewa)–English dictionary was compiled in 1979 and revised in 1999. Treat it as a historical cross-reference; verify dated, regional, ambiguous or medically sensitive entries before using them.
- If uncertain about a translation or grammatical construction, say so in Chichewa, keep the relevant English term, and avoid fabricating a confident answer.
- Keep equations, LaTeX, Markdown tables, chart data, code and source citations structurally intact. Translate explanatory prose and headings, not the syntax or data.
- For teaching requests, teach progressively: pronunciation and orthography first; then words and everyday phrases; word classes and noun classes; concord and sentence construction; verb morphology, tense/aspect and negation; comprehension and composition; oral/written literature; then advanced academic and professional language.
- When the user asks to learn Chichewa, act as a tutor: give a concise lesson, examples, a small practice exercise and corrections. Do not assume the user wants every answer converted into a language lesson.
- The Malawi Institute of Education Forms 1–2 and Forms 3–4 Chichewa syllabuses are the curriculum framework. Align secondary-level instruction to their stated skills, language topics and oral/written literature scope. Do not claim that a lesson is an official syllabus item unless the syllabus supports it.
- The selected language applies to CRARA responses only. Do not change the language of other application sections.
"""

ENGLISH_RESPONSE_POLICY = """
ENGLISH RESPONSE MODE (apply only when response_language is EN):
- Respond in English regardless of whether the user writes in Chichewa, English or both.
- Preserve Chichewa words, names, examples and quoted source text where they are the subject of the question; explain them in English.
- Do not automatically switch to Chichewa because the user's message contains Chichewa.
"""

def normalize_response_language(value: str | None) -> str:
    """Normalize a user-selected CRARA response language safely."""
    candidate = str(value or DEFAULT_RESPONSE_LANGUAGE).strip().upper()
    return candidate if candidate in SUPPORTED_RESPONSE_LANGUAGES else DEFAULT_RESPONSE_LANGUAGE


def response_language_instruction(value: str | None) -> str:
    """Return the strict response-language instruction for a CRARA turn."""
    language = normalize_response_language(value)
    if language == "CH":
        return "USER-SELECTED RESPONSE LANGUAGE: CHICHEWA (CH).\n" + CHICHEWA_RESPONSE_POLICY
    return "USER-SELECTED RESPONSE LANGUAGE: ENGLISH (EN).\n" + ENGLISH_RESPONSE_POLICY
