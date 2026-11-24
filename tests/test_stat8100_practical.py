"""Structural and reproducibility checks for the STAT 8100 practical companion.

The structural checks use only the standard library. The runtime checks replay
the canonical code cells in one shared namespace when the declared scientific
stack is available; no Jupyter kernel is required to run the test suite.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import html as html_module
import importlib
import io
import json
import math
import os
import re
import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "frontend" / "resources"
SAMPLES = RESOURCES / "samples"
NOTEBOOK = RESOURCES / "stat8100_biostatistics_epidemiology_practical.ipynb"
COMPANION = RESOURCES / "stat8100_practical_companion.html"
RESULTS = RESOURCES / "stat8100_practical_results.json"

QUESTION_IDS = [
    "Q1a", "Q1b",
    "Q2a", "Q2b", "Q2c", "Q2d",
    "Q3a", "Q3b", "Q3c", "Q3d",
    "Q4", "Q5", "Q6",
    "Q7a", "Q7b", "Q7c",
    "Q8a", "Q8b", "Q8c", "Q8d", "Q8e",
    "Q9",
    "Q10a", "Q10b", "Q10c", "Q10d", "Q10e", "Q10f",
]
QUESTION_GROUPS = [f"Q{i}" for i in range(1, 11)]
RESULT_GROUPS = [qid for qid in QUESTION_IDS if qid not in {"Q2a", "Q3c"}] + ["Audit"]
TABLE_HEADERS = [
    "Question/Subquestion", "Practical requirement", "Task classification",
    "Jupyter action", "Code", "Output to inspect",
    "Interpretation guidance", "Reporting guidance",
]
TEMPLATE_TITLES = [
    "Descriptive statistics", "Probability", "Correlation", "Confidence interval",
    "Independent t-test", "Paired t-test", "ANOVA", "Chi-square test",
    "Proportion test", "Linear regression", "Logistic regression",
    "Kaplan-Meier analysis", "Log-rank test", "Exponential survival rate",
    "Cox regression",
]
DATA_HASHES = {
    "anc_cohort.csv": "EE9D58D5E484D62244B62E17910AEDE241B074B4E7F70D22C783F50DD6E9E1DA",
    "bp_paired.csv": "677B7643994C0C57CE9FA2C052EEB22086D5B20537E5D8FE1290A98B3AFEF786",
    "postpartum_survival.csv": "0099FFCFCC226141DD762E6ABD338343325DC360A8011FFC571CAB06AC332EF2",
}
BUILD = "2026.11.22-statistical-tests-glossary-v44"


def _sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    ).hexdigest().upper()


def _results() -> dict:
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def _notebook() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def _source(cell: dict) -> str:
    value = cell.get("source", "")
    return "".join(value) if isinstance(value, list) else value


def _card(companion: str, qid: str) -> str:
    start = companion.index(f'id="{qid}"')
    return companion[start:companion.index("</details>", start)]


def test_practical_resources_exist_and_match_the_uploaded_csvs():
    for path in (NOTEBOOK, COMPANION, RESULTS):
        assert path.is_file(), path
    for name, digest in DATA_HASHES.items():
        assert _sha256(SAMPLES / name) == digest

    results = _results()
    audit = {row["dataset"]: row for row in results["Audit"]["datasets"]}
    assert set(audit) == set(DATA_HASHES)
    for name, digest in DATA_HASHES.items():
        assert audit[name]["sha256"] == digest
        assert audit[name]["duplicate_rows"] == 0
    assert (audit["anc_cohort.csv"]["rows"], audit["anc_cohort.csv"]["columns"]) == (400, 14)
    assert (audit["bp_paired.csv"]["rows"], audit["bp_paired.csv"]["columns"]) == (60, 3)
    assert (audit["postpartum_survival.csv"]["rows"], audit["postpartum_survival.csv"]["columns"]) == (500, 6)
    assert results["Audit"]["education_levels"]["None"] == 55
    assert results["Audit"]["facility_levels"] == {
        "Urban": 154, "Peri-urban": 133, "Rural": 113,
    }
    assert results["Audit"]["iptp3_levels"] == {"Yes": 243, "No": 157}
    assert results["Audit"]["anaemia_mismatches"] == 0
    assert results["Audit"]["preterm_mismatches"] == 9


def test_notebook_is_executed_has_no_errors_and_contains_every_subquestion():
    notebook = _notebook()
    assert notebook.get("nbformat") == 4
    assert notebook["metadata"]["kernelspec"]["name"] == "python3"

    cells = notebook["cells"]
    code_cells = [cell for cell in cells if cell.get("cell_type") == "code"]
    assert len(code_cells) >= 30
    mark_done_cells = [
        _source(cell).strip()
        for cell in code_cells
        if _source(cell).strip().startswith("mark_done(")
    ]
    assert mark_done_cells == [f'mark_done("{group}")' for group in QUESTION_GROUPS]
    assert all(cell.get("execution_count") is not None for cell in code_cells)
    assert not [
        output
        for cell in code_cells
        for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    images = sum(
        1
        for cell in code_cells
        for output in cell.get("outputs", [])
        if "image/png" in output.get("data", {})
    )
    assert images >= 10

    markdown = "\n".join(
        _source(cell) for cell in cells if cell.get("cell_type") == "markdown"
    )
    sources = "\n".join(_source(cell) for cell in code_cells)
    for qid in QUESTION_IDS:
        assert f"#### {qid} —" in markdown
        assert f"**Worked report from the executed notebook.**" in markdown
    assert "**Measurement-scale classification table (verified against the supplied file)**" in markdown
    assert "| Variable | Scale | Why | Verified evidence |" in markdown
    assert markdown.count("**Reusable pattern**") == len(TEMPLATE_TITLES)
    assert markdown.count("**Worked example from Q") == len(TEMPLATE_TITLES)
    for group in QUESTION_GROUPS:
        assert f'<a id="{group.lower()}"></a>' in markdown
    assert '<a id="reporting-templates"></a>' in markdown
    assert '<a id="limitations"></a>' in markdown
    assert markdown.count("| " + " | ".join(TABLE_HEADERS) + " |") == 10

    # Verified library choices are visible in the executed code itself.
    assert "st.binomtest(" in sources
    assert "proportion_confint(" in sources
    assert "SurvfuncRight(" in sources
    assert "PHReg(" in sources
    assert "schoenfeld_residuals" in sources
    assert "multipletests(" in sources
    assert "lifelines" not in sources

    for title, _ in [
        ("Descriptive statistics", ""), ("Kaplan-Meier analysis", ""),
    ]:
        assert title in markdown


def test_verified_results_are_finite_and_use_transparent_denominators():
    text = RESULTS.read_text(encoding="utf-8")
    assert "NaN" not in text and "Infinity" not in text
    results = _results()
    assert set(results) == set(RESULT_GROUPS)

    preterm, low_bw = results["Q1a"]
    assert (preterm["count"], preterm["denominator"]) == (47, 400)
    assert (low_bw["count"], low_bw["denominator"]) == (43, 400)

    anaemia = results["Q3b"]
    assert (anaemia["events"], anaemia["denominator"]) == (139, 382)
    assert anaemia["missing_excluded"] == 18
    assert anaemia["ci"][0] < anaemia["prevalence"] < anaemia["ci"][1]

    survival = results["Q10a"]
    assert (survival["participants"], survival["events"], survival["censored"]) == (500, 209, 291)
    assert survival["median_observed_follow_up"] == 119.0

    km = results["Q10b"]
    for estimate, bounds in (
        (km["survival_90"], km["ci_90"]),
        (km["survival_180"], km["ci_180"]),
    ):
        assert 0 < bounds[0] <= estimate <= bounds[1] < 1
    assert km["number_at_risk"]["0"] == 500

    anova = results["Q6"]
    assert (anova["anova_df_between"], anova["anova_df_within"]) == (2, 379)
    assert 0 <= anova["anova_p"] <= 1
    assert len(anova["tukey"]) == 3

    assert "column_percent" in results["Q7a"]
    assert len(results["Q10f"]) == 3
    assert all("p_holm" in row and "flag_ph_concern" in row for row in results["Q10f"])


def test_html_companion_has_searchable_navigation_and_exact_layout():
    companion = COMPANION.read_text(encoding="utf-8")
    assert "<title>STAT 8100 Practical Companion</title>" in companion
    assert 'id="search"' in companion
    assert 'id="progress-fill"' in companion
    assert 'id="progress-text"' in companion
    assert 'id="nav-table"' in companion

    assert companion.count('<details class="question-card"') == len(QUESTION_IDS)
    for qid in QUESTION_IDS:
        assert f'id="{qid}"' in companion
        assert f'href="#{qid}"' in companion
    for group in QUESTION_GROUPS:
        assert f'id="section-{group}"' in companion

    for header in TABLE_HEADERS:
        assert f"<th>{header}</th>" in companion
    assert "<thead><tr>" + "".join(f"<th>{h}</th>" for h in TABLE_HEADERS) + "</tr></thead>" in companion

    for title in TEMPLATE_TITLES:
        assert f"<summary>{title}</summary>" in companion
    assert companion.count('<details class="template-example">') == len(TEMPLATE_TITLES)
    assert companion.count("Worked example from ") >= len(TEMPLATE_TITLES)
    assert 'id="reporting-templates"' in companion
    assert "Placeholders must be replaced with actual values" not in companion
    assert "Lectures 1–6 · Questions 1–10" not in companion
    assert "Output executed against the uploaded CSVs" not in companion
    for qid in QUESTION_IDS:
        card = _card(companion, qid)
        assert "<h4>Worked report — verified from the executed notebook</h4>" in card
        assert "<strong>Verified source:</strong>" in card
        assert "<strong>Teaching note:</strong>" in card
    q2a = _card(companion, "Q2a")
    assert "Measurement-scale classification table" in q2a
    assert "<th>Verified evidence</th>" in q2a
    assert "Urban (n=154)" in q2a
    assert "47/400" in _card(companion, "Q1a")
    assert "139/382" in _card(companion, "Q3b")
    assert "68,841 person-days" in _card(companion, "Q10d")
    assert "simulated teaching data" in companion
    assert "not an exact" in companion

    match = re.search(
        r'<script type="application/json" id="verified-results">(.*?)</script>',
        companion,
        flags=re.S,
    )
    assert match
    assert json.loads(html_module.unescape(match.group(1))) == _results()


def test_html_code_is_copyable_but_manual_tasks_have_no_code_cell():
    companion = COMPANION.read_text(encoding="utf-8")
    code_blocks = re.findall(
        r'<pre><code class="language-python">(.*?)</code></pre>',
        companion,
        flags=re.S,
    )
    assert len(code_blocks) == 27
    assert companion.count('<button class="copy-code"') == 27
    assert companion.count('data-requires-setup="true"') == 26
    assert companion.count('<button class="copy-cell-only"') == 26
    assert all("language-python" not in _card(companion, qid) for qid in ("Q2a", "Q3c"))
    assert all("No code cell is required" in _card(companion, qid) for qid in ("Q2a", "Q3c"))

    q1a = _card(companion, "Q1a")
    assert "language-python" in q1a
    assert 'data-requires-setup="true"' in q1a
    assert "Copy setup + cell" in q1a
    assert "Copy cell only" in q1a
    assert "setupCode=document.querySelector('.code-wrap[data-cell=\"setup\"] pre code')" in companion
    assert "wrap.querySelector('pre code')" in companion
    assert "class=\"verified-output\"" in q1a
    assert "<h4>Interpretation guidance</h4>" in q1a
    assert "<h4>Reporting guidance</h4>" in q1a

    decoded = [html_module.unescape(block) for block in code_blocks]
    assert any("st.binomtest(" in block for block in decoded)
    assert any("SurvfuncRight(" in block for block in decoded)
    assert any("PHReg(" in block for block in decoded)
    assert not any("pip install" in block or "requests." in block for block in decoded)

    # The HTML and the executed notebook share one source of code cells.
    sources = "\n".join(
        _source(cell)
        for cell in _notebook()["cells"]
        if cell.get("cell_type") == "code"
    )
    assert "MNH_VERIFIED_RESULTS_JSON:" in sources
    for marker in ("st.binomtest(", "schoenfeld_residuals", "SurvfuncRight("):
        assert marker in sources
        assert marker in "\n".join(decoded)


def test_question_cells_explain_the_setup_prerequisite():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from stat8100_code_cells import CODE

    namespace = {}
    raised = None
    try:
        exec(CODE["q1a"], namespace)
    except RuntimeError as exc:
        raised = exc
    assert raised is not None
    assert "Run the 'Reusable setup' cell" in str(raised)
    assert "record()" in str(raised)
    assert "Reusable setup" in CODE["q1a"].splitlines()[0]


def test_companion_light_and_high_contrast_rendering_is_explicit():
    companion = COMPANION.read_text(encoding="utf-8")
    assert 'color-scheme:light' in companion
    assert 'data-companion-theme="dark"' in companion
    assert '@media(forced-colors:active)' in companion
    assert '@media(prefers-contrast:more)' in companion
    assert 'CanvasText' in companion
    assert 'data-companion-theme-btn="light"' in companion
    assert 'data-companion-theme-btn="dark"' in companion


def test_practical_view_is_additive_to_the_existing_full_screen_pattern():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    config = (ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")

    assert f'BUILD_ID = "{BUILD}"' in config
    assert f'window.MNH_BUILD="{BUILD}"' in index
    assert f'const BUILD = "{BUILD}"' in worker

    # Existing Python Library behaviour remains intact.
    assert 'id="view-python-library"' in index
    assert 'id="open-python-library"' in index
    assert 'python-library-frame' in css
    assert 'id="view-stat8100-practical"' in index
    assert 'id="open-stat8100-practical"' in index
    assert 'id="stat8100-practical-back"' in index
    assert 'data-view="stat8100-practical"' not in index
    assert 'src="/resources/stat8100_practical_companion.html?v=2026.11.22-stat8100-practical-v2"' in index
    assert 'title="STAT 8100 Biostatistics and Epidemiology Practical Companion"' in index

    assert '"stat8100-practical"' in app
    assert 'previousNonPracticalView' in app
    assert 'practical=document.getElementById("view-stat8100-practical")' in app
    assert 'practical.hidden=name!=="stat8100-practical"' in app
    assert 'name==="python-library"||name==="python-setup-simulation"||name==="stat8100-practical"' in app
    assert 'getElementById("open-stat8100-practical")?.addEventListener("click",()=>showView("stat8100-practical"))' in app
    assert 'getElementById("stat8100-practical-back")?.addEventListener("click",()=>showView(previousNonPracticalView||"resources"))' in app
    assert 'body.python-library-view #view-stat8100-practical:not([hidden])' in css

    for path in (
        "/resources/stat8100_practical_companion.html",
        "/resources/stat8100_biostatistics_epidemiology_practical.ipynb",
        "/resources/stat8100_practical_results.json",
    ):
        assert f'"{path}"' in worker


def test_stat8100_companion_is_english_only():
    assert not (RESOURCES / "stat8100_practical_companion_ny.html").exists()
    assert not (ROOT / "scripts" / "stat8100_chichewa.py").exists()

    companion = COMPANION.read_text(encoding="utf-8")
    assert "stat8100_practical_companion_ny" not in companion
    assert "Chichewa version" not in companion
    assert "lang-ny" not in companion

    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "stat8100_practical_companion_ny" not in index
    assert "Open Chichewa STAT 8100 Companion" not in index

    worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    assert "/resources/stat8100_practical_companion_ny.html" not in worker.split("const REMOVED_APP_FILES")[0]

    builder = (ROOT / "scripts" / "build_stat8100_practical.py").read_text(encoding="utf-8")
    assert "stat8100_chichewa" not in builder
    assert "stat8100_practical_companion_ny" not in builder
    assert "_localize_document" not in builder


def test_generators_and_dev_dependencies_are_present():
    scripts = ROOT / "scripts"
    for name in (
        "stat8100_code_cells.py",
        "stat8100_guides.py",
        "stat8100_reporting.py",
        "build_stat8100_practical.py",
        "execute_stat8100_practical.py",
    ):
        assert (scripts / name).is_file()
    builder = (scripts / "build_stat8100_practical.py").read_text(encoding="utf-8")
    runner = (scripts / "execute_stat8100_practical.py").read_text(encoding="utf-8")
    assert "def build_notebook()" in builder
    assert "def build_html(results=None):" in builder
    assert "from stat8100_reporting import work_report, worked_template_examples" in builder
    assert "nbformat.writes(" in runner
    assert "_atomic_write_text(" in runner
    assert "NotebookClient(" in runner
    assert "MARKER" in runner

    dev = (ROOT / "backend" / "requirements-dev.txt").read_text(encoding="utf-8")
    for package in ("matplotlib", "seaborn", "nbformat", "nbclient", "ipykernel"):
        assert package in dev

    for path in (NOTEBOOK, COMPANION, RESULTS):
        text = path.read_text(encoding="utf-8")
        assert "TODO" not in text
        assert "FIXME" not in text
        assert "coming soon" not in text.lower()


def _code_cells_module(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("stat8100_code_cells")


def _close_enough(left, right) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if isinstance(left, int) and isinstance(right, int):
            return left == right
        return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _close_enough(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _close_enough(a, b) for a, b in zip(left, right)
        )
    return left == right


def test_canonical_code_cells_parse_and_html_shows_exact_source(monkeypatch):
    module = _code_cells_module(monkeypatch)
    guides = importlib.import_module("stat8100_guides")
    for key, source in module.CODE.items():
        ast.parse(source, filename=f"CODE[{key!r}]")

    companion = COMPANION.read_text(encoding="utf-8")
    blocks = re.findall(
        r'<pre><code class="language-python">(.*?)</code></pre>',
        companion,
        flags=re.S,
    )
    decoded = [html_module.unescape(block) for block in blocks]
    expected = [module.CODE["setup"]] + [
        module.CODE[cell]
        for qid in guides.GUIDES
        for cell in module.QUESTION_CODE[qid]
    ]
    assert decoded == expected
    assert all(block.endswith("\n") for block in decoded)


def test_copy_buttons_use_real_newlines_and_prerequisite_chain():
    companion = COMPANION.read_text(encoding="utf-8")
    assert "String.fromCharCode(10,10)" in companion
    assert "'\\\\n\\\\n'" not in companion
    assert "function fallbackCopy(text)" in companion
    assert "document.execCommand('copy')" in companion
    assert "(wrap.dataset.prereqs||'').split(' ')" in companion
    for key, prerequisites in (
        ("q8c", "q8b"),
        ("q8d", "q8b"),
        ("q8e", "q8b q8d"),
        ("q10d", "q10a"),
        ("q10f", "q10e"),
    ):
        assert f'data-cell="{key}" data-requires-setup="true" data-prereqs="{prerequisites}"' in companion


def test_code_window_is_dark_and_high_contrast_in_both_themes():
    companion = COMPANION.read_text(encoding="utf-8")
    # Light resources page, dark editor: the code palette is fixed on :root.
    assert "--code:#0f172a" in companion
    assert "--code-head:#1e293b" in companion
    assert "--code:#020617" in companion
    assert "color-scheme:dark" in companion
    assert ".code-line::before" in companion
    assert "user-select:none" in companion
    assert "min-width:max-content" in companion
    assert "overscroll-behavior-x:contain" in companion
    for token in ("comment", "string", "keyword", "number", "function",
                  "builtin", "variable", "operator"):
        assert f".tok-{token}{{" in companion
    assert "forced-color-adjust:auto" in companion


def test_runtime_replay_reproduces_the_committed_verified_results(monkeypatch):
    for package in ("numpy", "pandas", "scipy", "statsmodels", "seaborn"):
        pytest.importorskip(package)
    matplotlib = pytest.importorskip("matplotlib")
    # A GUI backend imported by another test would make plt.show() block.
    matplotlib.use("Agg", force=True)
    module = _code_cells_module(monkeypatch)
    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.setenv("MNH_DATA_DIR", str(SAMPLES))
    monkeypatch.chdir(ROOT)

    namespace = {"__name__": "__main__"}
    streams = []
    marker = "MNH_VERIFIED_RESULTS_JSON:"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for key, source in module.CODE.items():
            ast.parse(source)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exec(compile(source, f"cell:{key}", "exec"), namespace)
            streams.append(buffer.getvalue())

    marker_outputs = [text for text in streams if marker in text]
    assert len(marker_outputs) == 1
    fresh = json.loads(marker_outputs[0].split(marker, 1)[1].strip())
    committed = _results()
    assert set(fresh) == set(committed)
    assert _close_enough(fresh, committed)
    assert all(math.isfinite(value) for value in _flatten_numbers(fresh))

    # The canonical CODE cells print the initial 0/10 state. The notebook's
    # separate mark_done cells advance it to 10/10 and are checked above.
    progress = [
        int(match.group(1))
        for match in re.finditer(
            r"Progress:.*?\b(\d+)/10 questions covered", "\n".join(streams)
        )
    ]
    assert progress == [0]


def _flatten_numbers(value):
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _flatten_numbers(child)]
    if isinstance(value, list):
        return [item for child in value for item in _flatten_numbers(child)]
    return []


def test_chained_cells_report_missing_prerequisites(monkeypatch):
    module = _code_cells_module(monkeypatch)
    # Supply only the setup objects so the setup guard passes and the new
    # cell-specific guard is the one under test.
    namespace = {"anc": object(), "record": lambda *args, **kwargs: None}
    for key, expected in (
        ("q8c", ("q8b", "model_multi")),
        ("q8d", ("q8b", "formula_base")),
        ("q8e", ("q8b", "q8d", "model_extended")),
        ("q10d", ("q10a", "events")),
        ("q10f", ("q10e", "cox_design")),
    ):
        with pytest.raises(RuntimeError) as raised:
            exec(compile(module.CODE[key], f"cell:{key}", "exec"), dict(namespace))
        message = str(raised.value)
        assert "Run prerequisite code cell(s)" in message
        for token in expected:
            assert token in message


def test_worked_reports_use_correct_statistical_direction_and_wording(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    reporting = importlib.import_module("stat8100_reporting")
    results = _results()

    q6 = reporting.work_report("Q6", results)
    assert "Rural minus Peri-urban = -0.11 g/dL" in q6["text"]
    assert "Urban minus Peri-urban = 0.64 g/dL" in q6["text"]
    assert "group2 minus group1" in q6["teach"]
    assert "Alexander-Govern" in q6["text"]

    q8c = reporting.work_report("Q8c", results)
    assert "descriptive only" in q8c["text"]
    assert "row index 243" in q8c["text"]

    q8d = reporting.work_report("Q8d", results)
    assert "mixed, weak evidence of improvement" in q8d["text"]

    q10e = reporting.work_report("Q10e", results)
    assert "age HR 1.020 (95% CI 0.998 to 1.042" in q10e["text"]
    assert "no clear change in hazard" in q10e["text"]
    assert "flags a time trend for anaemia and caesarean" in q10e["text"]

    assert "still needed" in reporting.work_report("Q2d", results)["text"]
    assert "Q8d" in reporting.work_report("Q3d", results)["teach"]
