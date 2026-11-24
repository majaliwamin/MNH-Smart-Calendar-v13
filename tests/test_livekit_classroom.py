from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import config
from app.database import connection
from app.main import app
from app.services import backup_service

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
    assert "Physics" not in js
    assert "Hypothesis Testing" in js
    assert "Hypothesis Testing \u2014 Shared Screen" in js
    assert "\u00b7 Hypothesis Testing \u00b7 Term 2" in js
    assert "CRARA" in js
    assert "Your CRARA classroom is ready" in js


def test_classroom_chat_has_voice_ask_without_delivery_noise():
    js = (CLASSROOM_DIR / "crara-classroom.js").read_text(encoding="utf-8")
    css = (CLASSROOM_DIR / "crara-classroom.css").read_text(encoding="utf-8")

    assert "Chat with CRARA and the room" not in js
    assert "CRARA answers here while the lesson continues" not in js
    assert 'children:"Sent"' not in js

    assert 'className:"voiceask"' in js
    assert "Ask CRARA by voice" in js
    assert "Stop voice question" in js
    assert "/api/class-rep/transcribe" in js
    assert "crara-voice-question.webm" in js
    assert "Voice question received. CRARA is answering in chat and on the board." in js
    assert "ue.narration||ue.body||ue.caption" in js, "chat bubbles must show the spoken answer, not the board title"
    assert ".compose button.voiceask" in css

    whiteboard = (CLASSROOM_DIR / "crara-whiteboard.js").read_text(encoding="utf-8")
    assert "/api/class-rep/speak" in whiteboard
    assert "speakNarration" in whiteboard


def test_crara_ui_offers_lesson_scoped_classroom_panel():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    assert "cr-classroom-panel" in js
    assert "crara-live-classroom-wrapper" in js
    assert "crara-live-classroom-frame" in js
    assert "/api/class-rep/livekit/handoff" in js
    assert "/api/class-rep/livekit/join-code" in js
    assert "classroomCodeInput" in js and "useClassroomCode" in js and "createClassroomCode" in js
    assert "join_code" in js
    assert "cr-classroom-launch" in js
    assert "cr-classroom-launch-status" in js
    assert "CRARA is opening live session…" in js
    assert "CRARA is opening live class…" in js
    assert "cr-classroom-button" not in js
    assert "Join 1:1 Classroom" not in js
    assert "camera; microphone; autoplay; display-capture; clipboard-write; fullscreen" in js
    assert "classroomPanel.requestFullscreen()" in js
    assert "Request fullscreen synchronously from the click gesture" in js
    assert "Reconnect" in js and "Fullscreen" in js and "Exit" in js

    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert ".cr-classroom-panel[hidden]{display:none!important}" in css
    assert ".cr-classroom-frame-wrap" in css
    assert ".cr-classroom-code-input" in css
    assert "#crara-live-classroom-frame" in css

    worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    assert "/resources/crara-classroom/index.html" in worker
    assert "/resources/crara-classroom/crara-classroom.js" in worker
    assert "/resources/crara-classroom/crara-classroom.css" in worker


def test_classroom_iframe_class_matches_css_and_fills_the_stage():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")

    assert 'frame.className = "cr-classroom-frame"' in js
    assert 'frame.style.width = "100%"' in js
    assert 'frame.style.height = "100%"' in js

    # The iframe class assigned in JS must have a real CSS rule, otherwise the
    # browser renders it at its default 300x150 size.
    rule = ".cr-classroom-frame{"
    assert rule in css
    body = css.split(rule, 1)[1].split("}", 1)[0]
    assert "display:block" in body
    assert "width:100%" in body
    assert "height:100%" in body

    id_rule = "#crara-live-classroom-frame{"
    assert id_rule in css
    id_body = css.split(id_rule, 1)[1].split("}", 1)[0]
    assert "width:100%!important" in id_body
    assert "height:100%!important" in id_body

    assert ".cr-classroom-panel:fullscreen" in css
    assert "height:100dvh!important" in css


