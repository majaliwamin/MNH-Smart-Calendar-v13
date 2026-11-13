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


def test_sample_send_requires_an_editor_and_reports_missing_credentials(monkeypatch):
    monkeypatch.delenv("MNH_WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("MNH_WHATSAPP_PHONE_ID", raising=False)
    monkeypatch.delenv("MNH_ENV", raising=False)
    from app.main import app

    with TestClient(app) as client:
        anonymous = client.post("/api/reminders/test", json={"to": "+265881988156"})
        assert anonymous.status_code == 401, "the test send must never be open to the public"
        assert client.post("/api/auth", json={"password": "rep"}).status_code == 200
        response = client.post("/api/reminders/test", json={"to": "+265881988156"})
    assert response.status_code == 503
    message = response.json()["error"]
    assert "MNH_WHATSAPP_TOKEN" in message and "MNH_WHATSAPP_PHONE_ID" in message


def test_status_describes_the_sender_without_leaking_credentials_or_numbers():
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/reminders")
    assert response.status_code == 200
    body = response.json()
    assert body["whatsapp"]["sender"] == "Maternal & Neonatal Health Smart Time Table"
    assert "bearer" not in str(body).lower()
    assert body["settings"]["recipients"] == []
