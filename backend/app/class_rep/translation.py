"""Dedicated English <-> Chichewa translation and interpretation engine.

This is an AI-assisted engine grounded by a small, traceable MLW terminology
reference. It does not pretend that a finite glossary is a complete dictionary.
"""
import re
from app.class_rep.providers import complete

LANGUAGES = {"EN": "English", "CH": "Chichewa"}
REGISTERS = {"casual", "neutral", "professional", "clinical", "academic"}

# Traceable terms transcribed selectively from the user-supplied MLW dictionary.
# Page numbers refer to the printed page numbers in Medical Terms – Mawu a za Chipatala.
MEDICAL_GLOSSARY = [
    {"en": "abdomen", "ch": "mimba", "page": 10, "domain": "anatomy"},
    {"en": "abdominal cavity", "ch": "mpata wa mkati mwa mimba; mphako ya m’mimba", "page": 10, "domain": "anatomy"},
    {"en": "abdominal pain", "ch": "ululu wa m’mimba; kupweteka kwa m’mimba", "page": 10, "domain": "symptoms"},
    {"en": "abortion", "ch": "kuchotsa mimba; kuchotsa pakati; kuchotsa pathupi; kutaya mimba", "page": 10, "domain": "reproductive health"},
    {"en": "abortion care", "ch": "chisamaliro chimene munthu amalandira akachotsa mimba kapena akapititsa padera", "page": 11, "domain": "reproductive health"},
    {"en": "placental abruption", "ch": "kuchoka kwa nsengwa mosayembekezereka", "page": 11, "domain": "obstetrics"},
    {"en": "abscess", "ch": "chotupa/chithupsya cha mafinya cha pa khungu choyambitsidwa ndi kachirombo ka bakiteriya", "page": 11, "domain": "infectious disease"},
    {"en": "absorption", "ch": "kulowa kwa chakudya m’magazi kuti chikagwire ntchito m’thupi", "page": 11, "domain": "physiology"},
    {"en": "acidosis", "ch": "kuchuluka kwa asidi m’thupi; kuchuluka kwa asidi m’madzi ndi magazi a m’thupi kopyola muyezo", "page": 11, "domain": "pathophysiology"},
    {"en": "acute illness", "ch": "kudwala kwambiri; kudwala kwa kayaya; matenda odza mwadzidzidzi ndi mwa mphamvu", "page": 12, "domain": "clinical medicine"},
    {"en": "cardiovascular system", "ch": "ndondomeko ya kayendedwe ka magazi kuchokera ku mtima kukafikira ku ziwalo zonse za thupi", "page": 31, "domain": "cardiology"},
    {"en": "cartilage", "ch": "mnofu wofewa woterera umene umapezeka polumikizana mafupa kuti mafupa asakhulane", "page": 31, "domain": "anatomy"},
    {"en": "genes", "ch": "majini; zotengera ku mtundu", "page": 61, "domain": "genetics"},
    {"en": "genetic", "ch": "khudzana ndi majini komanso DNA", "page": 61, "domain": "genetics"},
    {"en": "genetic variation", "ch": "kusiyana kwa dongosolo la zigawo za DNA kapena majini", "page": 61, "domain": "genetics"},
    {"en": "genotype", "ch": "zotengera kumtundu", "page": 61, "domain": "genetics"},
    {"en": "genital warts", "ch": "mauka; njerewere za ku maliseche", "page": 61, "domain": "sexual health"},
    {"en": "parasite", "ch": "kachirombo komwe kamayambitsa matenda komwe kamakhala pa chinthu cha moyo", "page": 101, "domain": "parasitology"},
    {"en": "patient", "ch": "wodwala", "page": 101, "domain": "clinical care"},
    {"en": "pelvis", "ch": "mafupa a m’munsi mwa chiuno, pomwe pamalumikizana mitendo ndi thunthu", "page": 101, "domain": "anatomy"},
    {"en": "penicillin", "ch": "mankhwala a antibiotiki", "page": 101, "domain": "pharmacology"},
    {"en": "peritonitis", "ch": "kutupa kwa mimba koyambitsidwa ndi vuto la m’mimba", "page": 101, "domain": "gastroenterology"},
    {"en": "HIV", "ch": "kachirombo koyambitsa HIV; kachirombo ka vairasi kochepetsa chitetezo cha m’thupi la munthu", "page": 141, "domain": "infectious disease"},
    {"en": "HIV testing and counselling", "ch": "kuyeza ndi kupereka uphungu wa HIV", "page": 141, "domain": "public health"},
    {"en": "maternal and neonatal health", "ch": "umoyo wa amayi wokhudzana ndi ubereki ndi ana obadwa kumene", "page": 142, "domain": "maternal and neonatal health"},
    {"en": "maternal mortality ratio", "ch": "chiwerengero cha amayi omwalira chifukwa cha ubereki pachaka", "page": 141, "domain": "public health"},
    {"en": "magnetic resonance imaging", "ch": "njira yojambula mkati mwa thupi la munthu ndi makina a maginito", "page": 142, "domain": "radiology"},
    {"en": "mother-to-child transmission", "ch": "mayi kupatsira mwana kachirombo ka HIV pamene akubereka", "page": 142, "domain": "infectious disease"},
    {"en": "reproductive health", "ch": "uchembere wabwino", "page": 143, "domain": "reproductive health"},
    {"en": "sexual and reproductive health", "ch": "uchembere ndi ubereki wabwino", "page": 143, "domain": "reproductive health"},
    {"en": "sexually transmitted infections", "ch": "matenda opatsirana pogonana", "page": 143, "domain": "infectious disease"},
    {"en": "traditional birth attendant", "ch": "mzamba", "page": 144, "domain": "maternal health"},
]

