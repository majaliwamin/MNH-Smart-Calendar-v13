import json
from fastapi.testclient import TestClient
from app import config
from app.database import connection
from app.main import app
from app.services import backup_service


def _test_storage(monkeypatch, tmp_path):
    database_dir, backup_dir = tmp_path / "database", tmp_path / "backups"
    monkeypatch.setattr(config, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(config, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(connection, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "BACKUP_DIR", backup_dir)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MNH_ENV", "development")


def test_cara_account_memory_is_persistent_and_isolated(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    from app.class_rep import routes

    monkeypatch.setattr(routes, "reply", lambda message, history, **kwargs:
                        ("A real assistant response.", "cloudflare", "test-model", None))
    with TestClient(app) as client:
        assert client.get("/api/class-rep/memories").status_code == 401
        created = client.post("/api/class-rep/auth/register", json={
            "name": "Student One", "email": "one@example.org", "password": "correct-horse-battery"
        })
        assert created.status_code == 200
        assert created.json()["authenticated"] is True
        # The saved HttpOnly session survives a fresh auth check and its
        # persistent cookie expiry is renewed on return visits.
        session_cookie = client.cookies.get("cara_session")
        assert session_cookie
        checked = client.get("/api/class-rep/auth/me")
        assert checked.status_code == 200
        assert checked.json()["authenticated"] is True
        assert client.cookies.get("cara_session") == session_cookie
        assert "Max-Age=2592000" in checked.headers.get("set-cookie", "")
        chat = client.post("/api/class-rep/chat", json={"message": "We are preparing the seminar announcement."})
        assert chat.status_code == 200
        assert chat.json()["reply"] == "A real assistant response."
        conversation_id = chat.json()["conversation_id"]
        saved = client.post("/api/class-rep/memories", json={"content": "The seminar is on Thursday."})
        assert saved.status_code == 200
        assert client.get("/api/class-rep/memories").json()["memories"][0]["content"] == "The seminar is on Thursday."
        conversations = client.get("/api/class-rep/conversations").json()["conversations"]
        assert any(item["id"] == conversation_id for item in conversations)
        client.post("/api/class-rep/auth/logout")
        signed_in = client.post("/api/class-rep/auth/login", json={"email": "one@example.org", "password": "correct-horse-battery"})
        assert signed_in.status_code == 200
        assert client.get("/api/class-rep/memories").json()["memories"][0]["content"] == "The seminar is on Thursday."

        other = TestClient(app)
        try:
            second = other.post("/api/class-rep/auth/register", json={
                "name": "Student Two", "email": "two@example.org", "password": "another-secure-password"
            })
            assert second.status_code == 200
            assert other.get("/api/class-rep/memories").json()["memories"] == []
            assert other.get("/api/class-rep/tasks").json()["tasks"] == []
        finally:
            other.close()


def test_cara_tasks_and_reminders_are_persisted(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    from app.class_rep import routes

    with TestClient(app) as client:
        client.post("/api/class-rep/auth/register", json={
            "name": "Task Owner", "email": "tasks@example.org", "password": "strong-password-123"
        })
        task = client.post("/api/class-rep/tasks", json={
            "title": "Review the academic timetable", "status": "in_progress",
            "project": "MNH Smart Calendar", "next_action": "Check the Friday sessions"
        })
        assert task.status_code == 200
        assert client.get("/api/class-rep/tasks").json()["tasks"][0]["status"] == "in_progress"
        reminder = client.post("/api/class-rep/reminders", json={
            "message": "Review the timetable", "scheduled_at": 4102444800,
            "timezone": "Africa/Blantyre"
        })
        assert reminder.status_code == 200
        assert client.get("/api/class-rep/reminders").json()["reminders"][0]["status"] == "scheduled"
        cancelled = client.patch("/api/class-rep/reminders/" + reminder.json()["id"], json={"action": "cancel"})
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"


def test_explicit_natural_language_reminder_parser():
    from app.class_rep.routes import _explicit_reminder

    class FakeReminder:
        def __call__(self, user_id, data):
            self.user_id, self.data = user_id, data
            return {"id": "reminder-test", **data}
    from app.class_rep import routes
    original = routes.memory.create_reminder
    fake = FakeReminder()
    routes.memory.create_reminder = fake
    try:
        result = _explicit_reminder("user-test", "Remind me tomorrow at 10:30 to send the announcement")
        assert result is not None
        reminder, when = result
        assert reminder["message"] == "send the announcement"
        assert fake.data["timezone"] == "Africa/Blantyre"
        assert when.hour == 10 and when.minute == 30
    finally:
        routes.memory.create_reminder = original


def test_private_cara_records_are_excluded_from_public_backup_and_export(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/class-rep/auth/register", json={
            "name": "Private Owner", "email": "private@example.org", "password": "private-password-123"
        })
        from app.class_rep import memory
        user = memory.resolve_session(client.cookies.get("cara_session"))
        memory.save_memory(user["id"], {"content": "private personal note"})
        backup = client.get("/api/backup").json()
        exported = client.get("/api/export").json()
        assert all(not item["col"].startswith("cara_") for item in backup["documents"])
        assert all(not item["col"].startswith("cara_") for item in exported)


def test_cara_memory_redacts_credential_like_messages_and_deduplicates_reminders(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    from app.class_rep import memory

    with TestClient(app) as client:
        client.post("/api/class-rep/auth/register", json={
            "name": "Safe Owner", "email": "safe@example.org", "password": "a-long-safe-password"
        })
        user = memory.resolve_session(client.cookies.get("cara_session"))
        memory.save_turn(user["id"], "conversation-safe", "My API key: sk-1234567890abcdefghijkl", "I will not repeat it.")
        saved = memory.list_conversations(user["id"])[0]["messages"][0]["content"]
        assert "sk-1234567890" not in saved
        when = 4102444800
        first = memory.create_reminder(user["id"], {"message": "Send the class announcement", "scheduled_at": when})
        second = memory.create_reminder(user["id"], {"message": "Send the class announcement", "scheduled_at": when})
        assert first["id"] == second["id"]


def test_cara_documents_are_account_scoped(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    from app.class_rep import documents

    monkeypatch.setattr(documents, "_vectors", lambda texts, prefix: [[0.1, 0.2] for _ in texts])
    documents.ingest("private-one.txt", b"Account one confidential timetable notes.", owner_id="account-one")
    documents.ingest("private-two.txt", b"Account two separate research notes.", owner_id="account-two")
    assert [item["title"] for item in documents.list_documents("account-one")] == ["private-one.txt"]
    assert [item["title"] for item in documents.list_documents("account-two")] == ["private-two.txt"]
    assert documents.delete_document("missing-document", owner_id="account-one") is False


def test_cara_projects_are_persisted_and_account_scoped(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/class-rep/auth/register", json={
            "name": "Project Owner", "email": "project@example.org", "password": "project-owner-password"
        })
        project = client.post("/api/class-rep/projects", json={
            "title": "Placental malaria study", "description": "Longitudinal maternal and neonatal project",
            "status": "active", "next_action": "Finalize the protocol"
        })
        assert project.status_code == 200
        assert client.get("/api/class-rep/projects").json()["projects"][0]["title"] == "Placental malaria study"
        task = client.post("/api/class-rep/tasks", json={
            "title": "Review cytokine panel", "project": "Placental malaria study",
            "project_id": project.json()["id"], "status": "in_progress"
        })
        assert task.status_code == 200
        assert task.json()["project_id"] == project.json()["id"]


def test_cara_natural_language_project_task_and_reminder_creation(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/class-rep/auth/register", json={
            "name": "Continuity User", "email": "continuity@example.org", "password": "continuity-password-123"
        })
        project = client.post("/api/class-rep/chat", json={"message": "Create project called MNH seminar planning"})
        assert project.status_code == 200
        task = client.post("/api/class-rep/chat", json={"message": "Create task to draft the seminar announcement"})
        assert task.status_code == 200
        tasks = client.get("/api/class-rep/tasks").json()["tasks"]
        assert tasks[0]["project"] == "MNH seminar planning"
        assert tasks[0]["project_id"]
        reminder = client.post("/api/class-rep/chat", json={"message": "Remind me tomorrow at 10:00 to send the seminar announcement"})
        assert reminder.status_code == 200
        assert "in-app reminder" in reminder.json()["reply"]
        assert client.get("/api/class-rep/reminders").json()["reminders"]


def test_production_cara_accounts_are_blocked_without_durable_storage(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MNH_CARA_SQLITE_PERSISTENT_DISK", raising=False)
    with TestClient(app) as client:
        status = client.get("/api/class-rep/auth/me")
        assert status.status_code == 200
        assert status.json()["storage_ready"] is False
        register = client.post("/api/class-rep/auth/register", json={
            "name": "No Storage", "email": "nostorage@example.org", "password": "safe-password-123"
        })
        assert register.status_code == 503



def test_cara_password_minimum_is_four_characters(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    from app.class_rep import memory

    created = memory.create_account("Four Character Password", "four@example.org", "abcd")
    assert created["email"] == "four@example.org"
    try:
        memory.create_account("Too Short", "short@example.org", "abc")
    except memory.MemoryError as exc:
        assert "4 and 256 characters" in str(exc)
    else:
        raise AssertionError("Three-character passwords must be rejected")



def test_cara_uploaded_file_is_viewable_and_account_scoped(monkeypatch, tmp_path):
    _test_storage(monkeypatch, tmp_path)
    from app.class_rep import routes
    routes._RATE_BUCKETS.clear()

    payload = b"Placental malaria research notes for the MNH cohort."
    with TestClient(app) as client:
        registered = client.post("/api/class-rep/auth/register", json={
            "name": "Document Owner", "email": "document-owner@example.org", "password": "secure-password"
        })
        assert registered.status_code == 200
        uploaded = client.post(
            "/api/class-rep/documents",
            files={"file": ("research-notes.txt", payload, "text/plain")},
            data={"conversation_id": "document-chat"},
        )
        assert uploaded.status_code == 200
        item = uploaded.json()
        assert item["title"] == "research-notes.txt"
        assert item["conversation_id"] == "document-chat"
        assert item["view_url"].endswith("/file")

        opened = client.get(item["view_url"])
        assert opened.status_code == 200
        assert opened.content == payload
        assert "inline" in opened.headers.get("content-disposition", "")

        readable = client.get("/api/class-rep/documents/" + item["id"] + "/text")
        assert readable.status_code == 200
        assert "Placental malaria" in readable.json()["text"]

        documents = client.get("/api/class-rep/documents").json()["documents"]
        assert any(doc["id"] == item["id"] for doc in documents)
        conversations = client.get("/api/class-rep/conversations").json()["conversations"]
        saved = next(row for row in conversations if row["id"] == "document-chat")
        assert "research-notes.txt" in saved["messages"][-1]["content"]

        other = TestClient(app)
        routes._RATE_BUCKETS.clear()
        try:
            other_registered = other.post("/api/class-rep/auth/register", json={
                "name": "Different User", "email": "different-user@example.org", "password": "other-password"
            })
            assert other_registered.status_code == 200
            assert other.get(item["view_url"]).status_code == 404
            assert other.get("/api/class-rep/documents/" + item["id"] + "/text").status_code == 404
        finally:
            other.close()
