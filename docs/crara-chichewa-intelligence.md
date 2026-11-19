# CRARA Chichewa conversational intelligence

## What changed

CRARA no longer treats a Chichewa message as an English request with a
Chichewa-shaped answer, and no longer requires a single owner account to get a
Chichewa reply. The backend now runs four explicit stages before inference:

1. **Detect** `detect_language()` (CH/EN/MIXED from lexical evidence) and
   `detect_mode()` (converse, follow-up, explain, translate in either
   direction, academic) in `language_intelligence.py`.
2. **Ground** `linguistic_context()` in `linguistic_knowledge.py` retrieves
   only matching entries from `data/chichewa_lexicon.json`, each with source,
   part of speech, grammar, example, verification status and confidence.
3. **Generate** `assistant.reply()` injects a short mode contract, the
   retrieved evidence and only mode-relevant prompt sections. The 16 KB
   always-on curriculum block was removed from ordinary turns. History now
   keeps the last 10 turns.
3b. **Refuse invented meanings**: an expression-meaning question about a
   headword with no curated entry and no retrieved passage containing it is
   answered with a request for the full sentence, never sent to the model.

4. **Validate** `output_validation.py` applies independent rule checks
   (language match, banned templates, unsupported verification claims,
   unbalanced LaTeX, repetition, truncation). A failure triggers one bounded
   regeneration with the specific defect; a second failure returns a short
   honest limitation in the selected language.

`routes.chat()` resolves the response language from an explicit saved
preference, the translation target, or detected Chichewa input — in that
order. Users without a saved preference are no longer forced into English.

## Casual expressive layer

`expressive_style.py` adds a deliberately narrow social register. `detect_tone()`
separates playful, warm, distressed and neutral messages; the emoji palette,
clean joke candidates and informal phrasing are injected only when `detect_mode()`
returns `converse`/`followup` **and** the tone is not distressed. Academic,
translation, expression-meaning, biomedical and maternal/neonatal answers never
receive emojis, jokes or slang. Curated morning/afternoon greeting answers get a
single restrained emoji; the palette includes facial expressions (including 🤣,
😂, 😭 and 😐), microbiology (🦠 🧬 🔬 🧫), maternal/neonatal (🤰 👶 🍼 🩺) and
stationery/learning (📝 📚) symbols. Chichewa informal forms are limited to the
verified standard greetings already present in the curated lessons; CRARA does
not invent regional slang or Chichewa jokes. Jokes are English-only, come from a
fixed non-clinical library, and never target health, bodies, pregnancy, babies,
identity or distress. An explicit Chichewa joke request gets an honest curated
reply, and rule-based validation rejects any model-generated Chichewa joke in a
social turn.

## Resources actually indexed

Present and structured: the 13 lesson Markdown files under
`docs/crara-chichewa-lessons/` plus `docs/crara-chichewa-curriculum.md`, from
which 50+ curated entries were transcribed into the JSON lexicon. Run
`python backend/scripts/index_chichewa_language_resources.py` once against a
persistent database to add those files to the shared document index; the
script is idempotent (`source_id` = `chichewa-language-reference:<filename>`).

Referenced but **not** present in this repository, therefore not indexed and
not claimed as evidence: the 2011 *Chichewa from English* guide, the historical
Chinyanja/Chicewa dictionary, the MLW *Medical Terms – Mawu a za Chipatala*
dictionary, the MIE syllabuses, and the Peace Corps/USAID materials. If they
are uploaded through the normal resource endpoints, `search_documents()` can
retrieve them, but their titles/pages must appear in the retrieved passages
before CRARA may cite them.

## Verification semantics

- `source-transcribed`: the form is printed in the cited lesson, which itself
  cites the supplied guide. This is not a contemporary dictionary verification.
- `curated-high-confidence`: high-confidence everyday usage already curated in
  `lexical_reference.py` (for example `malungo` = malaria, greetings).
- `policy-backed-loanword`: an internationally recognised term that should be
  retained rather than given an invented Chichewa equivalent (for example
  `rickets`, `preeclampsia`).
- `requires-native-review` / `unverified-damaged-source`: never presented as an
  established fact. `zenera`/`windo` are recorded as legitimate variants, not
  as one correct and one wrong form. `matewe` has no entry and must not acquire
  a confident definition.

Tests requiring native-speaker judgement are marked
`native_speaker_review` and skipped; they are not counted as language validation.
