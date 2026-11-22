"""Build the STAT 8100 notebook and the searchable HTML companion."""

from __future__ import annotations

import html
import json
from pathlib import Path

import nbformat as nbf

from stat8100_code_cells import CODE, QUESTION_CODE, QUESTION_TITLES
from stat8100_guides import GUIDES
from stat8100_reporting import work_report, worked_template_examples

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "frontend" / "resources"
NOTEBOOK_PATH = RESOURCE_DIR / "stat8100_biostatistics_epidemiology_practical.ipynb"
HTML_PATH = RESOURCE_DIR / "stat8100_practical_companion.html"
RESULTS_PATH = RESOURCE_DIR / "stat8100_practical_results.json"

BUILD_LABEL = "STAT 8100 · Lectures 1–6 · simulated teaching datasets"
DATA_HASHES = {
    "anc_cohort.csv": "EE9D58D5E484D62244B62E17910AEDE241B074B4E7F70D22C783F50DD6E9E1DA",
    "bp_paired.csv": "677B7643994C0C57CE9FA2C052EEB22086D5B20537E5D8FE1290A98B3AFEF786",
    "postpartum_survival.csv": "0099FFCFCC226141DD762E6ABD338343325DC360A8011FFC571CAB06AC332EF2",
}

AUDIT_FACTS = [
    ("All three CSVs load successfully.",
     "anc_cohort.csv is 400×14, bp_paired.csv is 60×3 and postpartum_survival.csv is 500×6."),
    ("Required columns are present.",
     "No expected analysis variable is absent. bp_paired.csv also contains an id column, which is useful for confirming the pairing."),
    ("Missingness is variable-specific.",
     "ANC: education 55, bmi 10, hb 18, anaemia 18; all other ANC variables complete. BP and survival datasets have no missing values."),
    ("Education uses a literal category name.",
     "The 55 'None' values are a real education level, not missing data. The loader uses keep_default_na=False so pandas does not silently convert them to NaN."),
    ("Binary coding is consistent.",
     "iptp3 uses Yes/No; preterm, low_bw and readmitted use 1/0 with the meanings stated in the practical."),
    ("Anaemia and low birth weight are internally consistent.",
     "(hb < 11) matches anaemia for all 382 evaluable records; (birthweight < 2500) matches low_bw for all 400 records."),
    ("Preterm has a documented definition discrepancy.",
     "Nine records have gest_age between 36.1 and 36.8 weeks but preterm = 0. The supplied preterm flag is used as the primary outcome; interpret it as the recorded clinical flag, not an exact recoding of decimal gest_age."),
    ("No duplicate identifiers or duplicate rows were found.",
     "ANC ids W001–W400, BP ids B01–B60 and survival ids P001–P500 are unique."),
    ("Outliers are plausible and retained.",
     "Gestational age has a left tail, birthweight has a few low/high IQR outliers and BP has a few extreme measurements. They are inspected, not deleted."),
    ("These are simulated teaching data.",
     "They are not real patient records and must not be used for clinical or public-health decisions."),
]

QUESTION_ORDER = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10"]
SUBQUESTION_ORDER = list(GUIDES.keys())


def _md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(out)


def navigation_rows(question_id):
    rows = []
    for qid in SUBQUESTION_ORDER:
        if qid.split("(")[0] != question_id and not (
            question_id == "Q1" and qid.startswith("Q1")
        ):
            pass
        # Match Q1a/Q1b to Q1, Q10a to Q10, etc.
        prefix = qid[:len(question_id)]
        if prefix != question_id or (len(qid) > len(question_id) and qid[len(question_id)].isdigit()):
            continue
        guide = GUIDES[qid]
        code_cell = QUESTION_CODE[qid]
        code_text = "See code cell " + ", ".join(code_cell) if code_cell else "Not required — conceptual/interpretation task."
        rows.append([
            qid,
            guide["requirement"],
            guide["classification"],
            guide["jupyter_action"],
            code_text,
            guide["output_to_inspect"],
            guide["interpretation"],
            guide["reporting"],
        ])
    return rows


