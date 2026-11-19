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



def direct_chichewa_conversation_answer(
    message: str, response_language: str = "EN", history: list[dict] | None = None
) -> str | None:
    """Handle a small set of high-confidence everyday exchanges without model improvisation."""
    text = re.sub(r"[!?.,]+$", "", str(message or "").strip().casefold())
    lang = str(response_language or "EN").upper()

    # Accept the common abbreviated chat spelling "bwanj" without repeating it.
    if re.fullmatch(r"(?:mwadzuka|mwauka)\s+bwanj(?:i)?", text):
        if lang == "CH":
            return "Tadzuka bwino, zikomo. Inu mwadzuka bwanji?"
        return "That is a morning greeting meaning “How did you wake up?” A natural reply is “Tadzuka bwino, zikomo.”"

    if re.fullmatch(r"(?:moni|hello|hi|muli\s+bwanj(?:i)?)", text):
        if lang == "CH":
            return "Moni! Muli bwanji?"
        return "Hello! How are you?"

    if re.fullmatch(r"(?:eya|inde|inde\s+ndithu)", text):
        previous = " ".join(
            str(item.get("content", "")) for item in (history or [])[-3:]
            if item.get("role") == "assistant"
        ).casefold()
        if any(phrase in previous for phrase in (
            "nditha kukuthandizani", "ndingakuthandizeni", "mukhoza kundifunsira",
            "how can i help", "what can i help"
        )):
            return (
                "Chabwino. Ndi nkhani iti imene mukufuna tikambirane?"
                if lang == "CH" else
                "Of course. What would you like us to talk about?"
            )
    return None

def direct_malungo_definition_answer(message: str, response_language: str = "EN") -> str | None:
    """Answer a direct definition question deterministically, bypassing model drift."""
    text = str(message or "").casefold().strip()
    if len(text) > 180 or not re.search(r"(?<![\w])malungo(?![\w])", text):
        return None
    asks_meaning = re.search(
        r"\b(chani|chiyani|tanthauzo|meaning|means|what\s+(?:is|does))\b",
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


def unverified_chichewa_term_answer(message: str, response_language: str = "EN") -> str | None:
    """Decline to guess at a short, unsupported Chichewa word-meaning follow-up."""
    text = str(message or "").casefold().strip()
    if len(text) > 100:
        return None
    match = re.fullmatch(r"([a-zA-ZÀ-ž’'-]+)\s+(?:nanga|ndi\s+chani|ndi\s+chiyani)\??", text)
    if not match:
        return None
    term = match.group(1).casefold()
    if term in _ENTRIES:
        return None
    if str(response_language or "").upper() == "CH":
        return (
            f"Pakadali pano ndilibe umboni wokwanira wotsimikizira tanthauzo la mawu akuti **{term}**. "
            "Sindikufuna kungoyerekezera kapena kukupatsani tanthauzo lolakwika. "
            "Chonde mundipatse chiganizo kapena mmene mawuwa agwiritsidwira ntchito."
        )
    return (
        f"I don't yet have a sufficiently verified Chichewa reference for **{term}**. "
        "I don't want to guess or give you an invented definition. "
        "Please share the sentence or context in which you heard it so I can help assess it."
    )