def detect_language(text: str) -> str:
    """Conservative heuristic; return AUTO when a short phrase is ambiguous."""
    words = set(re.findall(r"[a-zA-Z']+", (text or "").casefold()))
    chichewa_markers = {"ndili", "ndikufuna", "muli", "bwanji", "chiyani", "chani",
                        "chonde", "zikomo", "ndikudziwa", "sindikudziwa", "tiku",
                        "akubwera", "ndinapita", "mwaswera", "mawa", "lero", "ayi"}
    english_markers = {"the", "and", "is", "are", "was", "were", "what", "why",
                       "how", "please", "translate", "explain", "means", "meaning"}
    ch_score = len(words & chichewa_markers)
    en_score = len(words & english_markers)
    if ch_score >= 1 and ch_score > en_score:
        return "CH"
    if en_score >= 1 and en_score > ch_score:
        return "EN"
    return "AUTO"

def glossary_matches(text: str, limit: int = 12) -> list[dict]:
    """Return longest exact phrase matches from the traceable MLW term subset."""
    normalized = re.sub(r"[^a-z0-9]+", " ", (text or "").casefold()).strip()
    matches = []
    for entry in MEDICAL_GLOSSARY:
        terms = [entry["en"]]
        terms.extend(part.strip() for part in re.split(r"[;/]", entry["ch"]) if len(part.strip()) >= 8)
        if "wodwala" in entry["ch"].casefold():
            terms.append("wodwala")
        matched = any(
            re.search(
                r"(?<![a-z0-9])" +
                re.escape(re.sub(r"[^a-z0-9]+", " ", term.casefold()).strip()) +
                r"(?![a-z0-9])",
                normalized,
            )
            for term in terms
        )
        if matched:
            matches.append(entry)
    return sorted(matches, key=lambda item: len(item["en"]), reverse=True)[:limit]

def glossary_context(text: str) -> str:
    matches = glossary_matches(text)
    if not matches:
        return "No exact MLW glossary entry matched. Do not invent a dictionary citation or force a technical equivalent."
    return "\n".join(
        f'- {item["en"]} = {item["ch"]} (MLW, Medical Terms – Mawu a za Chipatala, printed p. {item["page"]}; domain: {item["domain"]}).'
        for item in matches
    )