def question_slug(question_id):
    return question_id.lower()


def parent_question(subquestion_id):
    """Return Q10 for Q10a-f, otherwise the two-character parent question."""
    return "Q10" if subquestion_id.startswith("Q10") else subquestion_id[:2]


def guide_markdown(qid, results):
    guide = GUIDES[qid]
    report = work_report(qid, results)
    lines = [f"#### {qid} — {guide['title']}", ""]
    lines.append(f"**Practical requirement.** {guide['requirement']}")
    lines.append(f"**Task classification.** {guide['classification']}")
    lines.append(f"**Code required.** {'Yes' if guide['code_required'] else 'No'}")
    lines.append("")
    lines.append("**Learning guide**")
    lines.append("")
    for point in guide["learning"]:
        lines.append(f"- {point}")
    lines.append("")
    lines.append(f"**Output to inspect.** {guide['output_to_inspect']}")
    lines.append("")
    lines.append(f"**Interpretation guidance.** {guide['interpretation']}")
    lines.append("")
    lines.append(f"**Reporting guidance.** {guide['reporting']}")
    lines.append("")
    lines.append(f"**Worked report from the executed notebook.** {report['text']}")
    lines.append("")
    lines.append(f"*Verified source:* {report['source']}. *Teaching note:* {report['teach']}")
    lines.append("")
    lines.append(f"**Common mistakes.** {guide['common_mistakes']}")
    lines.append("")
    return "\n".join(lines)


