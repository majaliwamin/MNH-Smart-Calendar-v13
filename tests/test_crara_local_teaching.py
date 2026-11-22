import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    """Hash canonical LF bytes, matching the committed teaching resources."""
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    ).hexdigest()


def _chart_from(answer: str) -> dict:
    match = re.search(r"```chart\s*(\{.*?\})\s*```", answer, flags=re.S | re.I)
    assert match, "a fenced chart JSON block is required"
    return json.loads(match.group(1))


def test_generated_local_knowledge_is_source_backed():
    from app.class_rep import local_knowledge

    payload = local_knowledge.knowledge()
    assert payload["schema_version"] == 1
    assert payload["build"] == "2026.11.22-statistical-tests-glossary-v44"
    assert payload["generated_by"] == "scripts/build_statistical_glossary.py"
    assert len(payload["glossary"]) == 46
    assert len(payload["library_sections"]) >= 40
    assert len(payload["visual_recipes"]) == 7

    for source in payload["sources"].values():
        path = ROOT / source["path"]
        assert path.is_file()
        assert _sha256(path) == source["sha256"]
    for name, meta in payload["datasets"].items():
        path = ROOT / meta["path"]
        assert path.is_file()
        assert _sha256(path) == meta["sha256"]
        assert "simulated teaching data" in meta["label_en"]
        assert "si zolemba za odwala enieni" in meta["label_ny"]


def test_glossary_and_library_evidence_uses_verified_bilingual_wording():
    from app.class_rep import local_knowledge

    english = local_knowledge.local_teaching_context("Explain Welch's t-test from the local library", "EN")
    chichewa = local_knowledge.local_teaching_context(
        "Fotokozani Welch's t-test mu Chichewa pogwiritsa ntchito chapter ya hypothesis testing",
        "CH",
    )
    assert "LOCAL PYTHON LIBRARY — VERIFIED STATISTICAL GLOSSARY" in english
    assert "LOCAL PYTHON LIBRARY — CHAPTER EVIDENCE" in english
    assert "Welch’s t-test" in english
    assert "English definition:" in english
    assert "Executed fixed-seed teaching output:" in english
    assert "Chichewa explanation:" in chichewa
    assert "Misconception:" in chichewa
    assert "python-command-library.html#" in chichewa

    assert local_knowledge.local_teaching_context("What time is the next class?", "EN") == ""


def test_dataset_evidence_never_presents_simulations_as_patient_records():
    from app.class_rep import local_knowledge

    context = local_knowledge.dataset_context("Draw a distribution curve from the data")
    assert "LOCAL VERIFIED TEACHING DATASETS" in context
    assert "simulated teaching data, never real patient records" in context
    for name in ("anc_cohort.csv", "bp_paired.csv", "postpartum_survival.csv"):
        assert name in context
        assert "SHA-256" in context


def test_distribution_visual_is_computed_from_verified_local_data():
    from app.class_rep import stats_visuals

    answer, provider, model = stats_visuals.answer_visual(
        "Draw a birthweight distribution curve", "EN"
    )
    assert provider == "CRARA local Python library"
    assert model == "verified-simulated-teaching-data-v1"
    assert "Chart from verified local teaching data" in answer
    assert "n =" not in answer or "Using 400 complete records" in answer
    assert "Gaussian KDE" in answer
    assert "not a real population" in answer
    assert "SHA-256" in answer
    assert "No web source or patient record was used" in answer
    assert "```python" in answer

    chart = _chart_from(answer)
    assert chart["type"] == "line"
    assert len(chart["labels"]) == 24
    assert len(chart["datasets"]) == 2
    assert chart["datasets"][0]["label"] == "Observed density (KDE)"
    assert chart["datasets"][1]["label"] == "Fitted normal curve"
    assert all(len(item["data"]) == 24 for item in chart["datasets"])
    assert all(value >= 0 for item in chart["datasets"] for value in item["data"])
    assert max(chart["datasets"][0]["data"]) > 0


def test_chichewa_distribution_visual_uses_gwero_and_simulated_data_wording():
    from app.class_rep import stats_visuals

    answer, provider, _ = stats_visuals.answer_visual(
        "Jambulani kufalikira kwa kulemera kwa makanda", "CH"
    )
    assert provider == "CRARA local Python library"
    assert "Chati yochokera ku deta yotsimikizirika" in answer
    assert "Kufalikira kwa kulemera" in answer
    assert "Gwero: fayilo ya deta yophunzitsira yopangidwa" in answer
    assert "Palibe gwero la intaneti kapena deta ya odwala" in answer
    assert "Izi si zomwe anapeza pa kafukufuku" in answer
    chart = _chart_from(answer)
    assert chart["datasets"][0]["label"] == "Kufalikira kwenikweni (KDE)"
    assert chart["datasets"][1]["label"] == "Normal curve yofananira"


