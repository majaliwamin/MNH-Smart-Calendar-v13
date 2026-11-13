"""Communications Centre tests: wa.me links, consent safeguards, drafts, jobs, ARI gating."""
import pytest
from fastapi.testclient import TestClient

from app import config
from app.database import connection
from app.main import app
from app.services import ari_service, ai_assistant, authentication, comm_contacts, comm_service
from app.services import whatsapp as _wa  # noqa: F401  (import order parity with test_reminders)


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
    token = authentication.create_session("rep")
    return {"mnh_session": token}


# ---- wa.me links -------------------------------------------------------------
def test_wa_links_use_digits_only_and_url_encoded_text():
    link = comm_service.wa_link("+265 881 988 156", "Reminder: PNIM\nStarts at 08:00")
    assert link.startswith("https://wa.me/265881988156?text=")
    assert "+" not in link.split("?")[0]
    assert "%0A" in link  # newline encoded, not raw


# ---- contacts and consent -------------------------------------------------------
def test_contact_requires_a_name_and_valid_phone():
    with pytest.raises(comm_contacts.ContactError):
        comm_contacts.upsert_contact("rep", {"name": "", "phone": "+265881988156"})
    with pytest.raises(comm_contacts.ContactError):
        comm_contacts.upsert_contact("rep", {"name": "Dr Banda", "phone": "123"})


def test_opt_out_and_dnc_block_preparation(monkeypatch, db):
    monkeypatch.setattr(comm_service, "emergency_stop", lambda: False)
    contact = comm_contacts.upsert_contact("rep", {"name": "Dr Banda", "phone": "0881988156"})
    # no consent yet
    with pytest.raises(comm_service.CommError):
        comm_service.create_draft("rep", [contact["id"]], "Hello")
    comm_contacts.set_consent("rep", contact["id"], "whatsapp", True)
    draft = comm_service.create_draft("rep", [contact["id"]], "Hello")
    assert draft["recipients"][0]["status"] == "ready"
    # opt-out blocks
    contact["optOut"] = True
    from app.services.comm_contacts import _write_doc
    _write_doc("comm_contacts", contact["id"], contact)
    with pytest.raises(comm_service.CommError):
        comm_service.create_draft("rep", [contact["id"]], "Hello")
    # DNC blocks
    contact["optOut"] = False
    _write_doc("comm_contacts", contact["id"], contact)
    comm_contacts.dnc_add("rep", "0881988156", "asked to stop")
    with pytest.raises(comm_service.CommError):
        comm_service.create_draft("rep", [contact["id"]], "Hello")


# ---- emergency stop ----------------------------------------------------------------
def test_emergency_stop_blocks_drafting_and_jobs(monkeypatch, tmp_path):
    monkeypatch.setattr(comm_service, "emergency_stop", lambda: True)
    with pytest.raises(comm_service.CommError):
        comm_service.schedule_job("rep", {"kind": "announcement", "runAt": "2099-01-01T08:00", "contactIds": ["x"]})


# ---- scheduled jobs create drafts only -------------------------------------------------
def test_due_job_creates_a_draft_and_never_sends(monkeypatch, db):
    monkeypatch.setattr(comm_service, "emergency_stop", lambda: False)
    contact = comm_contacts.upsert_contact("rep", {"name": "Dr Banda", "phone": "0881988156"})
    comm_contacts.set_consent("rep", contact["id"], "whatsapp", True)
    job = comm_service.schedule_job("rep", {
        "kind": "exam-reminder", "runAt": "2099-01-01T08:00",
        "title": "Pharmacology exam", "contactIds": [contact["id"]],
        "body": "Exam on Friday.",
    })
    # duplicate prevention
    with pytest.raises(comm_service.CommError):
        comm_service.schedule_job("rep", {
            "kind": "exam-reminder", "runAt": "2099-01-01T08:00",
            "title": "Other title", "contactIds": [contact["id"]], "body": "x",
        })
    import time as _time
    job["runEpoch"] = _time.time() - 60  # one minute overdue
    from app.services.comm_service import _write_doc
    _write_doc("comm_jobs", job["id"], job)
    result = comm_service.run_due_jobs()
    assert result["done"] == 1
    drafts = comm_service.draft_rows()
    assert len(drafts) == 1
    # the job produced a draft with links — not a sent message
    entry = drafts[0]
    assert entry["recipients"][0]["status"] in ("ready", "opened", "sent-manual")
    assert entry["links"][0]["link"].startswith("https://wa.me/")


