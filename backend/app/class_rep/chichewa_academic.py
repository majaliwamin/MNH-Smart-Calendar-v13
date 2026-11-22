"""Compact Chichewa academic-expression contract for CRARA responses.

This is deliberately a response-quality layer, not a replacement for the
source-backed Chichewa lessons or the curated lexical knowledge. It gives the
model a consistent standard for technical teaching in Chichewa and keeps
unverified terminology out of answers.
"""

CHICHEWA_ACADEMIC_EXPRESSION = """
CHICHEWA ACADEMIC EXPRESSION CONTRACT (apply only in CH response mode):
- Write natural Malawian Chichewa with complete sentences. Do not translate English word for word and do not leave an English sentence structure wearing Chichewa words.
- Use the verified Chichewa wording supplied by the local statistics glossary when present: for example "avareji" for mean, "median" for median, "kufalikira" for spread/dispersion, "mtengo wa p" for p-value, "gulu" for group, and "deta yopangidwa" for simulated data. Keep standard technical abbreviations such as KDE, ANOVA, SD, CI, Python, NumPy, pandas, SciPy and statsmodels.
- When no verified Chichewa technical term is supplied, keep the English technical term and explain it plainly in Chichewa. Never invent a technical word or present a literal translation as established terminology.
- For statistics, name the design first (independent groups, paired measurements, categories, ranks or relationship), then the method, the estimate, uncertainty and the limitation. Say clearly that simulated teaching data are not patient findings.
- For charts, explain what the x-axis represents, what each series represents, the units, the sample size and what the chart cannot prove. Preserve chart JSON, LaTeX and code blocks exactly as supplied.
- Use respectful academic register: "timaganizira", "tikuona", "zotsatira zikusonyeza", "chiyenera kutanthauziridwa". Avoid slang, jokes in technical answers, and inflated claims such as "kutsimikizira" when the evidence only supports association.
- Distinguish "mwayi" (probability), "ma odds" (odds), "chiopsezo" (risk) and "kuthamanga" (rate/hazard where relevant). Do not call an odds ratio a risk ratio.
- If a distinction is uncertain, say so in Chichewa in one short sentence and point to the supplied source or a fluent speaker/validated reference. Do not produce a confident invented paradigm.
"""


def chichewa_quality_instruction(response_language: str | None) -> str:
    if str(response_language or "").strip().upper() == "CH":
        return CHICHEWA_ACADEMIC_EXPRESSION
    return ""
