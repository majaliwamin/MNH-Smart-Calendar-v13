"""WhatsApp reminder checks: phone numbers, wording, lead-time windows, endpoints."""
import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.services import reminders, whatsapp

TZ = ZoneInfo("Africa/Blantyre")


def test_phone_numbers_normalise_to_e164():
    assert whatsapp.normalise_phone("+265 881 988 156") == "265881988156"
    assert whatsapp.normalise_phone("0881988156") == "265881988156"
    assert whatsapp.normalise_phone("265881988156") == "265881988156"
    assert whatsapp.normalise_phone("881988156") == "265881988156"
    assert whatsapp.normalise_phone("00265881988156") == "265881988156"
    with pytest.raises(whatsapp.WhatsAppError):
        whatsapp.normalise_phone("   ")


def test_message_names_the_sender_the_module_code_and_the_lecturer():
    session = {
        "code": "PNIM-8100",
        "module_title": "Pregnancy and Neonatal Immunology",
        "weekday": "Wednesday",
        "date": dt.date(2026, 11, 18),
        "start": "08:00",
        "end": "10:00",
        "lecturer": "D Mzinza",
    }
    text = reminders.reminder_text(session, 10)
    assert "Maternal & Neonatal Health Smart Time Table" in text
    assert "PNIM-8100" in text
    assert "Pregnancy and Neonatal Immunology" in text
    assert "D Mzinza" in text
    assert "08:00–10:00" in text
    assert "Starts in 10 minutes" in text


def test_unknown_lecturer_is_stated_rather_than_invented():
    text = reminders.reminder_text({"code": "X", "start": "08:00", "end": "09:00"}, 20)
    assert "Lecturer: not assigned" in text
    assert "Starts in 20 minutes" in text


def test_each_lead_time_fires_in_its_own_window_and_once_only():
    session = {"code": "MIPN 8100", "weekday": "Monday", "date": dt.date(2026, 11, 16), "start": "10:00", "end": "12:00"}
    starts_at = dt.datetime(2026, 11, 16, 10, 0, tzinfo=TZ)
    leads = [10, 20, 30]

    def due(minutes_before, seconds=0):
        now = starts_at - dt.timedelta(minutes=minutes_before) + dt.timedelta(seconds=seconds)
        return [lead for _, lead in reminders.due_reminders([session], now, leads, window_seconds=60)]

    assert due(30) == [30]
    assert due(30, 30) == [30]          # a late tick still delivers
    assert due(29) == []
    assert due(20) == [20]
    assert due(10) == [10]
    assert due(0) == []
    assert due(1) == []


def test_reminder_keys_are_unique_per_session_lead_and_number():
    session = {"code": "MIPN 8100", "date": dt.date(2026, 11, 16), "start": "10:00"}
    first = reminders._key(session, 10, "265881988156")
    assert first == reminders._key(dict(session), 10, "265881988156")
    assert first != reminders._key(session, 20, "265881988156")
    assert first != reminders._key(session, 10, "265999999999")
    assert first.startswith("2026-11-16|MIPN 8100|10:00|10|")


def test_default_lead_times_are_ten_twenty_and_thirty():
    assert reminders.DEFAULT_LEADS == (10, 20, 30)
    assert "Maternal & Neonatal Health Smart Time Table" == whatsapp.WHATSAPP_SENDER_NAME


def test_sample_send_is_open_in_development_and_reports_missing_credentials(monkeypatch):
    monkeypatch.delenv("MNH_WA_BRIDGE_URL", raising=False)
    monkeypatch.delenv("MNH_ENV", raising=False)
    from app.main import app

    with TestClient(app) as client:
        anonymous = client.post("/api/reminders/test", json={"to": "+265881988156"})
    assert anonymous.status_code == 503  # public route; sending is unavailable without bridge configuration
    message = anonymous.json()["error"]
    assert "MNH_WA_BRIDGE_URL" in message


def test_status_describes_the_sender_without_leaking_credentials_or_numbers():
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/reminders")
    assert response.status_code == 200
    body = response.json()
    assert body["whatsapp"]["sender"] == "Maternal & Neonatal Health Smart Time Table"
    assert "bearer" not in str(body).lower()
    assert body["settings"]["recipients"] == []


# ---- WhatsApp groups ----------------------------------------------------------------------
def _use_temp_storage(monkeypatch, tmp_path):
    from app import config
    from app.database import connection
    monkeypatch.setattr(config, "DATABASE_DIR", tmp_path / "database")
    monkeypatch.setattr(connection, "DATABASE_PATH", tmp_path / "database" / "calendar.db")
    monkeypatch.setenv("MNH_ENV", "development")


def test_reminder_settings_accept_a_group_chat_id(monkeypatch, tmp_path):
    import json
    _use_temp_storage(monkeypatch, tmp_path)
    from app.database.connection import database
    with database() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            ("settings", "reminders", json.dumps({
                "enabled": True, "leadMinutes": [10],
                "recipients": ["+265881988156", "120363043999999999@g.us", "not a number"],
            }), 0),
        )
    assert reminders.settings()["recipients"] == ["265881988156", "120363043999999999@g.us"]


def test_sample_send_can_target_a_group(monkeypatch):
    import io, json, urllib.request
    monkeypatch.setenv("MNH_WA_BRIDGE_URL", "http://bridge.test")
    sent = []

    def fake_urlopen(request, timeout=None):
        sent.append(json.loads(request.data.decode("utf-8")))
        return io.BytesIO(b'{"ok":true}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = reminders.send_test("120363043999999999@g.us")
    assert result["isGroup"] is True
    assert sent[0]["chatId"] == "120363043999999999@g.us"


def test_sample_send_still_normalises_individual_numbers(monkeypatch):
    import io, json, urllib.request
    monkeypatch.setenv("MNH_WA_BRIDGE_URL", "http://bridge.test")
    sent = []

    def fake_urlopen(request, timeout=None):
        sent.append(json.loads(request.data.decode("utf-8")))
        return io.BytesIO(b'{"ok":true}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = reminders.send_test("+265 881 988 156")
    assert result["to"] == "265881988156"
    assert sent[0]["chatId"] == "265881988156@c.us"

