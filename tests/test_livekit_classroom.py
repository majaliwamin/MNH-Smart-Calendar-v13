from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
CLASSROOM_DIR = ROOT / "frontend" / "resources" / "crara-classroom"


def test_classroom_bundle_is_present_and_rebranded():
    html_path = CLASSROOM_DIR / "index.html"
    js_path = CLASSROOM_DIR / "crara-classroom.js"
    css_path = CLASSROOM_DIR / "crara-classroom.css"
    assert html_path.is_file()
    assert js_path.is_file()
    assert css_path.is_file()

    html = html_path.read_text(encoding="utf-8")
    assert "<title>CRARA — 1:1 Classroom</title>" in html
    assert "crara-classroom.js" in html
    assert "crara-classroom.css" in html

    for path in (html_path, js_path, css_path):
        content = path.read_text(encoding="utf-8").lower()
        assert "penrose" not in content, path
        assert "scholarmw" not in content, path
        assert "voice training" not in content, path
        assert "vtc" not in content, path

    js = js_path.read_text(encoding="utf-8")
    assert "crara.classroom.token" in js
    assert "/api/v1/livekit/token" in js
    assert "/api/v1/system-audio/virtual-recordings" in js
    assert "This classroom is not connected to a CRARA session" in js


def test_crara_ui_offers_lesson_scoped_classroom_panel():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    assert "cr-classroom-panel" in js
    assert "crara-live-classroom-wrapper" in js
    assert "crara-live-classroom-frame" in js
    assert "/api/class-rep/livekit/handoff" in js
    assert "Join 1:1 Classroom" in js
    assert "camera; microphone; autoplay; display-capture; clipboard-write; fullscreen" in js
    assert "Reconnect" in js and "Fullscreen" in js and "Exit" in js

    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert ".cr-classroom-panel[hidden]{display:none!important}" in css
    assert ".cr-classroom-frame-wrap" in css

    worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    assert "/resources/crara-classroom/index.html" in worker
    assert "/resources/crara-classroom/crara-classroom.js" in worker
    assert "/resources/crara-classroom/crara-classroom.css" in worker


def test_livekit_backend_routes_and_configuration_are_registered():
    routes = (ROOT / "backend" / "app" / "livekit" / "routes.py").read_text(encoding="utf-8")
    assert '@router.post("/api/class-rep/livekit/handoff")' in routes
    assert '@router.post("/api/v1/livekit/token")' in routes
    assert '@router.post("/api/class-rep/livekit/token")' in routes
    assert '@router.post("/api/v1/system-audio/virtual-recordings")' in routes
    assert 'from app.config import' in routes

    main = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "from app.livekit.routes import router as livekit_router" in main
    assert "app.include_router(livekit_router)" in main

    config = (ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")
    for name in ("MNH_LIVEKIT_URL", "MNH_LIVEKIT_API_KEY", "MNH_LIVEKIT_API_SECRET"):
        assert name in config

    requirements = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    assert "livekit-api" in requirements


def test_handoff_token_is_scoped_to_the_lesson_and_crara_identity(monkeypatch):
    from app.livekit import routes as livekit_routes

    monkeypatch.setattr(livekit_routes, "_handoff_secret", lambda: b"unit-test-secret")
    user = {"id": "guest_abcdefgh1234", "name": "Test Learner"}
    token = livekit_routes._issue_handoff(user, "One-Sample Z Test!")
    claims = livekit_routes._verify_handoff("Bearer " + token)

    assert claims["identity"] == "guest_abcdefgh1234"
    assert claims["name"] == "Test Learner"
    assert claims["lesson"] == "one_sample_z_test"
    assert claims["room"].startswith("crara_one_sample_z_test_")
    assert claims["typ"] == "crara-classroom-handoff"


def test_tampered_handoff_token_is_rejected(monkeypatch):
    from app.livekit import routes as livekit_routes

    monkeypatch.setattr(livekit_routes, "_handoff_secret", lambda: b"unit-test-secret")
    token = livekit_routes._issue_handoff({"id": "guest_abcdefgh1234", "name": "Learner"}, "z_test")
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(HTTPException) as exc:
        livekit_routes._verify_handoff("Bearer " + tampered)
    assert exc.value.status_code == 401
