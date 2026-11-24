"""Public chat API, identity, privacy, and retention tests."""
from __future__ import annotations

import importlib
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
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
    # Reload only the modules owned by this feature. Replacing every app module
    # breaks unrelated tests that imported their helpers during collection.
    for mod in ["app.main", "app.public_chat"] + [
        name for name in list(sys.modules)
        if name.startswith("app.public_chat.")
    ]:
        sys.modules.pop(mod, None)
    import app.config as config
    import app.database.connection as connection
    import app.services.authentication as authentication
    importlib.reload(config)
    importlib.reload(connection)
    importlib.reload(authentication)
    # Import the store before main so routes bind the store used by this test.
    import app.public_chat.store as store
    import app.main as main
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


def test_public_chat_codes_are_unique_under_concurrent_joins(app_ctx):
    app, authentication, store = app_ctx
    users = [{"id": f"race-user-{i}", "name": f"Racer {i}"} for i in range(24)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        participants = list(pool.map(lambda user: store.ensure_participant(user), users))
    codes = [participant["code"] for participant in participants]
    assert len(set(codes)) == len(users)
    assert all(store.CODE_RE.fullmatch(code) for code in codes)


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

    admin = _auth_client(app, authentication)
    result = admin.post("/api/public-chat/cleanup/run")
    assert result.status_code == 200
    assert result.json()["deleted_messages"] >= 2
    assert not media_path.exists()

    msgs = c1.get("/api/public-chat/messages").json()["messages"]
    assert not any(m["id"] in {msg["id"], vmsg["id"]} for m in msgs)
    status = admin.get("/api/public-chat/cleanup/status")
    assert status.status_code == 200
    assert status.json()["retention_days"] == 7
    assert status.json()["recent_runs"]


def test_guest_identity_is_signed_and_legacy_cookies_are_ignored(app_ctx):
    app, authentication, store = app_ctx
    client = TestClient(app)
    client.cookies.set("cara_guest", "guest_not_signed_by_this_app")
    status = client.get("/api/public-chat/status")
    assert status.status_code == 200
    assert status.json()["joined"] is False
    signed = client.cookies.get("mnh_pc_guest")
    assert signed and "." in signed

    client.cookies.clear()
    client.cookies.set("mnh_pc_guest", signed[:-1] + ("0" if signed[-1] != "0" else "1"))
    assert client.get("/api/public-chat/messages").status_code == 401


def test_reactions_edit_delete_and_search(app_ctx):
    app, authentication, store = app_ctx
    c1 = TestClient(app)
    c2 = TestClient(app)
    c1.post("/api/public-chat/join", json={"display_name": "Alpha"})
    c2.post("/api/public-chat/join", json={"display_name": "Beta"})
    created = c1.post("/api/public-chat/messages", json={"text": "statistics glossary"}).json()["message"]
    mid = created["id"]

    reaction = c2.post(f"/api/public-chat/messages/{mid}/reactions", json={"emoji": "👍"})
    assert reaction.status_code == 200
    assert reaction.json()["reactions"]["👍"]["count"] == 1
    assert reaction.json()["reactions"]["👍"]["mine"] is True
    mine = c1.get("/api/public-chat/messages").json()["messages"]
    target = next(m for m in mine if m["id"] == mid)
    assert target["reactions"]["👍"]["mine"] is False
    assert c2.post(f"/api/public-chat/messages/{mid}/reactions", json={"emoji": "👍"}).json()["reactions"] == {}

    edited = c1.put(f"/api/public-chat/messages/{mid}", json={"text": "updated glossary"})
    assert edited.status_code == 200
    assert edited.json()["message"]["edited"] is True
    assert c2.put(f"/api/public-chat/messages/{mid}", json={"text": "not allowed"}).status_code == 403
    found = c2.get("/api/public-chat/search", params={"q": "updated"}).json()["messages"]
    assert any(m["id"] == mid for m in found)
    assert c2.delete(f"/api/public-chat/messages/{mid}").status_code == 403
    assert c1.delete(f"/api/public-chat/messages/{mid}").status_code == 200
    assert not c2.get("/api/public-chat/search", params={"q": "updated"}).json()["messages"]


def test_unread_and_read_receipts(app_ctx):
    app, authentication, store = app_ctx
    c1 = TestClient(app)
    c2 = TestClient(app)
    c1.post("/api/public-chat/join", json={"display_name": "Alpha"})
    c2.post("/api/public-chat/join", json={"display_name": "Beta"})
    mid = c1.post("/api/public-chat/messages", json={"text": "ping"}).json()["message"]["id"]

    assert c2.get("/api/public-chat/unread").json()["unread"] == 1
    marked = c2.post("/api/public-chat/read", json={"at": 0})
    assert marked.status_code == 200
    assert c2.get("/api/public-chat/unread").json()["unread"] == 0
    sender_view = c1.get("/api/public-chat/messages").json()["messages"]
    assert next(m for m in sender_view if m["id"] == mid)["read_count"] == 1


def test_optional_access_approval_gate(app_ctx):
    app, authentication, store = app_ctx
    from app.public_chat import settings
    settings.REQUIRE_ACCESS_APPROVAL = True
    try:
        client = TestClient(app)
        admin = _auth_client(app, authentication)
        joined = client.post("/api/public-chat/join", json={"display_name": "Pending"})
        assert joined.json()["joined"] is False
        assert joined.json()["access_request"]["status"] == "pending"
        assert client.get("/api/public-chat/messages").status_code == 403

        pending = admin.get("/api/public-chat/admin/access-requests").json()["requests"]
        assert len(pending) == 1
        uid = pending[0]["user_id"]
        decision = admin.post(f"/api/public-chat/admin/access-requests/{uid}/decision",
                              json={"approved": True, "note": "Verified"})
        assert decision.status_code == 200
        assert client.get("/api/public-chat/status").json()["joined"] is True
        assert client.post("/api/public-chat/messages", json={"text": "approved"}).status_code == 200
    finally:
        settings.REQUIRE_ACCESS_APPROVAL = False


def test_reports_and_moderation_protect_reporter_and_suspend_offender(app_ctx):
    app, authentication, store = app_ctx
    c1 = TestClient(app)
    c2 = TestClient(app)
    admin = _auth_client(app, authentication)
    j2 = c2.post("/api/public-chat/join", json={"display_name": "Reporter target"}).json()["participant"]
    c1.post("/api/public-chat/join", json={"display_name": "Reporter"})

    first = c2.post("/api/public-chat/messages", json={"text": "spam one"}).json()["message"]
    report = c1.post("/api/public-chat/reports", json={
        "message_id": first["id"], "category": "spam", "reason": "Advert",
    })
    assert report.status_code == 200
    reports = admin.get("/api/public-chat/admin/reports").json()["reports"]
    assert reports and reports[0]["message_id"] == first["id"]
    resolved = admin.post(f"/api/public-chat/admin/reports/{reports[0]['id']}/resolve",
                          json={"action": "delete_message", "note": "Removed"})
    assert resolved.status_code == 200
    assert c1.get("/api/public-chat/messages").json()["messages"][0]["deleted"] is True

    second = c2.post("/api/public-chat/messages", json={"text": "spam two"}).json()["message"]
    report2 = c1.post("/api/public-chat/reports", json={
        "message_id": second["id"], "category": "harassment", "reason": "Repeated",
    }).json()
    open_reports = admin.get("/api/public-chat/admin/reports", params={"status": "open"}).json()["reports"]
    match = next(r for r in open_reports if r["id"] == report2["report_id"])
    assert admin.post(f"/api/public-chat/admin/reports/{match['id']}/resolve",
                      json={"action": "suspend"}).status_code == 200

    assert c2.get("/api/public-chat/status").json()["joined"] is False
    assert c2.get("/api/public-chat/messages").status_code == 403
    assert c1.get("/api/public-chat/status").json()["joined"] is True


def test_private_attachment_is_visible_only_to_recipient(app_ctx):
    app, authentication, store = app_ctx
    c1 = TestClient(app)
    c2 = TestClient(app)
    c3 = TestClient(app)
    j2 = c2.post("/api/public-chat/join", json={"display_name": "Two"}).json()["participant"]
    c1.post("/api/public-chat/join", json={"display_name": "One"})
    c3.post("/api/public-chat/join", json={"display_name": "Three"})

    response = c1.post("/api/public-chat/attachments",
                       files={"file": ("notes.png", io.BytesIO(b"fake-image"), "image/png")},
                       data={"text": "private file", "private_recipient_code": j2["code"]})
    assert response.status_code == 200
    message = response.json()["message"]
    fid = message["attachments"][0]["file_id"]
    assert c2.get(f"/api/public-chat/media/{fid}").status_code == 200
    assert c3.get(f"/api/public-chat/media/{fid}").status_code == 404


def test_websocket_requires_signed_identity(app_ctx):
    app, authentication, store = app_ctx
    anonymous = TestClient(app)
    with anonymous.websocket_connect("/api/public-chat/ws") as socket:
        assert socket.receive_json()["type"] == "error"

    client = TestClient(app)
    participant = client.post("/api/public-chat/join", json={"display_name": "Socket user"}).json()["participant"]
    with client.websocket_connect("/api/public-chat/ws") as socket:
        hello = socket.receive_json()
        assert hello["type"] == "hello"
        assert hello["joined"] is True
        assert hello["participant"]["code"] == participant["code"]


def test_calendar_export_and_restore_preserve_chat_data(app_ctx, monkeypatch):
    app, authentication, store = app_ctx
    from app.api import routes as api_routes
    monkeypatch.setattr(api_routes, "make_backup", lambda: None)

    c1 = TestClient(app)
    c1.post("/api/public-chat/join", json={"display_name": "Keeper"})
    message = c1.post("/api/public-chat/messages", json={"text": "do not erase me"}).json()["message"]
    admin = _auth_client(app, authentication)

    exported = admin.get("/api/export")
    assert exported.status_code == 200
    assert all(not str(doc.get("col", "")).startswith("public_chat_") for doc in exported.json())
    backup = admin.get("/api/backup")
    assert backup.status_code == 200
    assert all(not str(doc.get("col", "")).startswith("public_chat_")
               for doc in backup.json()["documents"])

    restore = admin.post("/api/restore", json={
        "format": "mnh-calendar-backup",
        "documents": [{"col": "cells", "id": "0_0", "data": {"title": "Calendar"}}],
    })
    assert restore.status_code == 200
    remaining = c1.get("/api/public-chat/messages").json()["messages"]
    assert any(m["id"] == message["id"] for m in remaining)


def test_public_reply_cannot_quote_a_private_thread(app_ctx):
    app, authentication, store = app_ctx
    c1 = TestClient(app)
    c2 = TestClient(app)
    c3 = TestClient(app)
    j2 = c2.post("/api/public-chat/join", json={"display_name": "Two"}).json()["participant"]
    c1.post("/api/public-chat/join", json={"display_name": "One"})
    c3.post("/api/public-chat/join", json={"display_name": "Three"})
    private = c1.post("/api/public-chat/messages", json={
        "text": "TOPSECRET-123", "private_recipient_code": j2["code"],
    }).json()["message"]

    # A caller that omits the private recipient still cannot publish the quote.
    reply = c1.post("/api/public-chat/messages", json={
        "text": "publicly visible reply", "reply_to_id": private["id"],
    })
    assert reply.status_code == 200
    created = reply.json()["message"]
    assert created["kind"] == "private"
    assert created["private_recipient_code"] == j2["code"]

    # Read the stored document through the same serializer used by REST and WS.
    raw = store._message_doc(private["id"])
    outsider_view = store._serialize_message(raw, {"user_id": "third-party"})
    assert "TOPSECRET-123" not in str(outsider_view["reply_to"] or {})
    visible_to_third = c3.get("/api/public-chat/messages").json()["messages"]
    assert not any(m["id"] == created["id"] for m in visible_to_third)


def test_private_notifications_only_target_the_recipient(app_ctx):
    app, authentication, store = app_ctx
    from app.public_chat import notifications

    j1 = {"id": "u1", "code": "MNH-1111"}
    j2 = {"id": "u2", "code": "MNH-2222"}
    j3 = {"id": "u3", "code": "MNH-3333"}
    for item in (j1, j2, j3):
        store.ensure_participant(item, item["code"])
    message = {
        "id": "private-1",
        "kind": "private",
        "text": "PRIVATE-LEAK-777",
        "sender_user_id": j1["id"],
        "sender_code": j1["code"],
        "private_recipient_user_id": j2["id"],
        "mentions": [j3["code"]],
        "reply_to": {"id": "some-id", "sender_code": j3["code"]},
    }
    assert notifications.targets_for_message(message) == {j2["id"]}
    sent = []
    notifications.dispatch_for_message(message, lambda event, targets: sent.append((event, targets)))
    assert sent
    assert all(targets == {j2["id"]} for _event, targets in sent)
    assert all("PRIVATE-LEAK-777" not in str(_event) or targets == {j2["id"]}
               for _event, targets in sent)


def test_suspension_survives_rejoin_and_mutes_socket(app_ctx):
    app, authentication, store = app_ctx
    from app.public_chat.websocket import manager

    c1 = TestClient(app)
    c2 = TestClient(app)
    admin = _auth_client(app, authentication)
    j2 = c2.post("/api/public-chat/join", json={"display_name": "Target"}).json()["participant"]
    suspended_uid = c2.cookies.get("mnh_pc_guest")
    c1.post("/api/public-chat/join", json={"display_name": "Reporter"})
    spam = c2.post("/api/public-chat/messages", json={"text": "spam"}).json()["message"]
    report = c1.post("/api/public-chat/reports", json={"message_id": spam["id"], "category": "spam"}).json()
    assert admin.post(f"/api/public-chat/admin/reports/{report['report_id']}/resolve",
                      json={"action": "suspend"}).status_code == 200

    rejoin = c2.post("/api/public-chat/join", json={"display_name": "Target again"})
    assert rejoin.status_code == 200
    assert rejoin.json()["joined"] is False
    assert rejoin.json()["participant"]["status"] == "suspended"
    assert c2.post("/api/public-chat/messages", json={"text": "still here"}).status_code == 403
    assert c2.delete("/api/public-chat/access-request").status_code == 403
    assert c2.post("/api/public-chat/join", json={"display_name": "Still suspended"}).json()["joined"] is False

    # A moderator can still find the suspended record and restore it.
    restored = admin.post(f"/api/public-chat/admin/participants/{j2['code']}/status",
                          json={"status": "active"})
    assert restored.status_code == 200
    assert c2.post("/api/public-chat/join", json={"display_name": "Restored"}).json()["joined"] is True

    message = c1.post("/api/public-chat/messages", json={"text": "public after suspension"}).json()["message"]
    event = {"type": "message.created", "message": {"id": message["id"]}}
    assert manager._serialize_for(event, {"user_id": suspended_uid, "code": ""},
                                  {"user_id": suspended_uid}) is None


def test_reaction_events_are_serialized_for_each_viewer(app_ctx):
    app, authentication, store = app_ctx
    from app.public_chat.websocket import manager

    c1 = TestClient(app)
    c2 = TestClient(app)
    j1 = c1.post("/api/public-chat/join", json={"display_name": "One"}).json()["participant"]
    j2 = c2.post("/api/public-chat/join", json={"display_name": "Two"}).json()["participant"]
    viewer1 = store.participant_by_code(j1["code"])
    viewer2 = store.participant_by_code(j2["code"])
    uid1 = str(viewer1["user_id"])
    uid2 = str(viewer2["user_id"])
    mid = c1.post("/api/public-chat/messages", json={"text": "react to me"}).json()["message"]["id"]
    assert c2.post(f"/api/public-chat/messages/{mid}/reactions", json={"emoji": "👍"}).status_code == 200

    event = {"type": "message.reaction", "message_id": mid, "added": True,
             "reactions": {"👍": {"count": 1, "mine": True}}}
    reactor_view = manager._serialize_for(event, viewer2, {"user_id": uid2})
    assert reactor_view["reactions"]["👍"]["mine"] is True
    other_view = manager._serialize_for(event, viewer1, {"user_id": uid1})
    # The broadcaster's flag must not be borrowed by other viewers.
    assert other_view["reactions"]["👍"]["mine"] is False


def test_chat_routes_allow_microphone_policy(app_ctx):
    app, authentication, store = app_ctx
    response = TestClient(app).get("/api/public-chat/status")
    assert response.status_code == 200
    policy = response.headers.get("permissions-policy", "")
    assert "microphone=(self)" in policy
    assert "unload=self" in policy
    assert "unload=*" not in policy


def test_chat_promoted_moderator_can_moderate(app_ctx):
    app, authentication, store = app_ctx
    admin = _auth_client(app, authentication)
    member = TestClient(app)
    participant = member.post("/api/public-chat/join", json={"display_name": "Helper"}).json()["participant"]
    assert member.get("/api/public-chat/admin/reports").status_code == 403

    promoted = admin.post(f"/api/public-chat/admin/participants/{participant['code']}/role",
                          json={"role": "moderator"})
    assert promoted.status_code == 200
    assert member.get("/api/public-chat/admin/reports").status_code == 200