def test_marking_status_transitions(monkeypatch, db):
    monkeypatch.setattr(comm_service, "emergency_stop", lambda: False)
    contact = comm_contacts.upsert_contact("rep", {"name": "Dr Banda", "phone": "0881988156"})
    comm_contacts.set_consent("rep", contact["id"], "whatsapp", True)
    draft = comm_service.create_draft("rep", [contact["id"]], "Hi")
    comm_service.mark_draft("rep", draft["id"], contact["id"], "opened")
    comm_service.mark_draft("rep", draft["id"], contact["id"], "sent-manual")
    rows = comm_service.draft_rows()
    assert rows[0]["recipients"][0]["status"] == "sent-manual"
    with pytest.raises(comm_service.CommError):
        comm_service.mark_draft("rep", draft["id"], contact["id"], "delivered-auto")  # not a legal state


# ---- ARI safeguards ------------------------------------------------------------------
def test_ari_call_blocked_without_consent_even_when_configured(monkeypatch, db):
    monkeypatch.setattr(ari_service, "configured", lambda: True)
    monkeypatch.setattr(ari_service, "_request", lambda *a, **k: {"id": "ch1"})
    contact = comm_contacts.upsert_contact("rep", {"name": "Dr Banda", "phone": "0881988156"})
    with pytest.raises(ari_service.ARIError):
        ari_service.request_call("rep", contact["id"], "check-in", checks={"consentOk": False, "dncOk": True, "windowOk": True})
    comm_contacts.set_consent("rep", contact["id"], "voice", True)
    call = ari_service.request_call("rep", contact["id"], "check-in", checks={"consentOk": True, "dncOk": True, "windowOk": True})
    assert call["state"] == "dialing"
    assert not call["recording"]  # recording off by default


def test_calling_window_default(monkeypatch):
    import datetime as dt
    monkeypatch.setenv("MNH_CALL_WINDOW_START", "08:00")
    monkeypatch.setenv("MNH_CALL_WINDOW_END", "18:00")
    ok, reason = comm_service.within_call_window(dt.datetime(2026, 11, 16, 7, 0, tzinfo=comm_service.TZ))
    assert not ok and "only allowed" in reason
    ok, _ = comm_service.within_call_window(dt.datetime(2026, 11, 16, 10, 0, tzinfo=comm_service.TZ))
    assert ok


def test_ari_reports_unconfigured_not_failure():
    info = ari_service.status()
    assert info["configured"] is False and "MNH_ARI_BASE_URL" in info["missing"]


# ---- AI drafting never sends ---------------------------------------------------------
def test_ai_disabled_without_key():
    assert ai_assistant.enabled() is False
    with pytest.raises(ai_assistant.AIError):
        ai_assistant.draft("Draft an exam reminder")


# ---- API surface -----------------------------------------------------------------------
def test_comm_endpoints_require_sign_in(client):
    assert client.get("/api/comm/contacts").status_code == 401
    assert client.post("/api/comm/drafts", json={"contactIds": [], "body": "x"}).status_code == 401


def test_contacts_flow_through_the_api(client, editor_session):
    response = client.post("/api/comm/contacts", json={"name": "Dr Banda", "phone": "0881988156"}, cookies=editor_session)
    assert response.status_code == 200
    contact_id = response.json()["id"]
    assert response.json()["phone"] == "265881988156"
    listed = client.get("/api/comm/contacts", cookies=editor_session).json()
    assert any(c["id"] == contact_id for c in listed["contacts"])
    # consent + dnc round trip
    client.post(f"/api/comm/contacts/{contact_id}/consent", json={"channel": "whatsapp", "granted": True}, cookies=editor_session)
    draft = client.post("/api/comm/drafts", json={"contactIds": [contact_id], "body": "Hello"}, cookies=editor_session)
    assert draft.status_code == 200
    assert draft.json()["links"][0]["link"].startswith("https://wa.me/265881988156")


def test_drafted_contacts_without_consent_are_handled_safely(client, editor_session):
    contact = client.post("/api/comm/contacts", json={"name": "No Consent", "phone": "0991777666"}, cookies=editor_session).json()
    consented = client.post("/api/comm/contacts", json={"name": "Consented", "phone": "0991777555"}, cookies=editor_session).json()
    client.post(f"/api/comm/contacts/{consented['id']}/consent", json={"channel": "whatsapp", "granted": True}, cookies=editor_session)
    # all recipients blocked -> the API refuses rather than producing a dead draft
    dead = client.post("/api/comm/drafts", json={"contactIds": [contact["id"]], "body": "Hi"}, cookies=editor_session)
    assert dead.status_code == 400
    # mixed recipients -> link only for the consented one
    mixed = client.post("/api/comm/drafts", json={"contactIds": [contact["id"], consented["id"]], "body": "Hi"}, cookies=editor_session)
    assert mixed.status_code == 200
    data = mixed.json()
    assert data["links"] and data["links"][0]["contactId"] == consented["id"]
    by_id = {r["contactId"]: r for r in data["recipients"]}
    assert by_id[contact["id"]]["status"] == "blocked"
