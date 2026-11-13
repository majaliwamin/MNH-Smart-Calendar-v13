"""AI-triggered sending: bridge transport, consent guards, schedule-change detection."""
import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.database import connection
from app.main import app
from app.services import ai_trigger, authentication, comm_contacts, wa_bridge


def configure_test_storage(monkeypatch, tmp_path):
    database_dir = tmp_path / "database"
    database_path = database_dir / "calendar.db"
    monkeypatch.setattr(config, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(connection, "DATABASE_PATH", database_path)
    monkeypatch.setenv("MNH_ENV", "development")
    authentication.SESSIONS.clear()


@pytest.fixture()
def db(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)


@pytest.fixture()
def client(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def editor_session():
    authentication.SESSIONS.clear()
    return {"mnh_session": authentication.create_session("rep")}


@pytest.fixture()
def bridge(monkeypatch):
    """A fake bridge: records payloads, always succeeds."""
    sent = []
    monkeypatch.setenv("MNH_WA_BRIDGE_URL", "http://bridge.test")
    import urllib.request

    def fake_urlopen(request, timeout=None):
        payload = json.loads(request.data.decode("utf-8"))
        sent.append(payload)
        import io
        return io.BytesIO(b'{"ok":true}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return sent


def consented_contact():
    contact = comm_contacts.upsert_contact("rep", {"name": "Dr Banda", "phone": "0881988156"})
    comm_contacts.set_consent("rep", contact["id"], "whatsapp", True)
    return contact


# ---- bridge transport -----------------------------------------------------------------
def test_bridge_send_waha_shape(bridge):
    result = wa_bridge.send_text("265881988156", "Hello")  # bridge takes digits; callers normalise
    assert result["ok"] is True
    assert bridge == [{"session": "default", "chatId": "265881988156@c.us", "text": "Hello"}]


def test_bridge_unconfigured_raises(monkeypatch):
    monkeypatch.delenv("MNH_WA_BRIDGE_URL", raising=False)
    with pytest.raises(wa_bridge.BridgeError):
        wa_bridge.send_text("265881988156", "Hello")


# ---- manual AI trigger -------------------------------------------------------------------
def test_ai_trigger_composes_and_sends_without_human_approval(db, bridge, monkeypatch):
    contact = consented_contact()
    monkeypatch.setattr(ai_trigger, "compose", lambda *a, **k: ("AI composed text", True))
    result = ai_trigger.trigger_now("rep", "announcement", "Exam moved to Friday.")
    assert result["sentCount"] == 1
    assert bridge[0]["chatId"] == f"{contact['phone']}@c.us"
    assert bridge[0]["text"] == "AI composed text"
    log = ai_trigger.trigger_log()
    assert log[0]["aiUsed"] is True and log[0]["sentCount"] == 1


def test_ai_trigger_refuses_without_consent(db, bridge):
    comm_contacts.upsert_contact("rep", {"name": "No Consent", "phone": "0991777666"})
    with pytest.raises(ai_trigger.TriggerError):
        ai_trigger.trigger_now("rep", "announcement", "Test")


def test_ai_trigger_refuses_dnc_and_optout(db, bridge):
    contact = consented_contact()
    comm_contacts.dnc_add("rep", contact["phone"], "asked to stop")
    with pytest.raises(ai_trigger.TriggerError):
        ai_trigger.trigger_now("rep", "announcement", "Test")


def test_ai_trigger_blocked_by_emergency_stop(db, bridge, monkeypatch):
    consented_contact()
    monkeypatch.setattr(ai_trigger, "comm_service_emergency_stop", lambda: True)
    with pytest.raises(ai_trigger.TriggerError):
        ai_trigger.trigger_now("rep", "announcement", "Test")
    assert bridge == []


def test_ai_trigger_compose_falls_back_to_template_without_ai(db, monkeypatch):
    monkeypatch.setattr(ai_trigger.ai_assistant, "draft", lambda *a, **k: (_ for _ in ()).throw(ai_trigger.ai_assistant.AIError("no key")))
    message, used = ai_trigger.compose("exam-reminder", "Pharmacology Friday 09:00.", [])
    assert used is False and "Pharmacology" in message


# ---- automatic trigger (schedule watcher) ---------------------------------------------------
def test_auto_check_baseline_then_changes(db, bridge, monkeypatch):
    consented_contact()
    monkeypatch.setenv("MNH_AI_TRIGGER_ENABLED", "1")
    monkeypatch.setattr(ai_trigger, "compose", lambda *a, **k: ("AI notice", True))
    from app.services import reminders
    sessions = [{"id": "cell-1", "date": "2026-11-16", "start": "08:00", "end": "10:00",
                 "code": "Immunology", "lecturer": "Dr Mzinza", "status": "scheduled"}]
    monkeypatch.setattr(reminders, "week_sessions", lambda now=None: sessions)
    first_run = ai_trigger.auto_check()
    assert first_run.get("checked") == "baseline" and bridge == []  # baseline sends nothing
    # now change the session and run again — AI should send automatically
    sessions[0] = {**sessions[0], "start": "09:00"}
    second_run = ai_trigger.auto_check()
    assert second_run["changes"] >= 1
    assert second_run["sent"] == 1 and bridge and bridge[0]["text"] == "AI notice"


def test_auto_check_disabled_by_default(db, bridge, monkeypatch):
    monkeypatch.delenv("MNH_AI_TRIGGER_ENABLED", raising=False)
    result = ai_trigger.auto_check()
    assert result["enabled"] is False and bridge == []


# ---- API -------------------------------------------------------------------------------------
def test_trigger_endpoint_requires_editor(client):
    assert client.post("/api/comm/ai/trigger", json={"kind": "announcement", "instructions": "x"}).status_code == 401


def test_trigger_endpoint_sends(client, editor_session, bridge, monkeypatch):
    consented_contact()
    monkeypatch.setattr(ai_trigger, "compose", lambda *a, **k: ("Hello from the AI", True))
    response = client.post("/api/comm/ai/trigger", json={"kind": "announcement", "instructions": "Test day notice"}, cookies=editor_session)
    assert response.status_code == 200
    assert response.json()["sentCount"] == 1
    assert bridge[0]["text"] == "Hello from the AI"