def build_notebook():
    """Build the notebook, using the last verified results for worked examples."""
    results = {}
    if RESULTS_PATH.is_file():
        results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    cells = []

    cells.append(nbf.v4.new_markdown_cell("\n".join([
        "# STAT 8100 — Biostatistics and Epidemiology Practical Companion",
        "",
        f"**{BUILD_LABEL}**",
        "",
        "This notebook is a complete, executable navigation guide for Questions 1–10. "
        "Run the reusable setup first, then work through the questions in order. Every "
        "code cell has been executed against the three CSV files in this folder; its "
        "output is preserved below the cell.",
        "",
        "## How to use this notebook",
        "",
        "- Run **Reusable setup** once.",
        "- Run **Dataset audit** once to reproduce the verification recorded below.",
        "- For each question, read the learning guide, run the listed code cell(s), inspect the output, then write your own interpretation and report.",
        "- The `mark_done` cell at the end of each question updates the progress indicator.",
        "- Each reporting template is shown twice: once as a reusable sentence frame and once as a worked example filled from the executed notebook.",
        "",
        "## Navigation",
        "",
        _md_table(["Question", "Topic"], [[q, QUESTION_TITLES[q]] for q in QUESTION_ORDER]),
        "",
        "A searchable HTML version with expandable cards and copy-code buttons is available as "
        "`stat8100_practical_companion.html` in the same folder.",
        "",
    ])))

    cells.append(nbf.v4.new_markdown_cell("\n".join([
        "## Dataset audit — completed before implementation",
        "",
        _md_table(["Verification", "Finding"], AUDIT_FACTS),
        "",
        "### Source fingerprints (SHA-256, LF-normalised files)",
        "",
        _md_table(["File", "SHA-256"], [[name, digest] for name, digest in DATA_HASHES.items()]),
        "",
        "The supplied Google Drive files and the bundled `frontend/resources/samples` copies "
        "have identical LF-normalised content; the deployed sample files now use the Drive bytes.",
        "",
    ])))

    cells.append(nbf.v4.new_markdown_cell("## Reusable setup"))
    cells.append(nbf.v4.new_code_cell(CODE["setup"]))
    cells.append(nbf.v4.new_markdown_cell("## Dataset audit code"))
    cells.append(nbf.v4.new_code_cell(CODE["audit"]))

    for qid in QUESTION_ORDER:
        cells.append(nbf.v4.new_markdown_cell(
            f'<a id="{question_slug(qid)}"></a>\n\n## {qid}. {QUESTION_TITLES[qid]}'
        ))
        nav = navigation_rows(qid)
        cells.append(nbf.v4.new_markdown_cell("\n".join([
            "### Navigation table",
            "",
            _md_table(
                ["Question/Subquestion", "Practical requirement", "Task classification",
                 "Jupyter action", "Code", "Output to inspect",
                 "Interpretation guidance", "Reporting guidance"],
                nav,
            ),
            "",
        ])))
        for subid in SUBQUESTION_ORDER:
            prefix = subid[:len(qid)]
            if prefix != qid or (len(subid) > len(qid) and subid[len(qid)].isdigit()):
                continue
            cells.append(nbf.v4.new_markdown_cell(guide_markdown(subid, results)))
            for key in QUESTION_CODE[subid]:
                cells.append(nbf.v4.new_markdown_cell(f"**Code cell `{key}`**"))
                cells.append(nbf.v4.new_code_cell(CODE[key]))
            cells.append(nbf.v4.new_markdown_cell(
                f"**After running:** compare the actual output with the *Output to inspect* "
                f"and *Interpretation guidance* above, then complete the *Reporting guidance* "
                f"in your own words."
            ))
        cells.append(nbf.v4.new_code_cell(f'mark_done("{qid}")'))

    cells.append(nbf.v4.new_markdown_cell("\n".join([
        '<a id="reporting-templates"></a>',
        "## Reporting templates",
        "",
        "Each template keeps placeholders as a reusable writing pattern. The worked example immediately "
        "underneath fills every placeholder from the verified notebook output, so you can compare the "
        "frame with a completed, data-grounded sentence. Do not copy a result that does not match your own output.",
        "",
    ])))
    for example in worked_template_examples(results):
        cells.append(nbf.v4.new_markdown_cell("\n".join([
            f"### {example['title']}",
            "",
            "**Reusable pattern**",
            "",
            f"> {example['pattern']}",
            "",
            f"**Worked example from {example['qid']}**",
            "",
            f"> {example['text']}",
            "",
            f"*Verified source:* {example['source']}. *Teaching note:* {example['teach']}",
            "",
            f"See the executed {example['qid']} section above for the full output.",
            "",
        ])))

    cells.append(nbf.v4.new_markdown_cell("\n".join([
        '<a id="limitations"></a>',
        "## Limitations",
        "",
        "- The datasets are fixed-seed simulated teaching data, not real patient records.",
        "- The supplied `preterm` flag disagrees with a literal decimal `gest_age < 37` rule for nine records; the recorded flag is used as primary.",
        "- `lifelines` is not installed, so survival analysis uses statsmodels and a transparent log-rank implementation. The proportional-hazards check is a Schoenfeld-residual screen, not an exact R `cox.zph` reproduction.",
        "- Statistical associations from these observational data are not causal effects.",
        "- No biomedical threshold, guideline or population claim is inferred from these simulated data.",
        "",
    ])))

    cells.append(nbf.v4.new_markdown_cell("## Machine-readable verification record"))
    cells.append(nbf.v4.new_code_cell(CODE["results"]))

    notebook = nbf.v4.new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3"},
            "title": "STAT 8100 Biostatistics and Epidemiology Practical Companion",
        },
    )
    nbf.write(notebook, NOTEBOOK_PATH)
    return NOTEBOOK_PATH


def _code_block(key):
    code = html.escape(CODE[key].rstrip())
    return (
        '<div class="code-wrap">'
        '<div class="code-head"><span>Code cell <code>' + html.escape(key) +
        '</code></span><button class="copy-code" type="button">Copy code</button></div>'
        '<pre><code class="language-python">' + code + '</code></pre></div>'
    )


def _verified_output(qid, results):
    value = results.get(qid)
    if value is None:
        return '<pre class="verified-output">No code output required — use the conceptual guidance above.</pre>'
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    return '<pre class="verified-output">' + html.escape(text) + '</pre>'


