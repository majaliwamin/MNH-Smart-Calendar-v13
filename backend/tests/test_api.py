import json

from fastapi.testclient import TestClient

from app import config
from app.database import connection
from app.main import app
from app.services import authentication, backup_service


def configure_test_storage(monkeypatch, tmp_path):
    database_dir = tmp_path / "database"
    backup_dir = tmp_path / "backups"
    database_path = database_dir / "calendar.db"

    monkeypatch.setattr(config, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(config, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(connection, "DATABASE_PATH", database_path)
    monkeypatch.setattr(backup_service, "DATABASE_PATH", database_path)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", backup_dir)
    monkeypatch.setenv("MNH_ENV", "development")
    monkeypatch.delenv("MNH_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("MNH_LECTURER_PASSWORD", raising=False)
    authentication.SESSIONS.clear()


def test_web_assets_and_service_worker_are_served(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/docs").status_code == 200
        health = client.get("/health").json()
        assert health["ok"] is True
        assert client.get("/api/build").json()["build"] == health["build"]
        assert client.get("/css/app.css").status_code == 200
        assert client.get("/js/app.js").status_code == 200
        service_worker = client.get("/service-worker.js")
        assert service_worker.status_code == 200
        assert f'const BUILD = "{health["build"]}"' in service_worker.text
        assert health["build"] in client.get("/").text            # page, service worker and server agree
        assert "addEventListener(\"fetch\"" in service_worker.text
        assert "no-cache" in service_worker.headers.get("cache-control", "")


def test_api_requires_authentication_for_shared_writes(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)

    with TestClient(app) as client:
        denied = client.put("/api/doc/cells/0_0", json={"title": "Should be blocked"})
        assert denied.status_code == 401

        login = client.post("/api/auth", json={"password": "rep"})
        assert login.status_code == 200
        assert login.json()["role"] == "administrator"

        saved = client.put("/api/doc/cells/0_0", json={"title": "API test"})
        assert saved.status_code == 200
        rows = client.get("/api/col/cells").json()
        assert any(row["id"] == "0_0" and row["data"]["title"] == "API test" for row in rows)

        assert client.post("/api/logout").status_code == 200
        assert client.put("/api/doc/cells/0_1", json={"title": "Blocked after logout"}).status_code == 401


def test_analytics_requires_a_management_role(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)

    with TestClient(app) as client:
        assert client.post("/api/auth", json={"password": "rep"}).status_code == 200
        assert client.get("/api/analytics").status_code == 403
        client.post("/api/logout")

        monkeypatch.setenv("MNH_HOD_PASSWORD", "hod-audit-secret")
        assert client.post("/api/auth", json={"password": "hod-audit-secret"}).status_code == 200
        response = client.get("/api/analytics")
        assert response.status_code == 200
        assert "delivery_modes" in response.json()


def test_restore_rejects_duplicate_records_without_deleting_existing_data(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)

    with TestClient(app) as client:
        client.post("/api/auth", json={"password": "rep"})
        client.put("/api/doc/cells/0_0", json={"title": "Keep this record"})
        before = client.get("/api/col/cells").json()

        backup = {
            "format": "mnh-calendar-backup",
            "documents": [
                {"col": "cells", "id": "0_0", "data": {"title": "First duplicate"}},
                {"col": "cells", "id": "0_0", "data": {"title": "Second duplicate"}},
            ],
        }
        response = client.post("/api/restore", json=backup)

        assert response.status_code == 400
        rows = client.get("/api/col/cells").json()
        assert rows == before


def test_custom_session_times_are_validated_and_saved(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/auth", json={"password": "rep"})
        invalid = client.put("/api/doc/cells/session-invalid", json={
            "dayIndex": 1, "startTime": "14:00", "endTime": "13:00", "title": "Invalid"
        })
        assert invalid.status_code == 400
        valid = client.put("/api/doc/cells/session-valid", json={
            "dayIndex": 1, "startTime": "14:15", "endTime": "15:45", "title": "Seminar"
        })
        assert valid.status_code == 200


def test_saturday_cells_are_rejected(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/auth", json={"password": "rep"})
        response = client.put("/api/doc/cells/session-saturday", json={
            "dayIndex": 5, "startTime": "09:00", "endTime": "10:00", "title": "Saturday"
        })
        assert response.status_code == 400


def test_custom_session_overlap_is_rejected(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/auth", json={"password": "rep"})
        first = client.put("/api/doc/cells/session-first", json={
            "dayIndex": 0, "startTime": "09:15", "endTime": "10:45", "title": "First"
        })
        assert first.status_code == 200
        overlap = client.put("/api/doc/cells/session-overlap", json={
            "dayIndex": 0, "startTime": "10:00", "endTime": "11:00", "title": "Overlap"
        })
        assert overlap.status_code == 409


def test_database_migration_keeps_and_flags_non_weekday_timetable_records(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        with connection.database() as c:
            c.execute(
                "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
                ("cells", "session-old-saturday", json.dumps({"dayIndex": 5, "title": "Old Saturday"}), 1),
            )
            c.execute(
                "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
                ("cells", "session-friday", json.dumps({"dayIndex": 4, "startTime": "09:00", "endTime": "10:00", "title": "Friday"}), 1),
            )
        client.get("/api/health")  # any request reopens the database and re-runs the migration
        rows = client.get("/api/col/cells").json()
        ids = {row["id"] for row in rows}
        # Historical data is preserved (never silently deleted) ...
        assert "session-old-saturday" in ids
        assert "session-friday" in ids
        # ... but flagged for review and excluded from every Monday–Friday view and export.
        with connection.database() as c:
            flagged = json.loads(c.execute("SELECT value FROM app_meta WHERE key='flagged_non_weekday_records'").fetchone()[0])
        assert "session-old-saturday" in {item["id"] for item in flagged}
        from app.services.schedule import cell_interval
        assert cell_interval("session-old-saturday", {"dayIndex": 5, "startTime": "09:00", "endTime": "10:00"}) is None


def test_restore_rejects_overlapping_custom_sessions_without_erasing_data(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/auth", json={"password": "rep"})
        client.put("/api/doc/cells/session-kept", json={
            "dayIndex": 0, "startTime": "08:00", "endTime": "09:00", "title": "Keep"
        })
        backup = {
            "format": "mnh-calendar-backup",
            "documents": [
                {"col": "cells", "id": "session-a", "data": {"dayIndex": 0, "startTime": "09:00", "endTime": "10:30", "title": "A"}},
                {"col": "cells", "id": "session-b", "data": {"dayIndex": 0, "startTime": "10:00", "endTime": "11:00", "title": "B"}},
            ],
        }
        response = client.post("/api/restore", json=backup)
        assert response.status_code == 400
        rows = client.get("/api/col/cells").json()
        assert any(row["id"] == "session-kept" for row in rows)


def test_recurring_saturday_records_are_rejected_and_old_ones_flagged_not_deleted(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/auth", json={"password": "rep"})
        rejected = client.put("/api/doc/recurring/rec-sat", json={
            "title": "Saturday seminar", "day": "Saturday", "frequency": "Weekly"
        })
        assert rejected.status_code == 400
        with connection.database() as c:
            c.execute(
                "INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
                ("recurring", "rec-old-sat", json.dumps({"title": "Old Saturday activity", "day": "Saturday"}), 1),
            )
        client.get("/api/health")
        rows = client.get("/api/col/recurring").json()
        assert "rec-old-sat" in {row["id"] for row in rows}
        with connection.database() as c:
            flagged = json.loads(c.execute("SELECT value FROM app_meta WHERE key='flagged_non_weekday_records'").fetchone()[0])
        assert "rec-old-sat" in {item["id"] for item in flagged}


def test_restore_rejects_saturday_recurring_activity_without_erasing_data(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post("/api/auth", json={"password": "rep"})
        client.put("/api/doc/recurring/keep", json={"title": "Weekday seminar", "day": "Friday"})
        backup = {
            "format": "mnh-calendar-backup",
            "documents": [{"col": "recurring", "id": "sat", "data": {"title": "Saturday seminar", "day": "Saturday"}}],
        }
        response = client.post("/api/restore", json=backup)
        assert response.status_code == 400
        rows = client.get("/api/col/recurring").json()
        assert any(row["id"] == "keep" for row in rows)


def test_analytics_reports_module_targets_attendance_and_delivery(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        monkeypatch.setenv("MNH_HOD_PASSWORD", "hod-analytics-secret")
        assert client.post("/api/auth", json={"password": "hod-analytics-secret"}).status_code == 200
        assert client.put("/api/doc/modules/TEST-8100", json={
            "title": "Test Maternal Health Module",
            "semesterTargetSessions": 20,
            "semesterTargetHours": 40,
        }).status_code == 200
        assert client.put("/api/doc/cells/test-session-1", json={
            "dayIndex": 0, "startTime": "08:00", "endTime": "10:00",
            "moduleCode": "TEST-8100", "code": "TEST-8100",
            "status": "completed", "mode": "online",
        }).status_code == 200
        assert client.put("/api/doc/cells/test-session-2", json={
            "dayIndex": 1, "startTime": "10:00", "endTime": "11:30",
            "moduleCode": "TEST-8100", "code": "TEST-8100",
            "status": "missed", "mode": "face_to_face",
        }).status_code == 200
        result = client.get("/api/analytics").json()
        module = next(item for item in result["modules"] if item["code"] == "TEST-8100")
        assert module["weeklySessions"] == 2
        assert module["weeklyHours"] == 3.5
        assert module["semesterSessions"] == 2
        assert module["semesterHours"] == 3.5
        assert module["semesterTracked"] is False
        assert module["targetSessions"] == 20
        assert module["targetHours"] == 40
        assert module["missedSessions"] == 1
        assert module["onlineSessions"] == 1
        assert module["faceToFaceSessions"] == 1


def test_excel_timetable_export_is_editable_and_navigable(monkeypatch, tmp_path):
    from io import BytesIO
    from openpyxl import load_workbook

    configure_test_storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/auth", json={"password": "rep"}).status_code == 200
        assert client.put("/api/doc/modules/MIPN%208100", json={
            "title": "Medical Imaging in Pregnancy and Neonates", "facilitator": "Dr Example"
        }).status_code == 200
        assert client.put("/api/doc/cells/session-1", json={
            "dayIndex": 0, "startTime": "08:30", "endTime": "10:15",
            "code": "MIPN 8100", "title": "Ultrasound principles", "mode": "online"
        }).status_code == 200
        response = client.get("/api/export/timetable.xlsx")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        workbook = load_workbook(BytesIO(response.content))
        assert workbook.sheetnames == ["Weekly Timetable", "Session Details", "Read Me"]
        weekly = workbook["Weekly Timetable"]
        details = workbook["Session Details"]
        assert all("Saturday" not in str(weekly.cell(3, col).value) for col in range(1, 7))
        assert details[3][5].value == "MIPN 8100"
        assert details[3][6].value == "Medical Imaging in Pregnancy and Neonates"
        assert details[3][7].value == "Dr Example"
        assert weekly["A2"].hyperlink is not None                 # weekly sheet -> Session Details
        assert details.cell(3, 1).hyperlink is not None           # Session Details -> its weekly cell
        assert any("Lunch" in str(weekly.cell(row, 1).value).replace(" ", "") for row in range(4, weekly.max_row + 1))
        assert "A1:F1" in {str(m) for m in weekly.merged_cells.ranges}   # header row merged across the table
        assert details.auto_filter.ref
        details.cell(3, 8).value = "Edited lecturer"
        assert details.cell(3, 8).value == "Edited lecturer"
