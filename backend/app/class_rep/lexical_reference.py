"""High-confidence lexical grounding for common Chichewa expressions.

Keep this reference deliberately small: only add entries supported by reliable
Malawian usage or supplied reference material. Unknown words are not guessed.
"""
import re

_ENTRIES = {
    "malungo": (
        "CHICHEWA LEXICAL REFERENCE — authoritative correction: "
        "'malungo' means malaria (the illness) in ordinary Malawian Chichewa. "
        "It does NOT mean relatives, family members, kin, elders, or a village group. "
        "Do not invent idioms or examples that assign it those meanings. "
        "If the user asks 'malungo ndi chani?', explain that it means malaria. "
        "If discussing fever generally, distinguish malungo (malaria) from a fever "
        "as a symptom; do not claim they are interchangeable in every context."
    ),
    "mwaswera": (
        "CHICHEWA GREETING REFERENCE: 'Mwaswera bwanji?' is an afternoon greeting "
        "(roughly, 'How has your afternoon been?'). A natural concise reply is "
        "'Ndaswera bwino, zikomo. Nanga inu?' ('I have had a good afternoon, thank you. And you?'). "
        "Do not answer every greeting with a generic self-introduction."
    ),
}

def lexical_reference_context(message: str) -> str:
    """Return only matching curated lexical notes; never infer unknown definitions."""
    text = str(message or "").casefold()
    notes = []
    for key, note in _ENTRIES.items():
        if re.search(r"(?<![\w])" + re.escape(key) + r"(?![\w])", text):
            notes.append(note)
    return "\n".join(notes)


def direct_malungo_definition_answer(message: str, response_language: str = "EN") -> str | None:
    """Answer a direct definition question deterministically, bypassing model drift."""
    text = str(message or "").casefold().strip()
    if len(text) > 180 or not re.search(r"(?<![\\w])malungo(?![\\w])", text):
        return None
    asks_meaning = re.search(
        r"\\b(chani|chiyani|tanthauzo|meaning|means|what\\s+(?:is|does))\\b",
        text,
    )
    if not asks_meaning:
        return None
    if str(response_language or "").upper() == "CH":
        return (
            "**Malungo** amatanthauza **matenda a malungo (malaria)**. "
            "Si mawu otanthauza achibale kapena anthu a m’banja. "
            "Malungo amayamba chifukwa cha tizilombo ta *Plasmodium*, "
            "tomwe nthawi zambiri timafalikira munthu akalumidwa ndi udzudzu "
            "wonyamula tizilomboti."
        )
    return (
        "**Malungo** is the Chichewa term for **malaria**, an illness caused by "
        "*Plasmodium* parasites, usually transmitted through the bite of an "
        "infected female *Anopheles* mosquito. It does not mean relatives or kin."
    )