def _guide_html(qid, results):
    guide = GUIDES[qid]
    report = work_report(qid, results)
    learned = "".join(f"<li>{html.escape(point)}</li>" for point in guide["learning"])
    codes = "".join(_code_block(key) for key in QUESTION_CODE[qid]) or (
        '<p class="no-code">No code cell is required for this task.</p>'
    )
    badge_class = {
        "Code": "tag-code", "Interpretation": "tag-interp",
        "Conceptual": "tag-concept", "Calculation": "tag-calc",
        "Mixed": "tag-mixed", "Reporting": "tag-report",
    }.get(guide["classification"], "tag-mixed")
    return f"""
    <details class="question-card" id="{html.escape(qid)}" data-qid="{html.escape(qid)}"
             data-classification="{html.escape(guide['classification'])}" open>
      <summary>
        <span class="qid">{html.escape(qid)}</span>
        <span class="qtitle">{html.escape(guide['title'])}</span>
        <span class="tag {badge_class}">{html.escape(guide['classification'])}</span>
        <span class="done-state" aria-label="Completion state">○</span>
      </summary>
      <div class="card-body">
        <section class="card-section">
          <h4>Practical requirement</h4>
          <p>{html.escape(guide['requirement'])}</p>
          <p class="muted"><strong>Jupyter action:</strong> {html.escape(guide['jupyter_action'])}</p>
          <p class="muted"><strong>Code required:</strong> {'Yes' if guide['code_required'] else 'No'}</p>
        </section>
        <section class="card-section">
          <h4>Learning guide — the ten questions answered</h4>
          <ol class="learning">{learned}</ol>
        </section>
        <section class="card-section">
          <h4>Code</h4>
          {codes}
        </section>
        <section class="card-section">
          <h4>Verified output from the executed notebook</h4>
          {_verified_output(qid, RESULTS_PLACEHOLDER)}
        </section>
        <section class="card-section two-col">
          <div>
            <h4>Interpretation guidance</h4>
            <p>{html.escape(guide['interpretation'])}</p>
          </div>
          <div>
            <h4>Reporting guidance</h4>
            <p>{html.escape(guide['reporting'])}</p>
          </div>
        </section>
        <section class="card-section worked-report">
          <h4>Worked report — verified from the executed notebook</h4>
          <p>{html.escape(report['text'])}</p>
          <p class="muted"><strong>Verified source:</strong> {html.escape(report['source'])}</p>
          <p class="muted"><strong>Teaching note:</strong> {html.escape(report['teach'])}</p>
          <p><a href="#reporting-templates">Compare with the reporting templates</a></p>
        </section>
        <section class="card-section">
          <h4>Common mistakes</h4>
          <p class="warning">{html.escape(guide['common_mistakes'])}</p>
        </section>
        <div class="card-actions">
          <a class="jump" href="#section-{html.escape(parent_question(qid))}">Notebook section {html.escape(parent_question(qid))}</a>
          <button class="mark-complete" type="button" data-qid="{html.escape(qid)}">Mark complete</button>
        </div>
      </div>
    </details>"""


RESULTS_PLACEHOLDER = {}


