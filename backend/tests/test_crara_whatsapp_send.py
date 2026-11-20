import pytest
from fastapi.testclient import TestClient

from app.class_rep.whatsapp_send import SendError, parse_request
from app.config import WHATSAPP_SENDER_NAME


def _storage(monkeypatch, tmp_path):
    from app import config
    from app.database import connection
    from app.services import backup_service

    database_dir, backup_dir = tmp_path / "database", tmp_path / "backups"
    database_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(config, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(connection, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "BACKUP_DIR", backup_dir)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MNH_ENV", "development")


def _student_group(actor="editor"):
    from app.services import comm_contacts

    return comm_contacts.upsert_contact(actor, {
        "name": "MNH PhD students",
        "kind": "group",
        "phone": "120363099999999999@g.us",
        "category": "student",
        "consent": {"whatsapp": True, "voice": False},
    })


def test_parse_request_only_accepts_explicit_send_and_confirm_phrases():
    preview = parse_request("Send a WhatsApp message to the students: Class is at 13:30 tomorrow.")
    assert preview == {"kind": "preview", "body": "Class is at 13:30 tomorrow.", "target": "the students"}

    chichewa = parse_request("Tumiza uthenga kwa ophunzira wakuti Msonkhano ulipo Lachisanu.")
    assert chichewa and chichewa["kind"] == "preview"
    assert parse_request("CONFIRM SEND A1B2C3") == {"kind": "confirm", "token": "A1B2C3"}
    assert parse_request("Draft a WhatsApp message to the students about the seminar.") is None
    assert parse_request("What can you do?") is None


def test_preview_then_confirm_sends_once_through_waha_bridge(monkeypatch, tmp_path):
    _storage(monkeypatch, tmp_path)
    monkeypatch.setenv("MNH_WA_BRIDGE_URL", "https://wa.test")
    monkeypatch.setenv("MNH_WA_BRIDGE_TOKEN", "secret")
    from app.class_rep import whatsapp_send

    calls = []
    def fake_send(target, body):
        calls.append((target, body))
        return {"ok": True, "id": "wamid.1"}

    monkeypatch.setattr(whatsapp_send.wa_bridge, "send_text", fake_send)
    group = _student_group()

    preview = whatsapp_send.handle(
        "user-1", "Send a WhatsApp message to the students: Class is at 13:30 tomorrow.", "EN")
    assert preview["provider"] == "CRARA WhatsApp send"
    assert "Nothing has been sent yet." in preview["reply"]
    assert "CONFIRM SEND " + preview["token"] in preview["reply"]
    assert calls == []

    sent = whatsapp_send.handle("user-1", "CONFIRM SEND " + preview["token"], "EN")
    assert "Sent via WhatsApp to MNH PhD students." in sent["reply"]
    assert sent["model"] == "WAHA bridge"
    assert calls == [(group["phone"], WHATSAPP_SENDER_NAME + "\n\nClass is at 13:30 tomorrow.")]

    with pytest.raises(SendError, match="expired or was already used"):
        whatsapp_send.handle("user-1", "CONFIRM SEND " + preview["token"], "EN")
    assert len(calls) == 1


def test_preview_is_blocked_without_a_consented_student_group(monkeypatch, tmp_path):
    _storage(monkeypatch, tmp_path)
    from app.class_rep import whatsapp_send
    from app.services import comm_contacts

    comm_contacts.upsert_contact("editor", {
        "name": "Staff group",
        "kind": "group",
        "phone": "120363088888888888@g.us",
        "category": "staff",
        "consent": {"whatsapp": True},
    })
    with pytest.raises(SendError, match="No saved student WhatsApp group"):
        whatsapp_send.handle("user-1", "Send a WhatsApp message to students: Hello.", "EN")


def test_emergency_stop_blocks_confirmation(monkeypatch, tmp_path):
    _storage(monkeypatch, tmp_path)
    monkeypatch.setenv("MNH_WA_BRIDGE_URL", "https://wa.test")
    from app.class_rep import whatsapp_send
    from app.services import comm_service

    calls = []
    monkeypatch.setattr(whatsapp_send.wa_bridge, "send_text",
                        lambda target, body: calls.append((target, body)) or {"ok": True})
    _student_group()
    preview = whatsapp_send.handle("user-1", "Notify the class that the seminar is cancelled.", "EN")
    comm_service.set_emergency_stop("editor", True)
    with pytest.raises(SendError, match="emergency stop"):
        whatsapp_send.handle("user-1", "CONFIRM SEND " + preview["token"], "EN")
    assert calls == []


def test_chat_intercepts_explicit_whatsapp_send(monkeypatch, tmp_path):
    _storage(monkeypatch, tmp_path)
    from app.class_rep import routes, whatsapp_send
    from app.main import app

    monkeypatch.setattr(whatsapp_send, "handle", lambda user, message, language: {
        "reply": "Prepared. Reply CONFIRM SEND TEST12.",
        "provider": "CRARA WhatsApp send",
        "model": "pending-confirmation",
    } if "send" in message.casefold() else None)

    with TestClient(app) as client:
        created = client.post("/api/class-rep/auth/register", json={
            "name": "Class Rep", "email": "rep-wa@example.org", "password": "send-pass-123"})
        assert created.status_code == 200
        response = client.post("/api/class-rep/chat", json={
            "message": "Send a WhatsApp message to the students: Revision class at 14:00."})
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "CRARA WhatsApp send"
        assert data["model"] == "pending-confirmation"
        assert "CONFIRM SEND" in data["reply"]