def test_other_verified_visual_recipes_return_valid_backend_chart_json():
    from app.class_rep import stats_visuals

    cases = [
        ("Draw a paired blood pressure chart", "line"),
        ("Show a birth weight by facility chart", "bar"),
        ("Draw a gestational age scatter", "scatter"),
        ("Show a survival curve by anaemia", "line"),
    ]
    for message, chart_type in cases:
        answer, provider, model = stats_visuals.answer_visual(message, "EN")
        assert provider == "CRARA local Python library"
        assert model == "verified-simulated-teaching-data-v1"
        chart = _chart_from(answer)
        assert chart["type"] == chart_type
        assert chart["datasets"] and chart["datasets"][0]["data"]
        assert "SHA-256" in answer
        assert "not research findings" in answer or "simulated teaching" in answer


def test_visual_route_does_not_capture_timetable_or_real_patient_requests():
    from app.class_rep import stats_visuals

    assert stats_visuals.answer_visual("What is on the timetable on Monday?", "EN") is None
    assert stats_visuals.answer_visual("Kodi muli makalasi lero?", "CH") is None

    answer, _, model = stats_visuals.answer_visual(
        "Can you draw a chart from real patient data?", "EN"
    )
    assert model == "supported-visual-options-v1"
    assert "I cannot use real patient records here" in answer
    assert "```chart" not in answer


def test_tampered_dataset_hash_fails_closed_without_inventing_a_chart(monkeypatch):
    from app.class_rep import local_knowledge, stats_visuals

    original = local_knowledge.knowledge()
    tampered = copy.deepcopy(original)
    tampered["datasets"]["anc_cohort.csv"]["sha256"] = "0" * 64
    monkeypatch.setattr(stats_visuals.local_knowledge, "knowledge", lambda: tampered)
    answer, _, model = stats_visuals.answer_visual("Draw a birthweight curve", "EN")
    assert model == "visual-unavailable-v1"
    assert "No values or chart have been invented" in answer
    assert "```chart" not in answer


def test_assistant_injects_local_evidence_and_chichewa_contract(monkeypatch):
    from app.class_rep import assistant

    seen = {}

    def complete(messages):
        seen["messages"] = messages
        return (
            "Welch’s t-test ndi mayeso lomwe limayerekeza avareji ya magulu awiri "
            "osadalirana popanda kuganiza kuti kufalikira kwawo kuli kofanana. "
            "Timaganizira kusiyana kwa avareji, mtengo wa p ndi chidaliro cha "
            "zotsatira. Deta yopangidwa yophunzitsira imatithandiza kuona njirayi, "
            "koma si zomwe anapeza pa odwala enieni.",
            "test", "m1",
        )

    monkeypatch.setattr(assistant, "build_calendar_context", lambda query="": ("{}", None))
    monkeypatch.setattr(assistant, "search_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(assistant, "unknown_term_answer", lambda *args, **kwargs: None)
    monkeypatch.setattr(assistant, "complete", complete)

    answer, _, _, _ = assistant.reply(
        "Fotokozani Welch's t-test mu Chichewa", [], response_language="CH"
    )
    system = seen["messages"][0]["content"]
    assert "LOCAL PYTHON LIBRARY GROUNDING" in system
    assert "primary source" in system
    assert "LOCAL PYTHON LIBRARY — VERIFIED STATISTICAL GLOSSARY" in system
    assert "Welch’s t-test" in system
    assert "CHICHEWA ACADEMIC EXPRESSION CONTRACT" in system
    assert "Simulated teaching data" in answer or "Deta yopangidwa yophunzitsira" in answer


def test_assistant_answers_verified_visuals_without_provider_call(monkeypatch):
    from app.class_rep import assistant

    def forbidden_complete(messages):
        raise AssertionError("deterministic local visuals must not call a model provider")

    monkeypatch.setattr(assistant, "complete", forbidden_complete)
    answer, provider, model, updated = assistant.reply(
        "Draw a haemoglobin distribution curve", [], response_language="EN"
    )
    assert provider == "CRARA local Python library"
    assert model == "verified-simulated-teaching-data-v1"
    assert updated is None
    assert "haemoglobin density" in answer
    chart = _chart_from(answer)
    assert chart["type"] == "line"
    assert len(chart["datasets"]) == 2


def test_chat_route_returns_verified_visual_to_guest(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import config
    from app.database import connection
    from app.main import app
    from app.services import backup_service

    database_dir, backup_dir = tmp_path / "database", tmp_path / "backups"
    monkeypatch.setattr(config, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(config, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(connection, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "BACKUP_DIR", backup_dir)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MNH_ENV", "development")

    with TestClient(app) as client:
        me = client.get("/api/class-rep/auth/me")
        assert me.status_code == 200
        assert me.json()["guest"] is True
        response = client.post("/api/class-rep/chat", json={
            "message": "Draw a birthweight distribution curve",
            "response_language": "EN",
        })
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "CRARA local Python library"
        assert payload["model"] == "verified-simulated-teaching-data-v1"
        chart = _chart_from(payload["reply"])
        assert chart["type"] == "line"
        assert len(chart["datasets"]) == 2
