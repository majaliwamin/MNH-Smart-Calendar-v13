"""Validation for the Chichewa STAT 8100 companion and translation layer."""

from __future__ import annotations

import html as html_module
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "frontend" / "resources"
sys.path.insert(0, str(ROOT / "scripts"))

import build_stat8100_practical as builder  # noqa: E402
import stat8100_chichewa as ny  # noqa: E402
import stat8100_guides as guides  # noqa: E402
import stat8100_reporting as reporting  # noqa: E402

EN_COMPANION = RESOURCES / "stat8100_practical_companion.html"
NY_COMPANION = RESOURCES / "stat8100_practical_companion_ny.html"
RESULTS = RESOURCES / "stat8100_practical_results.json"


def _card(document: str, qid: str) -> str:
    match = re.search(
        rf'<details class="question-card" id="{re.escape(qid)}".*?</details>',
        document,
        flags=re.S,
    )
    assert match, qid
    return match.group(0)


def _codes(document: str) -> list[str]:
    return re.findall(
        r'<pre><code class="language-python">(.*?)</code></pre>',
        document,
        flags=re.S,
    )


def _embedded_results(document: str):
    match = re.search(
        r'<script type="application/json" id="verified-results">(.*?)</script>',
        document,
        flags=re.S,
    )
    assert match
    return json.loads(html_module.unescape(match.group(1)))


def _numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", text)


def test_translation_coverage_is_complete():
    report = ny.coverage_report()
    assert report["guides"] == 28
    assert report["learning_points"] == 280
    assert report["templates"] == 15
    assert report["unmapped"] == []


def test_guide_translations_preserve_structure_and_identifiers():
    for qid, source in guides.GUIDES.items():
        translated = ny.guide_ny(qid)
        assert set(translated) == set(source)
        assert len(translated["learning"]) == len(source["learning"]) == 10
        for key in ("id", "title", "requirement", "classification", "jupyter_action"):
            assert isinstance(translated[key], str) and translated[key]
        source_json = json.dumps(source, ensure_ascii=False)
        translated_json = json.dumps(translated, ensure_ascii=False)
        for token in ("anc", "low_bw", "gest_age", "hb", "bmi", "iptp3", "preterm"):
            pattern = rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])"
            if re.search(pattern, source_json):
                assert re.search(pattern, translated_json), token


def test_reports_and_templates_preserve_verified_numbers():
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    for qid in guides.GUIDES:
        source = reporting.work_report(qid, results)
        translated = ny.report_ny(qid, source)
        assert set(translated) == {"text", "source", "teach"}
        assert _numbers(translated["text"]) == _numbers(source["text"])
    for example in reporting.worked_template_examples(results):
        translated = ny.template_ny(example)
        assert set(translated) == set(example)
        assert _numbers(translated["text"]) == _numbers(example["text"])


def test_audit_and_classification_translations_preserve_evidence():
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    audit = ny.audit_facts_ny()
    assert len(audit) == len(builder.AUDIT_FACTS)
    for (translated_verification, translated_finding), (verification, finding) in zip(
        audit, builder.AUDIT_FACTS
    ):
        assert _numbers(verification) == _numbers(translated_verification)
        assert _numbers(finding) == _numbers(translated_finding)

    rows = builder.classification_rows(results)
    translated_rows = ny.classification_rows_ny(rows)
    assert len(translated_rows) == len(rows) == 5
    for source_row, translated_row in zip(rows, translated_rows):
        assert len(translated_row) == len(source_row) == 4
        assert translated_row[0] == source_row[0]
        assert _numbers(" ".join(translated_row)) == _numbers(" ".join(source_row))


def test_key_chichewa_statistical_terminology_is_used():
    sample = " ".join(
        ny.guide_ny(qid)["learning"][0] + " " + ny.guide_ny(qid)["interpretation"]
        for qid in guides.GUIDES
    )
    lower = sample.lower()
    for term in (
        "kubadwa msanga",
        "kulemera kochepa pakubadwa",
        "kuchepa kwa magazi",
        "mwayi",
        "confidence interval",
        "chi-square",
        "hazard ratio",
        "anova",
    ):
        assert term in lower, term


def test_chichewa_companion_is_complete_and_matches_verified_data():
    assert NY_COMPANION.is_file()
    en = EN_COMPANION.read_text(encoding="utf-8")
    translated = NY_COMPANION.read_text(encoding="utf-8")
    assert '<html lang="ny">' in translated
    assert translated.count('class="question-card"') == 28
    assert len(_codes(translated)) == len(_codes(en)) == 27
    assert _codes(translated) == _codes(en)
    assert translated.count('<details class="template-example"') == 15
    assert _embedded_results(translated) == _embedded_results(en)
    assert "Placeholders must be replaced" not in translated
    assert 'data-companion-theme-btn="light"' in translated
    assert 'data-companion-theme-btn="dark"' in translated
    assert 'href="./stat8100_practical_companion.html"' in translated
    assert 'href="./stat8100_practical_companion_ny.html"' in en
    assert ".lang-en{display:none}.lang-ny{display:inline-block}" in translated


def test_q1a_chichewa_card_keeps_the_setup_fix_and_verified_output():
    translated = NY_COMPANION.read_text(encoding="utf-8")
    card = _card(translated, "Q1a")
    assert 'data-requires-setup="true"' in card
    assert "Copy setup + cell" not in card  # visible button text is translated
    assert "Copy cell only" not in card
    assert "language-python" in card
    assert "class=\"verified-output\"" in card
    assert "47" in card
    assert "400" in card


def test_language_version_is_discoverable_and_cacheable():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    service_worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    assert "stat8100_practical_companion_ny.html?v=2026.11.22-stat8100-practical-v2" in index
    assert '"/resources/stat8100_practical_companion_ny.html"' in service_worker
