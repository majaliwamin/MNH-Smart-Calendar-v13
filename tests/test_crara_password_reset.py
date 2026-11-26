from pathlib import Path

from fastapi.testclient import TestClient

from app import config
from app.class_rep import routes as class_rep_routes
from app.class_rep import memory
from app.database import connection
from app.main import app
from app.services import backup_service, mail_service

ROOT = Path(__file__).resolve().parents[1]
BUILD = "2026.11.26-exams-hardening-v1"


def _test_storage(monkeypatch, tmp_path):
    database_dir = tmp_path / "database"
    monkeypatch.setattr(config, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(connection, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MNH_ENV", "development")
    class_rep_routes._RATE_BUCKETS.clear()


def test_password_reset_link_is_single_use_and_replaces_the_password(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    sent = []
    monkeypatch.setenv("MNH_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("MNH_SMTP_FROM", "CRARA <no-reply@example.test>")
    monkeypatch.setattr(mail_service, "send_text", lambda to, subject, body: sent.append((to, subject, body)))
    memory.create_account("Host", "majaliwamin@gmail.com", "old-password-123")

    with TestClient(app) as client:
        client.get("/api/class-rep/auth/me")
        response = client.post("/api/class-rep/auth/forgot-password", json={"email": "majaliwamin@gmail.com"})
        assert response.status_code == 200
        assert "If an account exists" in response.json()["message"]
        assert len(sent) == 1
        assert sent[0][0] == "majaliwamin@gmail.com"
        assert "Reset your CRARA password" in sent[0][1]
        token = sent[0][2].split("/?crara_reset=", 1)[1].splitlines()[0].strip()
        assert token

        reused = client.post("/api/class-rep/auth/reset-password", json={"token": "not-a-token", "password": "next-password-456"})
        assert reused.status_code == 400
        short = client.post("/api/class-rep/auth/reset-password", json={"token": token, "password": "x"})
        assert short.status_code == 400

        reset = client.post("/api/class-rep/auth/reset-password", json={"token": token, "password": "next-password-456"})
        assert reset.status_code == 200
        body = reset.json()
        assert body["authenticated"] is True
        assert body["password_reset"] is True
        assert body["user"]["email"] == "majaliwamin@gmail.com"

        again = client.post("/api/class-rep/auth/reset-password", json={"token": token, "password": "another-password-789"})
        assert again.status_code == 400

    with TestClient(app) as client:
        client.get("/api/class-rep/auth/me")
        assert client.post("/api/class-rep/auth/login", json={
            "email": "majaliwamin@gmail.com", "password": "old-password-123"
        }).status_code == 401
        assert client.post("/api/class-rep/auth/login", json={
            "email": "majaliwamin@gmail.com", "password": "next-password-456"
        }).status_code == 200


def test_forgot_password_does_not_reveal_unknown_accounts(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    sent = []
    monkeypatch.setenv("MNH_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("MNH_SMTP_FROM", "CRARA <no-reply@example.test>")
    monkeypatch.setattr(mail_service, "send_text", lambda to, subject, body: sent.append(to))

    with TestClient(app) as client:
        client.get("/api/class-rep/auth/me")
        response = client.post("/api/class-rep/auth/forgot-password", json={"email": "nobody@example.test"})
        assert response.status_code == 200
        assert response.json() == {"ok": True, "message": "If an account exists, a reset link has been sent."}
        assert sent == []


def test_crara_reset_ui_contract():
    js = (ROOT / "frontend" / "js" / "class-rep.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "class-rep.css").read_text(encoding="utf-8")
    assert 'el("button", "cr-auth-forgot", "Forgot password?")' in js
    assert "/api/class-rep/auth/forgot-password" in js
    assert "/api/class-rep/auth/reset-password" in js
    assert "crara_reset" in js
    assert "window.history.replaceState" in js
    assert ".cr-auth-forgot" in css
    assert ".cr-auth-reset[hidden]" in css

    routes = (ROOT / "backend" / "app" / "class_rep" / "routes.py").read_text(encoding="utf-8")
    assert '@router.post("/auth/forgot-password")' in routes
    assert '@router.post("/auth/reset-password")' in routes
    assert "MNH_SMTP_HOST" in (ROOT / ".env.example").read_text(encoding="utf-8")
    assert BUILD in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