def test_livekit_backend_routes_and_configuration_are_registered():
    routes = (ROOT / "backend" / "app" / "livekit" / "routes.py").read_text(encoding="utf-8")
    assert '@router.post("/api/class-rep/livekit/handoff")' in routes
    assert '@router.post("/api/class-rep/livekit/join-code")' in routes
    assert '@router.post("/api/class-rep/livekit/join-code/revoke")' in routes
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
    assert claims["role"] == "student"
    assert claims["permissions"]["canControl"] is False


def test_tampered_handoff_token_is_rejected(monkeypatch):
    from app.livekit import routes as livekit_routes

    monkeypatch.setattr(livekit_routes, "_handoff_secret", lambda: b"unit-test-secret")
    token = livekit_routes._issue_handoff({"id": "guest_abcdefgh1234", "name": "Learner"}, "z_test")
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(HTTPException) as exc:
        livekit_routes._verify_handoff("Bearer " + tampered)
    assert exc.value.status_code == 401


def _test_storage(monkeypatch, tmp_path):
    database_dir = tmp_path / "database"
    monkeypatch.setattr(config, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(connection, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MNH_ENV", "development")


def _configure_livekit(monkeypatch):
    from app.livekit import routes as livekit_routes

    livekit_routes._JOIN_CODES.clear()
    monkeypatch.setattr(livekit_routes, "LIVEKIT_URL", "wss://livekit.example.test")
    monkeypatch.setattr(livekit_routes, "LIVEKIT_API_KEY", "unit-test-key")
    monkeypatch.setattr(livekit_routes, "LIVEKIT_API_SECRET", "unit-test-secret")
    monkeypatch.setattr(livekit_routes, "_handoff_secret", lambda: b"unit-test-secret")
    return livekit_routes


def test_host_join_code_joins_a_student_to_the_host_room(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    livekit_routes = _configure_livekit(monkeypatch)
    from app.class_rep import classroom_permissions, memory

    assert "crara-e2e-host@example.com" not in classroom_permissions._DEFAULT_HOST_EMAILS
    host = memory.create_account("Host", "majaliwamin@gmail.com", "strong-password-123")
    host_token = memory.create_session(host["id"])
    with TestClient(app) as client:
        client.get("/api/class-rep/auth/me")
        client.cookies.set("cara_session", host_token, path="/")
        created = client.post("/api/class-rep/livekit/join-code", json={"lesson": "Hypothesis Testing"})
        assert created.status_code == 200
        issued = created.json()
        assert len(issued["code"]) == livekit_routes._JOIN_CODE_LENGTH
        assert issued["room"].startswith("crara_hypothesis_testing_")
        assert issued["expires_in"] > 0

    with TestClient(app) as student:
        student.cookies.set("cara_guest", "guest_student_1234", path="/")
        student.get("/api/class-rep/auth/me")
        assert student.post("/api/class-rep/livekit/join-code", json={"lesson": "Hypothesis Testing"}).status_code == 403
        assert student.post("/api/class-rep/livekit/handoff", json={
            "lesson": "Hypothesis Testing", "join_code": "AAAAAAAA"
        }).status_code == 400
        assert student.post("/api/class-rep/livekit/handoff", json={
            "lesson": "Different Lesson", "join_code": issued["code"]
        }).status_code == 400

        response = student.post("/api/class-rep/livekit/handoff", json={
            "lesson": "Hypothesis Testing", "join_code": issued["code"]
        })
        assert response.status_code == 200
        body = response.json()
        assert body["room"] == issued["room"]
        assert body["identity"] == "guest_student_1234"
        assert body["role"] == "student"
        assert body["permissions"]["canControl"] is False
        assert body["joined_with_code"] is True
        claims = livekit_routes._verify_handoff("Bearer " + body["token"])
        assert claims["room"] == issued["room"]
        assert claims["identity"] == "guest_student_1234"

    with TestClient(app) as client:
        client.get("/api/class-rep/auth/me")
        client.cookies.set("cara_session", host_token, path="/")
        revoked = client.post("/api/class-rep/livekit/join-code/revoke", json={"code": issued["code"]})
        assert revoked.status_code == 200
    with TestClient(app) as student:
        student.cookies.set("cara_guest", "guest_student_1234", path="/")
        student.get("/api/class-rep/auth/me")
        assert student.post("/api/class-rep/livekit/handoff", json={
            "lesson": "Hypothesis Testing", "join_code": issued["code"]
        }).status_code == 400


def test_cohost_grant_can_create_and_revoke_a_room_scoped_join_code(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    livekit_routes = _configure_livekit(monkeypatch)
    from app.class_rep import memory

    host = memory.create_account("Host", "majaliwamin@gmail.com", "strong-password-123")
    cohost = memory.create_account("Cohost", "cohost@example.org", "strong-password-123")
    host_token = memory.create_session(host["id"])
    cohost_token = memory.create_session(cohost["id"])
    room = livekit_routes._room_name(str(host["id"]), "hypothesis_testing")

    with TestClient(app) as client:
        client.get("/api/class-rep/auth/me")
        client.cookies.set("cara_session", host_token, path="/")
        granted = client.post("/api/class-rep/whiteboard/control", json={
            "key": room,
            "type": "cohost",
            "value": {"enabled": True},
        })
        assert granted.status_code == 200
        authority = granted.json()["token"]

    with TestClient(app) as client:
        client.get("/api/class-rep/auth/me")
        client.cookies.set("cara_session", cohost_token, path="/")
        assert client.post("/api/class-rep/livekit/join-code", json={
            "lesson": "Hypothesis Testing",
        }).status_code == 403

        created = client.post("/api/class-rep/livekit/join-code", json={
            "lesson": "Hypothesis Testing",
            "authority": authority,
        })
        assert created.status_code == 200
        issued = created.json()
        assert issued["room"] == room

        wrong_lesson = client.post("/api/class-rep/livekit/join-code", json={
            "lesson": "Different Lesson",
            "authority": authority,
        })
        assert wrong_lesson.status_code == 403

        tampered = client.post("/api/class-rep/livekit/join-code", json={
            "lesson": "Hypothesis Testing",
            "authority": authority + "x",
        })
        assert tampered.status_code == 403

        revoked = client.post("/api/class-rep/livekit/join-code/revoke", json={
            "code": issued["code"],
            "authority": authority,
        })
        assert revoked.status_code == 200

    with TestClient(app) as guest:
        guest.get("/api/class-rep/auth/me")
        guest.cookies.set("cara_guest", "guest_cohost_1234", path="/")
        denied = guest.post("/api/class-rep/livekit/join-code", json={
            "lesson": "Hypothesis Testing",
            "authority": authority,
        })
        assert denied.status_code == 403


def test_cohost_authority_is_forwarded_from_the_classroom_without_granting_board_control():
    whiteboard = (CLASSROOM_DIR / "crara-whiteboard.js").read_text(encoding="utf-8")
    parent = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")

    assert "function notifyParentCohostGrant(enabled, authority)" in whiteboard
    assert 'type: "crara-classroom-cohost"' in whiteboard
    assert "notifyParentCohostGrant(value.enabled, packet.authority)" in whiteboard
    assert "setCohost(value.enabled, false, false)" in whiteboard
    assert "cohostAuthority" not in whiteboard.split("getState:", 1)[1].split("setCaption:", 1)[0]

    assert 'data.type !== "crara-classroom-cohost"' in parent
    assert "event.source !== frame.contentWindow" in parent
    assert "state.classroom.cohostAuthority" in parent
    assert "state.classroom.cohostRoom" in parent
    assert "authority: state.classroom.cohostAuthority" in parent
    assert "host or an authorized co-host" in parent
    assert 'result.role === "host"' in parent
    assert "createClassroomCode({ auto: true" in parent
    assert "!state.classroom.joinCode" in parent
    assert "setClassroomCodeDisplay" in parent
    assert ".cr-classroom-code-display" in css
