"""Public chat API, identity, privacy, and retention tests."""
from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


@pytest.fixture()
def app_ctx(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ENV", "test")
    monkeypatch.setenv("MNH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "")
    for mod in [
        "app.config",
        "app.database.connection",
        "app.database.postgres",
        "app.services.authentication",
        "app.public_chat.store",
        "app.public_chat.routes",
        "app.main",
    ]:
        sys.modules.pop(mod, None)
    import app.config as config
    import app.database.connection as connection
    import app.services.authentication as authentication
    import app.public_chat.store as store
    import app.main as main

    importlib.reload(config)
    importlib.reload(connection)
    importlib.reload(authentication)
    importlib.reload(store)
    importlib.reload(main)
    return main.app, authentication, store


def _auth_client(app, authentication, role="administrator"):
    token = authentication.create_session(role)
    client = TestClient(app)
    client.cookies.set("mnh_session", token)
    return client


def test_public_chat_join_assigns_unique_mnh_code(app_ctx):
    app, authentication, store = app_ctx
    c1 = TestClient(app)
    r1 = c1.post("/api/public-chat/join", json={"display_name": "Alpha"})
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["joined"] is True
    assert d1["participant"]["code"].startswith("MNH-")
    assert len(d1["participant"]["code"]) == 8

    c2 = TestClient(app)
    r2 = c2.post("/api/public-chat/join", json={"display_name": "Beta"})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["participant"]["code"] != d1["participant"]["code"]


def test_public_chat_requires_join_for_messages(app_ctx):
    app, authentication, store = app_ctx
    client = TestClient(app)
    # status creates guest cookie context but not joined
    s = client.get("/api/public-chat/status")
    assert s.status_code == 200
    assert s.json()["joined"] is False
    r = client.get("/api/public-chat/messages")
    assert r.status_code == 403


def test_private_message_visibility_and_media_access(app_ctx):
    app, authentication, store = app_ctx
    c1 = TestClient(app)
    c2 = TestClient(app)
    c3 = TestClient(app)
    j1 = c1.post("/api/public-chat/join", json={"display_name": "One"}).json()["participant"]
    j2 = c2.post("/api/public-chat/join", json={"display_name": "Two"}).json()["participant"]
    j3 = c3.post("/api/public-chat/join", json={"display_name": "Three"}).json()["participant"]

    # private message from c1 to c2
    r = c1.post("/api/public-chat/messages", json={"text": "secret", "private_recipient_code": j2["code"]})
    assert r.status_code == 200
    msg = r.json()["message"]
    assert msg["kind"] == "private"

    m2 = c2.get("/api/public-chat/messages").json()["messages"]
    m3 = c3.get("/api/public-chat/messages").json()["messages"]
    assert any(m["id"] == msg["id"] for m in m2)
    assert not any(m["id"] == msg["id"] for m in m3)

    # voice note private
    audio = io.BytesIO(b"fakewebmdata")
    files = {"file": ("note.webm", audio, "audio/webm")}
    data = {"private_recipient_code": j2["code"]}
    rv = c1.post("/api/public-chat/voice-notes", files=files, data=data)
    assert rv.status_code == 200
    vmsg = rv.json()["message"]
    file_id = vmsg["audio"]["file_id"]

    ok2 = c2.get(f"/api/public-chat/media/{file_id}")
    assert ok2.status_code == 200
    bad3 = c3.get(f"/api/public-chat/media/{file_id}")
    assert bad3.status_code == 404


def test_public_chat_retention_cleanup_removes_public_and_orphaned_media(app_ctx, monkeypatch):
    app, authentication, store = app_ctx
    c1 = TestClient(app)
    j1 = c1.post("/api/public-chat/join", json={"display_name": "One"}).json()["participant"]
    # create public message
    msg = c1.post("/api/public-chat/messages", json={"text": "old public"}).json()["message"]
    # create voice public message
    audio = io.BytesIO(b"fakewebmdata2")
    rv = c1.post("/api/public-chat/voice-notes", files={"file": ("note.webm", audio, "audio/webm")})
    assert rv.status_code == 200
    vmsg = rv.json()["message"]
    file_id = vmsg["audio"]["file_id"]
    media_path = store.get_media_path(file_id)
    assert media_path and media_path.exists()

    # age messages beyond retention
    old_s = int(__import__("time").time()) - (8 * 24 * 60 * 60)
    from app.database.connection import database
    with database() as db:
        for mid in [msg["id"], vmsg["id"]]:
            row = db.execute("SELECT data FROM docs WHERE col=? AND id=?", (store.COL_MESSAGES, mid)).fetchone()
            data = json.loads(row["data"])
            data["created_at_s"] = old_s
            db.execute("UPDATE docs SET data=? WHERE col=? AND id=?", (json.dumps(data), store.COL_MESSAGES, mid))

    result = store.cleanup_public_retention()
    assert result["deleted_messages"] >= 2
    assert not media_path.exists()

    msgs = c1.get("/api/public-chat/messages").json()["messages"]
    assert not any(m["id"] in {msg["id"], vmsg["id"]} for m in msgs)
