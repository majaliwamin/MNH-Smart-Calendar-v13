import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.database import connection
from app.main import app
from app.services import backup_service

ROOT = Path(__file__).resolve().parents[1]
CLASSROOM_DIR = ROOT / "frontend" / "resources" / "crara-classroom"


def _test_storage(monkeypatch, tmp_path):
    database_dir = tmp_path / "database"
    monkeypatch.setattr(config, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(connection, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MNH_ENV", "development")


def test_whiteboard_instruction_contract_is_whitelisted_and_code_free():
    from app.class_rep import whiteboard

    assert whiteboard.WHITEBOARD_INSTRUCTIONS == frozenset({
        "WRITE_TEXT", "DRAW_STROKE", "DRAW_LINE", "DRAW_ARROW", "DRAW_CIRCLE",
        "DRAW_RECTANGLE", "DRAW_CURVE", "DRAW_GRAPH", "RENDER_EQUATION",
        "HIGHLIGHT", "ERASE", "MOVE_OBJECT", "RESIZE_OBJECT", "EDIT_TEXT",
        "ADD_PAGE", "DELETE_PAGE", "NAVIGATE_PAGE", "UNDO", "REDO",
        "CLEAR_BOARD", "ZOOM", "PAN",
    })
    clean = whiteboard.validate_instruction({
        "type": "WRITE_TEXT",
        "args": {"text": "H0: no effect", "x": 80, "y": 120, "style": {"color": "#2563eb", "width": 4}},
    })
    assert clean == {
        "type": "WRITE_TEXT",
        "args": {"text": "H0: no effect", "x": 80.0, "y": 120.0, "style": {"color": "#2563eb", "width": 4}},
    }
    assert whiteboard.validate_instruction({"type": "RUN_CODE", "args": {}}) is None
    assert whiteboard.validate_instruction({
        "type": "WRITE_TEXT", "args": {"text": "x", "code": "alert(1)"}
    }) is None
    assert whiteboard.validate_instruction({
        "type": "RENDER_EQUATION", "args": {"latex": "z", "script": "fetch('/admin')"}
    }) is None
    assert whiteboard.validate_instruction({
        "type": "WRITE_TEXT", "args": {"text": "Physics review", "x": 80, "y": 120}
    }) is None
    assert whiteboard._has_banned_output("legacy ScholarMW lesson") is True
    assert whiteboard.parse_payload('```json\n{"narration":"hello"}\n```') == {"narration": "hello"}


def test_whiteboard_instructions_filter_untrusted_steps(monkeypatch):
    from app.class_rep import whiteboard

    payload = {
        "narration": "State the null hypothesis, then compute the test statistic.",
        "caption": "Hypothesis testing decision flow",
        "instructions": [
            {"type": "WRITE_TEXT", "args": {"text": "H0 and H1", "x": 100, "y": 120}},
            {"type": "RENDER_EQUATION", "args": {"latex": "z=\\frac{\\bar{x}-\\mu}{s/\\sqrt{n}}", "x": 100, "y": 220}},
            {"type": "EXECUTE_JAVASCRIPT", "args": {"code": "alert(1)"}},
            {"type": "WRITE_TEXT", "args": {"text": "x", "onclick": "bad()"}},
        ],
    }
    monkeypatch.setattr(
        whiteboard,
        "complete",
        lambda messages: (json.dumps(payload), "unit-test-provider", "unit-model"),
    )
    result = whiteboard.generate_instructions(whiteboard.WhiteboardInstructionRequest(prompt="How do I test H0?"))
    assert result.provider == "unit-test-provider"
    assert [item["type"] for item in result.instructions] == ["WRITE_TEXT", "RENDER_EQUATION"]
    assert result.speak is True
    assert result.control["type"] == "teaching"
    assert result.control["value"] == {"value": "teaching"}
    assert "CRARA" in result.narration or "hypothesis" in result.narration.lower()


def test_whiteboard_instructions_fall_back_without_provider(monkeypatch):
    from app.class_rep import whiteboard
    from app.class_rep.providers import ProviderError

    def fail(_messages):
        raise ProviderError("offline", category="not_configured")

    monkeypatch.setattr(whiteboard, "complete", fail)
    result = whiteboard.generate_instructions(whiteboard.WhiteboardInstructionRequest(prompt="Explain p-values"))
    assert result.provider == "crara-whiteboard-local-v1"
    assert result.instructions
    assert all(item["type"] in whiteboard.WHITEBOARD_INSTRUCTIONS for item in result.instructions)
    assert {item["type"] for item in result.instructions} >= {"WRITE_TEXT", "RENDER_EQUATION", "DRAW_GRAPH"}
    assert result.control["type"] == "teaching"
    assert "p-value" in result.narration


def test_whiteboard_session_endpoints_require_host_and_persist(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    from app.class_rep import whiteboard

    monkeypatch.setattr(
        whiteboard,
        "complete",
        lambda messages: (json.dumps({
            "narration": "Compare the p-value with alpha.",
            "caption": "Decision rule",
            "instructions": [{"type": "WRITE_TEXT", "args": {"text": "p < alpha", "x": 80, "y": 120}}],
        }), "unit-test-provider", "unit-model"),
    )
    with TestClient(app) as client:
        client.get("/api/class-rep/auth/me")
        generated = client.post("/api/class-rep/whiteboard/instructions", json={
            "prompt": "When do I reject H0?", "from": "Student", "mode": "Active"
        })
        assert generated.status_code == 200
        assert generated.json()["instructions"][0]["type"] == "WRITE_TEXT"

        saved = client.post("/api/class-rep/whiteboard/session", json={
            "key": "crara_hypothesis_testing_abc123",
            "pages": [{"id": "page-1", "objects": []}],
            "pageIndex": 0,
            "chatMode": "Question Queue",
            "permissions": {"canWrite": True, "boardLocked": False},
        })
        assert saved.status_code == 403  # guest is a student

        from app.class_rep import memory

        host = memory.create_account("Host", "majaliwamin@gmail.com", "strong-password-123")
        client.cookies.set("cara_session", memory.create_session(host["id"]), path="/")
        saved = client.post("/api/class-rep/whiteboard/session", json={
            "key": "crara_hypothesis_testing_abc123",
            "pages": [{"id": "page-1", "objects": []}],
            "pageIndex": 0,
            "chatMode": "Question Queue",
            "permissions": {"canWrite": True, "boardLocked": False},
        })
        assert saved.status_code == 200
        loaded = client.get("/api/class-rep/whiteboard/session", params={"key": "crara_hypothesis_testing_abc123"})
        assert loaded.status_code == 200
        assert loaded.json()["session"]["chatMode"] == "Question Queue"
        assert loaded.json()["session"]["pages"][0]["id"] == "page-1"


def test_whiteboard_control_tokens_are_host_issued_and_verified(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    from app.class_rep import memory

    host = memory.create_account("Host", "majaliwamin@gmail.com", "strong-password-123")
    host_token = memory.create_session(host["id"])
    with TestClient(app) as client:
        client.get("/api/class-rep/auth/me")
        denied = client.post("/api/class-rep/whiteboard/control", json={
            "key": "crara_hypothesis_testing_room",
            "type": "mode",
            "value": {"mode": "Question Queue"},
        })
        assert denied.status_code == 403

        client.cookies.set("cara_session", host_token, path="/")
        issued = client.post("/api/class-rep/whiteboard/control", json={
            "key": "crara_hypothesis_testing_room",
            "type": "mode",
            "value": {"mode": "Question Queue"},
        })
        assert issued.status_code == 200
        body = issued.json()
        assert body["value"] == {"mode": "Question Queue"}
        assert body["token"]

        teaching = client.post("/api/class-rep/whiteboard/control", json={
            "key": "crara_hypothesis_testing_room",
            "type": "teaching",
            "value": {"value": "stopped"},
        })
        assert teaching.status_code == 200
        teaching_body = teaching.json()
        assert teaching_body["value"] == {"value": "stopped"}
        assert client.post("/api/class-rep/whiteboard/control", json={
            "key": "crara_hypothesis_testing_room",
            "type": "teaching",
            "value": {"value": "run-code"},
        }).status_code == 400

    with TestClient(app) as student:
        student.get("/api/class-rep/auth/me")
        authorized = student.post("/api/class-rep/whiteboard/authorize", json={
            "key": "crara_hypothesis_testing_room",
            "type": "mode",
            "value": body["value"],
            "token": body["token"],
        })
        assert authorized.status_code == 200
        assert student.post("/api/class-rep/whiteboard/authorize", json={
            "key": "crara_hypothesis_testing_room",
            "type": "teaching",
            "value": teaching_body["value"],
            "token": teaching_body["token"],
        }).status_code == 200

        tampered = student.post("/api/class-rep/whiteboard/authorize", json={
            "key": "crara_hypothesis_testing_room",
            "type": "mode",
            "value": {"mode": "Silent monitoring"},
            "token": body["token"],
        })
        assert tampered.status_code == 403
        assert student.post("/api/class-rep/whiteboard/authorize", json={
            "key": "crara_hypothesis_testing_room",
            "type": "mode",
            "value": body["value"],
            "token": body["token"] + "x",
        }).status_code == 403


def test_handoff_carries_server_derived_role(monkeypatch):
    from app.livekit import routes as livekit_routes

    host = {"id": "user_abc123", "name": "Host", "email": "majaliwamin@gmail.com"}
    student = {"id": "user_def456", "name": "Student", "email": "student@example.org"}
    assert livekit_routes.classroom_role(host) == "host"
    assert livekit_routes.classroom_role(student) == "student"
    assert livekit_routes.classroom_role({"id": "guest_abcdefgh1234", "name": "Guest"}) == "student"
    assert livekit_routes.classroom_permissions(host, "room-1")["canControl"] is True
    assert livekit_routes.classroom_permissions(student, "room-1")["canControl"] is False

    monkeypatch.setattr(livekit_routes, "_handoff_secret", lambda: b"unit-test-secret")
    claims = livekit_routes._verify_handoff("Bearer " + livekit_routes._issue_handoff(host, "Hypothesis Testing"))
    assert claims["role"] == "host"
    assert claims["permissions"]["canControl"] is True
    assert claims["permissions"]["room"] == claims["room"]


def test_whiteboard_assets_are_wired_without_branding_or_build_change():
    html = (CLASSROOM_DIR / "index.html").read_text(encoding="utf-8")
    js = (CLASSROOM_DIR / "crara-whiteboard.js").read_text(encoding="utf-8")
    css = (CLASSROOM_DIR / "crara-whiteboard.css").read_text(encoding="utf-8")
    bundle = (CLASSROOM_DIR / "crara-classroom.js").read_text(encoding="utf-8")
    worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    parent = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")

    assert "crara-whiteboard.js?v=crara-classroom-v5" in html
    assert "crara-whiteboard.css?v=crara-classroom-v5" in html
    assert 'data-crara-classroom-build="crara-classroom-v5"' in html
    assert "/resources/crara-classroom/crara-whiteboard.js" in worker
    assert "/resources/crara-classroom/crara-whiteboard.css" in worker
    assert 'url.searchParams.set("role", result.role || "student")' in parent
    assert 'url.searchParams.set("permissions", JSON.stringify(result.permissions || {}))' in parent
    assert "publishWhiteboardData:wh" in bundle
    assert "Cr&&Cr.onChat&&Cr.onChat(Aa)" in bundle
    assert "Cr&&Cr.onMedia&&Cr.onMedia(u)" in bundle
    assert 'children:"Whiteboard"' in bundle
    assert "/api/class-rep/whiteboard/instructions" in js
    assert "/api/class-rep/whiteboard/session" in js
    assert "function startLessonIntro()" in js
    assert "startLessonIntro();" in js
    assert "startLessonIntro: startLessonIntro" in js
    assert "/api/class-rep/whiteboard/control" in js
    assert "/api/class-rep/whiteboard/authorize" in js
    assert 'packet.type === "question"' in js
    assert 'packet.type === "question-answered"' in js
    assert 'publish("question", { id: cleanText(message.id, 80)' in js
    assert "const hostQuestion = isHost() && message.mine === true;" in js
    assert "function authorizeControl(packet)" in js
    assert "async function hostSetTeaching(value)" in js

    for content in (html, js, css, bundle):
        lowered = content.lower()
        assert "penrose" not in lowered
        assert "scholarmw" not in lowered
        assert "voice training" not in lowered
        assert "vtc" not in lowered
        assert "your logo" not in lowered
        assert "physics" not in lowered
        assert "visual" not in lowered or content is bundle  # legacy bundle labels are untouched