def is_translation_request(message: str) -> bool:
    text = (message or "").casefold()
    return bool(re.search(
        r"\b(translate|translation|interpret|interpretation|in chichewa|into chichewa|into english|"
        r"from chichewa|from english|what does .+ mean in english|how do you say)\b", text
    ))

def translation_instruction(source_language: str = "AUTO", target_language: str = "AUTO",
                             register: str = "neutral", domain: str = "general",
                             mode: str = "translate", glossary: str = "") -> str:
    source = LANGUAGES.get(source_language, "the language detected from the source text")
    target = LANGUAGES.get(target_language, "the language explicitly requested by the user")
    register = register if register in REGISTERS else "neutral"
    mode = mode if mode in {"translate", "interpret"} else "translate"
    task = "Translate faithfully" if mode == "translate" else "Interpret the meaning, intent, tone and context, then provide a faithful translation"
    return f"""
DEDICATED BIDIRECTIONAL ENGLISH–CHICHEWA ENGINE
Task: {task}.
Source language: {source}. Target language: {target}.
Register: {register}. Domain: {domain or "general"}.

Rules:
- Determine the actual source language from the supplied text when AUTO is specified. Do not infer language from the user's response-language preference.
- Preserve meaning, tense, aspect, negation, questions, politeness, speaker perspective, quantities, dates, names, abbreviations and uncertainty.
- Produce natural, idiomatic Malawian Chichewa, not word-for-word English. Equally, render Chichewa into clear natural English without flattening idioms or culturally meaningful intent.
- Use context to resolve polysemy. If a word or sentence is ambiguous, state the plausible readings briefly instead of fabricating certainty.
- Retain established English loanwords and adapted scientific terms when they are clearer and commonly used; add a concise Chichewa explanation where useful. Do not force unfamiliar literal translations.
- For medical/biomedical content, preserve the exact clinical/scientific concept, anatomy, causality, severity, timing and negation. Never turn association into causation or a non-significant result into no effect. Do not add clinical advice.
- Prefer the supplied MLW terminology where an exact entry matches. The glossary is a terminology aid, not permission to force an unsuitable phrase into a different context.
- Do not claim a term appears in MLW unless it is present in the supplied glossary context below. Cite only its printed page supplied there.
- For interpretation, distinguish literal wording from intended meaning when they differ. Explain regional or register variation only when supported; do not invent regional claims.
- If a source phrase is incomplete, misspelled or too ambiguous to translate safely, provide the best bounded interpretation and identify the uncertainty. Do not hallucinate a dictionary definition.
- Output the requested translation first. Add a short note only when it materially helps explain ambiguity, terminology or register.
- Do not introduce CRARA, greet unnecessarily, teach a lesson, or append unrelated assistance.

TRACEABLE MLW TERMINOLOGY SUBSET:
{glossary or "No exact MLW glossary entry matched."}
"""

def translate_text(text: str, source_language: str = "AUTO", target_language: str = "AUTO",
                   register: str = "neutral", domain: str = "general",
                   mode: str = "translate") -> tuple[str, str, str]:
    if not str(text or "").strip():
        raise ValueError("Text to translate is required.")
    source_language = source_language.upper()
    target_language = target_language.upper()
    if source_language not in {"EN", "CH", "AUTO"} or target_language not in {"EN", "CH", "AUTO"}:
        raise ValueError("Languages must be EN, CH or AUTO.")
    if source_language == "AUTO":
        detected = detect_language(text)
        if detected != "AUTO":
            source_language = detected
    if target_language == "AUTO" and source_language in {"EN", "CH"}:
        target_language = "CH" if source_language == "EN" else "EN"
    system = translation_instruction(source_language, target_language, register, domain,
                                      mode, glossary_context(text))
    answer, provider, model = complete([
        {"role": "system", "content": system},
        {"role": "user", "content": str(text).strip()[:4000]},
    ])
    return answer, provider, model
