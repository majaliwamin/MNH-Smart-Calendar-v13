"""Structure and data-integrity tests for the visual hypothesis-testing lab."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD = "2026.11.26-exams-hardening-v1"


def test_generated_tables_use_validated_distribution_values():
    data = json.loads(
        (ROOT / "frontend" / "resources" / "data" / "statistical-tables.json").read_text(encoding="utf-8")
    )
    assert "scipy" in data["metadata"]["generated_by"]
    assert "CDF" in data["metadata"]["method"] and "PPF" in data["metadata"]["method"]
    assert data["z"]["critical_values"]["two_tailed"]["0.05"] == pytest.approx(1.959964, abs=1e-5)
    assert data["z"]["worked_lookup"]["cumulative"] == pytest.approx(0.9772, abs=1e-9)
    assert data["z"]["worked_lookup"]["two_tailed_p_full_precision"] == pytest.approx(0.0455, abs=1e-4)
    t_alpha_index = data["t"]["two_tailed_alpha"].index("0.05")
    assert data["t"]["two_tailed"]["24"][t_alpha_index] == pytest.approx(2.0639, abs=1e-4)
    assert data["chi2"]["values"]["2"][1] == pytest.approx(5.9915, abs=1e-4)
    assert data["f"]["values"]["2:60"][1] == pytest.approx(3.1504, abs=1e-4)


def test_alpha_controls_match_generated_table_keys():
    data = json.loads(
        (ROOT / "frontend" / "resources" / "data" / "statistical-tables.json").read_text(encoding="utf-8")
    )
    html = (ROOT / "frontend" / "resources" / "hypothesis-testing-lab.html").read_text(encoding="utf-8")
    alpha_options = set(re.findall(r'<option value="([0-9.]+)"[^>]*>[0-9.]+</option>', html))
    assert alpha_options == {"0.1", "0.05", "0.025", "0.01", "0.005"}
    assert alpha_options <= set(data["z"]["critical_values"]["one_tailed"])
    assert alpha_options <= set(data["z"]["critical_values"]["two_tailed"])
    assert alpha_options <= set(data["t"]["one_tailed_alpha"])
    assert alpha_options <= set(data["t"]["two_tailed_alpha"])
    assert alpha_options <= set(data["chi2"]["right_tail_alpha"])
    assert alpha_options <= set(data["f"]["right_tail_alpha"])


def test_table_builder_reproduces_committed_dataset():
    spec = importlib.util.spec_from_file_location(
        "build_statistical_tables", ROOT / "scripts" / "build_statistical_tables.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generated = module.build()
    committed = json.loads(
        (ROOT / "frontend" / "resources" / "data" / "statistical-tables.json").read_text(encoding="utf-8")
    )
    generated["metadata"]["generated_by"] = committed["metadata"]["generated_by"]
    assert generated == committed


def test_lab_page_is_manual_first_and_self_contained():
    html = (ROOT / "frontend" / "resources" / "hypothesis-testing-lab.html").read_text(encoding="utf-8")
    assert '<html lang="en">' in html
    assert "/vendor/katex/katex.min.css" in html
    assert "/vendor/katex/auto-render.min.js" in html
    assert "row **2.0**" not in html  # the page uses literal markup, not model prose
    assert "row <strong>2.0</strong>" in html
    assert "column <strong>0.00</strong>" in html
    assert "0.9772" in html and "0.0455" in html
    assert "id=\"python-content\" hidden" in html
    assert "id=\"unlock-python\"" in html
    assert "id=\"python-lock\"" in html
    assert html.index('id="python-lock"') < html.index('id="python-content"')
    for table in ("z", "t", "chi2", "f"):
        assert f'data-table="{table}"' in html
    for control in ("dist-alpha", "dist-tails", "dist-direction", "dist-z"):
        assert f'id="{control}"' in html
    assert "simulated teaching values" in html.lower()
    assert "not real patient records" in html.lower()
    assert "cdn." not in html.lower()


def test_lab_is_integrated_into_existing_app_shell():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")

    assert 'data-view="hypothesis-lab"' not in index
    assert 'id="open-hypothesis-lab"' in index
    assert 'id="view-hypothesis-lab"' in index
    assert 'id="hypothesis-lab-back"' in index
    assert 'src="/resources/hypothesis-testing-lab.html?v=visual-hypothesis-lab-v1"' in index

    assert '"hypothesis-lab"' in app
    assert 'showView("hypothesis-lab")' in app
    assert 'hypothesis.hidden=name!=="hypothesis-lab"' in app
    assert 'getElementById("open-hypothesis-lab")?.addEventListener("click"' in app
    assert 'getElementById("hypothesis-lab-back")?.addEventListener("click"' in app
    assert 'body.python-library-view #view-hypothesis-lab:not([hidden])' in css

    assert '"/resources/hypothesis-testing-lab.html"' in worker
    assert '"/resources/data/statistical-tables.json"' in worker


def test_build_string_is_unchanged():
    assert '"2026.11.26-exams-hardening-v1"' in (
        ROOT / "backend" / "app" / "config.py"
    ).read_text(encoding="utf-8")
    assert f'window.MNH_BUILD="{BUILD}"' in (
        ROOT / "frontend" / "index.html"
    ).read_text(encoding="utf-8")
    assert f'const BUILD = "{BUILD}"' in (
        ROOT / "frontend" / "service-worker.js"
    ).read_text(encoding="utf-8")