def build_html(results=None):
    results = results if results is not None else {}
    global RESULTS_PLACEHOLDER
    RESULTS_PLACEHOLDER = results

    nav_rows = []
    for qid, guide in GUIDES.items():
        code_text = ("See " + ", ".join(QUESTION_CODE[qid])) if QUESTION_CODE[qid] else "Not required"
        nav_rows.append([
            qid, guide["requirement"], guide["classification"],
            guide["jupyter_action"], code_text, guide["output_to_inspect"],
            guide["interpretation"], guide["reporting"],
        ])

    index_links = "".join(
        f'<a href="#{html.escape(qid)}"><span>{html.escape(qid)}</span> '
        f'{html.escape(GUIDES[qid]["title"])}</a>'
        for qid in SUBQUESTION_ORDER
    )

    cards = []
    for qid in QUESTION_ORDER:
        cards.append(
            f'<h2 class="question-heading" id="section-{qid}">{qid}. '
            f'{html.escape(QUESTION_TITLES[qid])}</h2>'
        )
        for subid in SUBQUESTION_ORDER:
            prefix = subid[:len(qid)]
            if prefix != qid or (len(subid) > len(qid) and subid[len(qid)].isdigit()):
                continue
            cards.append(_guide_html(subid, results))

    templates = "".join(
        f'<details class="template-example"><summary>{html.escape(example["title"])}</summary>'
        f'<h5>Reusable pattern</h5><pre>{html.escape(example["pattern"])}</pre>'
        f'<h5>Worked example from <a href="#{html.escape(example["qid"])}">{html.escape(example["qid"])}</a></h5>'
        f'<p class="worked-report">{html.escape(example["text"])}</p>'
        f'<p class="muted"><strong>Verified source:</strong> {html.escape(example["source"])} · '
        f'<strong>Teaching note:</strong> {html.escape(example["teach"])}</p>'
        f'</details>'
        for example in worked_template_examples(results)
    )

    audit_html = "".join(
        f"<tr><th>{html.escape(a)}</th><td>{html.escape(b)}</td></tr>"
        for a, b in AUDIT_FACTS
    )
    hashes_html = "".join(
        f"<tr><th>{html.escape(name)}</th><td><code>{html.escape(digest)}</code></td></tr>"
        for name, digest in DATA_HASHES.items()
    )

    embedded_results = json.dumps(results, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")

    document = rf"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>STAT 8100 Practical Companion</title>
<style>
:root{{--navy:#082f6b;--blue:#0b4f8a;--gold:#d8a12a;--ink:#102238;--muted:#5c6b7d;--line:#d8e0ea;--bg:#f4f7fb;--card:#fff;--code:#0b1b2e}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 "Segoe UI",Arial,sans-serif}}
a{{color:var(--blue)}}
header.top{{background:linear-gradient(135deg,#082f6b,#0d5b9f);color:#fff;padding:26px 28px 22px}}
header.top h1{{margin:0 0 6px;font-size:1.8rem}}
header.top p{{margin:4px 0;max-width:900px;color:#e7f0fb}}
.badge{{display:inline-block;border:1px solid #ffffff66;border-radius:999px;padding:3px 10px;font-size:.78rem;margin-right:8px}}
.header-actions{{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}}
.header-actions a{{background:#fff;color:var(--navy);border-radius:8px;padding:8px 12px;font-weight:700;text-decoration:none}}
.layout{{display:grid;grid-template-columns:280px minmax(0,1fr);gap:22px;max-width:1500px;margin:0 auto;padding:22px}}
aside{{position:sticky;top:12px;align-self:start;max-height:calc(100vh - 24px);overflow:auto;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}}
aside h2{{font-size:1rem;margin:0 0 10px;text-transform:uppercase;letter-spacing:.08em;color:var(--navy)}}
aside nav a{{display:block;padding:6px 8px;border-radius:7px;text-decoration:none;color:var(--ink);font-size:.88rem}}
aside nav a:hover{{background:#eaf2fb}}
aside nav a span{{display:inline-block;min-width:42px;font-weight:800;color:var(--blue)}}
main{{min-width:0}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:20px}}
.search-row{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
input[type=search]{{flex:1;min-width:220px;padding:11px 13px;border:1px solid var(--line);border-radius:9px;font-size:1rem}}
.chip{{border:1px solid var(--line);background:#fff;border-radius:999px;padding:7px 12px;cursor:pointer;font-size:.85rem}}
.chip.active{{background:var(--navy);color:#fff;border-color:var(--navy)}}
.progress-line{{height:12px;border-radius:999px;background:#dbe4ef;overflow:hidden;margin:12px 0 6px}}
.progress-fill{{height:100%;width:0;background:linear-gradient(90deg,var(--navy),var(--blue));transition:width .2s}}
.muted{{color:var(--muted)}}
.question-heading{{margin:28px 0 10px;color:var(--navy);font-size:1.35rem;border-bottom:2px solid var(--line);padding-bottom:7px}}
.question-card{{background:var(--card);border:1px solid var(--line);border-radius:13px;margin:10px 0;overflow:hidden}}
.question-card[hidden]{{display:none}}
.question-card>summary{{cursor:pointer;padding:14px 16px;display:flex;gap:10px;align-items:center;list-style:none;background:#fbfdff}}
.question-card>summary::-webkit-details-marker{{display:none}}
.qid{{font-weight:800;color:var(--navy);min-width:46px}}
.qtitle{{flex:1;font-weight:650}}
.tag{{font-size:.72rem;border-radius:999px;padding:3px 9px;font-weight:700;white-space:nowrap}}
.tag-code,.tag-mixed{{background:#e4f0ff;color:#0b4f8a}}
.tag-concept,.tag-interp{{background:#f3e9ff;color:#6b21a8}}
.tag-calc{{background:#e8f7ee;color:#166534}}
.tag-report{{background:#fff4d8;color:#8a5a00}}
.done-state{{color:var(--gold);font-size:1.2rem}}
.card-body{{border-top:1px solid var(--line);padding:4px 16px 16px}}
.card-section{{padding:12px 0;border-bottom:1px solid #edf1f6}}
.card-section:last-of-type{{border-bottom:0}}
.card-section h4{{margin:0 0 8px;font-size:.92rem;text-transform:uppercase;letter-spacing:.06em;color:var(--navy)}}
.card-section p{{margin:6px 0}}
.learning{{margin:0;padding-left:22px}}
.learning li{{margin:4px 0}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.warning{{background:#fff8e8;border-left:4px solid var(--gold);padding:9px 12px;border-radius:6px}}
.worked-report{{background:#f8fbff;border:1px solid #c8dcf2;border-left:4px solid var(--blue);border-radius:8px;padding:11px 13px}}
.worked-report p:first-of-type{{margin-top:0}}
.template-example{{border:1px solid var(--line);border-radius:9px;padding:10px 12px;margin:10px 0;background:#fff}}
.template-example h5{{margin:12px 0 5px;color:var(--navy);font-size:.86rem;text-transform:uppercase;letter-spacing:.05em}}
.code-wrap{{border-radius:10px;overflow:hidden;background:var(--code);border:1px solid #0b1b2e}}
.code-head{{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:#132947;color:#dbeafe;font-size:.82rem}}
.code-head code{{color:#fff}}
.copy-code{{background:#1d4ed8;color:#fff;border:0;border-radius:6px;padding:5px 9px;cursor:pointer;font-size:.78rem}}
pre{{margin:0;overflow:auto}}
.code-wrap pre{{padding:13px;max-height:420px}}
pre code{{font:13px/1.5 "Cascadia Code","Consolas","SFMono-Regular",monospace;color:#e6edf7}}
.verified-output{{background:#f1f5f9;border:1px solid var(--line);border-left:4px solid var(--blue);border-radius:8px;padding:12px;max-height:340px;white-space:pre-wrap;word-break:break-word;font:12.5px/1.45 "Cascadia Code",Consolas,monospace}}
.no-code{{color:var(--muted);font-style:italic}}
.card-actions{{display:flex;gap:12px;align-items:center;margin-top:12px}}
.jump{{font-size:.85rem}}
.mark-complete{{margin-left:auto;background:var(--navy);color:#fff;border:0;border-radius:8px;padding:8px 12px;cursor:pointer;font-weight:700}}
details>summary{{cursor:pointer;font-weight:700;color:var(--navy)}}
details pre{{background:#f1f5f9;border-radius:8px;padding:10px;margin-top:8px}}
table{{border-collapse:collapse;width:100%;font-size:.88rem}}
th,td{{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}}
th{{background:#f1f5fb;color:var(--navy)}}
code{{font-family:"Cascadia Code",Consolas,monospace}}
.tok-comment{{color:#7dd3fc}}
.tok-string{{color:#fbbf24}}
.tok-keyword{{color:#c084fc}}
.tok-number{{color:#86efac}}
footer{{max-width:1500px;margin:0 auto;padding:20px 22px 40px;color:var(--muted);font-size:.86rem}}
@media(max-width:960px){{.layout{{grid-template-columns:1fr}}aside{{position:static;max-height:none}}.two-col{{grid-template-columns:1fr}}header.top{{padding:20px}}}}
</style>
</head>
<body>
<header class="top">
  <h1>STAT 8100 Biostatistics &amp; Epidemiology Practical Companion</h1>
  <p>Lectures 1–6 · Questions 1–10 · searchable navigation, copyable code, verified outputs and reporting guidance.</p>
  <p><span class="badge">{html.escape(BUILD_LABEL)}</span><span class="badge">Output executed against the uploaded CSVs</span></p>
  <div class="header-actions">
    <a href="./stat8100_biostatistics_epidemiology_practical.ipynb" download>Download the notebook</a>
    <a href="./stat8100_practical_results.json" download>Download verified results</a>
    <a href="#nav-table">Jump to full navigation table</a>
  </div>
</header>
<div class="layout">
  <aside>
    <h2>Practical index</h2>
    <nav>{index_links}</nav>
  </aside>
  <main>
    <section class="panel">
      <div class="search-row">
        <input id="search" type="search" placeholder="Search all questions, code and guidance…" aria-label="Search practical">
        <button class="chip active" data-filter="all" type="button">All</button>
        <button class="chip" data-filter="Code" type="button">Code</button>
        <button class="chip" data-filter="Calculation" type="button">Calculation</button>
        <button class="chip" data-filter="Mixed" type="button">Mixed</button>
        <button class="chip" data-filter="Conceptual" type="button">Conceptual</button>
        <button class="chip" data-filter="Interpretation" type="button">Interpretation</button>
      </div>
      <div class="progress-line"><div class="progress-fill" id="progress-fill"></div></div>
      <p class="muted" id="progress-text">0 of 28 subquestions marked complete.</p>
      <p class="muted" id="result-count"></p>
    </section>

    <section class="panel">
      <h2>Data audit completed before implementation</h2>
      <table>{audit_html}</table>
      <h3>Source fingerprints</h3>
      <table>{hashes_html}</table>
      <p class="muted">The supplied Drive files and bundled sample files have identical LF-normalised content. These are simulated teaching datasets, not real patient records.</p>
    </section>

    <section class="panel" id="nav-table">
      <h2>Required navigation table — every subquestion</h2>
      <div style="overflow:auto">
      <table>
        <thead><tr><th>Question/Subquestion</th><th>Practical requirement</th><th>Task classification</th><th>Jupyter action</th><th>Code</th><th>Output to inspect</th><th>Interpretation guidance</th><th>Reporting guidance</th></tr></thead>
        <tbody>{"".join("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>" for row in nav_rows)}</tbody>
      </table>
      </div>
    </section>

    <section class="panel">
      <h2>Reusable setup cell</h2>
      {_code_block('setup')}
    </section>

    {''.join(cards)}

    <section class="panel" id="reporting-templates">
      <h2>Reporting templates with worked verified examples</h2>
      <p class="muted">Each generic pattern keeps placeholders as a reusable sentence frame. Directly underneath, a worked example fills every placeholder with values from the executed notebook; the same examples also appear in the individual question cards.</p>
      {templates}
    </section>

    <section class="panel">
      <h2>Limitations</h2>
      <ul>
        <li>Fixed-seed simulated teaching data; no real patient records.</li>
        <li>The recorded <code>preterm</code> flag differs from literal decimal <code>gest_age &lt; 37</code> for nine records and is used as the primary outcome.</li>
        <li>Survival analysis uses statsmodels plus a transparent log-rank implementation; <code>lifelines</code> is unavailable. The PH check is a Schoenfeld-residual screen, not an exact <code>cox.zph</code> reproduction.</li>
        <li>Observational associations are not causal effects.</li>
      </ul>
    </section>
  </main>
</div>
<footer>STAT 8100 companion · generated from the same verified code cells as the delivered Jupyter notebook.</footer>
<script type="application/json" id="verified-results">{embedded_results}</script>
<script>
(function(){{
  const cards=[...document.querySelectorAll('.question-card')];
  const search=document.getElementById('search');
  const chips=[...document.querySelectorAll('.chip')];
  const fill=document.getElementById('progress-fill');
  const ptext=document.getElementById('progress-text');
  const count=document.getElementById('result-count');
  const KEY='mnh-stat8100-progress-v1';
  let done={{}};
  try{{done=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{done={{}}}}

  function saveProgress(){{try{{localStorage.setItem(KEY,JSON.stringify(done))}}catch(e){{}}}}
  function paintProgress(){{
    cards.forEach(c=>{{
      const on=!!done[c.dataset.qid];
      c.querySelector('.done-state').textContent=on?'●':'○';
      c.querySelector('.mark-complete').textContent=on?'Completed ✓':'Mark complete';
    }});
    const n=Object.keys(done).filter(k=>cards.some(c=>c.dataset.qid===k)).length;
    fill.style.width=(n/cards.length*100)+'%';
    ptext.textContent=n+' of '+cards.length+' subquestions marked complete.';
  }}
  function highlight(code){{
    const source=code.textContent;
    const pattern=/(#.*$|\x22\x22\x22[\s\S]*?\x22\x22\x22|'''[\s\S]*?'''|\x22(?:\\.|[^\x22\\])*\x22|'(?:\\.|[^'\\])*'|\b(?:import|from|as|def|return|for|in|if|else|elif|while|try|except|with|class|lambda|None|True|False|and|or|not|is)\b|\b\d+(?:\.\d+)?\b)/gm;
    let out='';let last=0;let match;
    while((match=pattern.exec(source))!==null){{
      out+=source.slice(last,match.index);
      const token=match[0];
      let cls='tok-number';
      if(token.startsWith('#'))cls='tok-comment';
      else if(token[0]==='\x22'||token[0]==="'"||token.startsWith('\x22\x22\x22')||token.startsWith("'''"))cls='tok-string';
      else if(/^[A-Za-z_]/.test(token))cls='tok-keyword';
      out+='<span class="'+cls+'">'+token.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')+'</span>';
      last=pattern.lastIndex;
    }}
    out+=source.slice(last);
    code.innerHTML=out;
  }}
  document.querySelectorAll('pre code.language-python').forEach(highlight);

  let active='all';
  function filter(){{
    const term=(search.value||'').toLowerCase().trim();
    let shown=0;
    cards.forEach(card=>{{
      const matchesText=!term||card.textContent.toLowerCase().includes(term);
      const matchesTag=active==='all'||card.dataset.classification===active;
      const visible=matchesText&&matchesTag;
      card.hidden=!visible;
      if(visible)shown++;
    }});
    count.textContent=shown+' of '+cards.length+' subquestions visible.';
  }}
  search.addEventListener('input',filter);
  chips.forEach(chip=>chip.addEventListener('click',()=>{{
    chips.forEach(c=>c.classList.remove('active'));
    chip.classList.add('active');active=chip.dataset.filter;filter();
  }}));
  document.querySelectorAll('.copy-code').forEach(btn=>btn.addEventListener('click',async()=>{{
    const code=btn.closest('.code-wrap').querySelector('code');
    try{{await navigator.clipboard.writeText(code.textContent);btn.textContent='Copied ✓'}}
    catch(e){{btn.textContent='Copy failed'}}
    setTimeout(()=>btn.textContent='Copy code',1400);
  }}));
  document.querySelectorAll('.mark-complete').forEach(btn=>btn.addEventListener('click',()=>{{
    const id=btn.dataset.qid;
    if(done[id])delete done[id];else done[id]=true;
    saveProgress();paintProgress();
  }}));
  paintProgress();filter();
}})();
</script>
</body>
</html>
"""
    HTML_PATH.write_text(document, encoding="utf-8", newline="\n")
    if results:
        RESULTS_PATH.write_text(
            json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
    return HTML_PATH


if __name__ == "__main__":
    print("Notebook:", build_notebook())
    print("HTML:", build_html())
