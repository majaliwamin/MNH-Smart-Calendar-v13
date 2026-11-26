import os, importlib
from fastapi.testclient import TestClient


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import app.config as config
    import app.database.connection as connection
    import app.main as main
    import app.exams.store as exam_store
    import app.exams.permissions as exam_permissions
    import app.exams.audit as exam_audit
    import app.exams.schemas as exam_schemas
    import app.exams.routes as exam_routes
    import app.api.routes as api_routes
    importlib.reload(config)
    importlib.reload(connection)
    importlib.reload(exam_store)
    importlib.reload(exam_permissions)
    importlib.reload(exam_audit)
    importlib.reload(exam_schemas)
    importlib.reload(api_routes)
    importlib.reload(exam_routes)
    importlib.reload(main)
    return TestClient(main.app)


def auth_headers(monkeypatch, role="administrator"):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    return role


def login_admin(client):
    from app.services import authentication
    token = authentication.create_session("administrator")
    client.cookies.set("mnh_session", token)
    return token


def test_exams_health_and_legacy_isolation(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    r = client.get("/api/exams/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["isolated_from_legacy_examinations"] is True
    assert "exams_exams" in data["collections"]
    # legacy examinations endpoint still works
    r2 = client.get("/api/col/examinations")
    assert r2.status_code == 200


def test_exam_create_requires_manage(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    r = client.post("/api/exams/exams", json={"title":"X","duration_minutes":30})
    assert r.status_code == 403


def test_exam_crud_with_admin_session(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    r = client.post("/api/exams/questions", json={"prompt":"2+2?","type":"mcq","options":[{"id":"a","text":"4"},{"id":"b","text":"5"}],"correct_option_ids":["a"],"points":1})
    assert r.status_code == 200
    qid = r.json()["item"]["id"]
    r = client.post("/api/exams/exams", json={"title":"Math","duration_minutes":10,"status":"published","questions":[{"question_id":qid,"order":0}]})
    assert r.status_code == 200
    exam = r.json()["item"]
    r = client.get(f"/api/exams/exams/{exam['id']}")
    assert r.status_code == 200
    assert r.json()["item"]["title"] == "Math"


def test_session_start_autosave_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    q = client.post("/api/exams/questions", json={"prompt":"2+2?","type":"mcq","options":[{"id":"a","text":"4"},{"id":"b","text":"5"}],"correct_option_ids":["a"],"points":2}).json()["item"]
    exam = client.post("/api/exams/exams", json={"title":"Math","duration_minutes":10,"status":"published","questions":[{"question_id":q['id'],"order":0}]}).json()["item"]
    s = client.post("/api/exams/sessions/start", json={"exam_id": exam["id"]})
    assert s.status_code == 200
    sess = s.json()["item"]
    sid = sess["id"]
    a = client.post(f"/api/exams/sessions/{sid}/autosave", json={"answers":{q['id']:"a"}, "client_save_id":"save1", "seq":1})
    assert a.status_code == 200
    sub = client.post(f"/api/exams/sessions/{sid}/submit", json={"answers":{q['id']:"a"}, "client_submit_id":"sub1"})
    assert sub.status_code == 200
    body = sub.json()
    assert body["submission"]["score"]["percent"] == 100.0
    # idempotent submit
    sub2 = client.post(f"/api/exams/sessions/{sid}/submit", json={"answers":{q['id']:"a"}, "client_submit_id":"sub1"})
    assert sub2.status_code == 200
    assert sub2.json().get("already_submitted") or sub2.json().get("duplicate")


def test_enrollment_required_blocks_unenrolled(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    q = client.post("/api/exams/questions", json={"prompt":"2+2?","type":"mcq","options":[{"id":"a","text":"4"}],"correct_option_ids":["a"],"points":1}).json()["item"]
    exam = client.post("/api/exams/exams", json={"title":"Restricted","duration_minutes":10,"status":"published","require_enrollment":True,"questions":[{"question_id":q["id"],"order":0}]}).json()["item"]
    # executive_dean maps to exam_reviewer (no exams.manage), so enrollment is enforced.
    from app.services import authentication
    tok = authentication.create_session("executive_dean")
    c2 = make_client(tmp_path, monkeypatch)
    c2.cookies.set("mnh_session", tok)
    r = c2.post("/api/exams/sessions/start", json={"exam_id": exam["id"]})
    assert r.status_code == 403
    cap2 = c2.get("/api/exams/capabilities").json()["identity"]
    r2 = client.post("/api/exams/enrollments", json={"exam_id": exam["id"], "actor_id": cap2["actor_id"], "role":"candidate"})
    assert r2.status_code == 200
    r3 = c2.post("/api/exams/sessions/start", json={"exam_id": exam["id"]})
    assert r3.status_code == 200


def test_max_attempts_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    q = client.post("/api/exams/questions", json={"prompt":"2+2?","type":"mcq","options":[{"id":"a","text":"4"}],"correct_option_ids":["a"],"points":1}).json()["item"]
    exam = client.post("/api/exams/exams", json={"title":"One shot","duration_minutes":10,"status":"published","max_attempts":1,"questions":[{"question_id":q["id"],"order":0}]}).json()["item"]
    from app.services import authentication
    tok = authentication.create_session("lecturer")
    c2 = make_client(tmp_path, monkeypatch)
    c2.cookies.set("mnh_session", tok)
    s = c2.post("/api/exams/sessions/start", json={"exam_id": exam["id"]})
    assert s.status_code == 200
    sid = s.json()["item"]["id"]
    sub = c2.post(f"/api/exams/sessions/{sid}/submit", json={"answers":{q["id"]:"a"}, "client_submit_id":"sub1"})
    assert sub.status_code == 200
    # after submit, resume returns submitted session (same behavior)
    s2 = c2.post("/api/exams/sessions/start", json={"exam_id": exam["id"]})
    assert s2.status_code == 200
    assert s2.json().get("resumed") is True


def test_session_owner_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    q = client.post("/api/exams/questions", json={"prompt":"2+2?","type":"mcq","options":[{"id":"a","text":"4"}],"correct_option_ids":["a"],"points":1}).json()["item"]
    exam = client.post("/api/exams/exams", json={"title":"Math","duration_minutes":10,"status":"published","questions":[{"question_id":q["id"],"order":0}]}).json()["item"]
    s = client.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    from app.services import authentication
    tok = authentication.create_session("lecturer")
    c2 = make_client(tmp_path, monkeypatch)
    c2.cookies.set("mnh_session", tok)
    r = c2.get(f"/api/exams/sessions/{s['id']}")
    assert r.status_code == 403
    r2 = c2.post(f"/api/exams/sessions/{s['id']}/autosave", json={"answers":{}, "client_save_id":"x", "seq":1})
    assert r2.status_code == 403


def test_generic_export_excludes_exams(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    client.post("/api/exams/exams", json={"title":"Secret","duration_minutes":10,"status":"draft"})
    r = client.get("/api/export")
    assert r.status_code == 200
    body = r.json()
    docs = body.get("documents", body) if isinstance(body, dict) else body
    cols = {d.get("col") for d in docs if isinstance(d, dict)}
    assert not any(str(c).startswith("exams_") for c in cols)


def test_autosave_conflict_detection(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    q = client.post("/api/exams/questions", json={"prompt":"2+2?","type":"short_text","correct_text":"4","points":1}).json()["item"]
    exam = client.post("/api/exams/exams", json={"title":"Math","duration_minutes":10,"status":"published","questions":[{"question_id":q["id"],"order":0}]}).json()["item"]
    s = client.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    sid = s["id"]
    stale = s.get("updated_at")
    a1 = client.post(f"/api/exams/sessions/{sid}/autosave", json={"answers":{q["id"]:"4"}, "client_save_id":"s1", "seq":1, "expected_updated_at": stale})
    assert a1.status_code == 200
    a2 = client.post(f"/api/exams/sessions/{sid}/autosave", json={"answers":{q["id"]:"5"}, "client_save_id":"s2", "seq":2, "expected_updated_at": stale})
    assert a2.status_code == 200
    body = a2.json()
    assert body.get("conflict") is True or body.get("ok") is False


def test_my_exams_returns_actor_activity(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    q = client.post("/api/exams/questions", json={"prompt":"2+2?","type":"mcq","options":[{"id":"a","text":"4"}],"correct_option_ids":["a"],"points":1}).json()["item"]
    exam = client.post("/api/exams/exams", json={"title":"Math","duration_minutes":10,"status":"published","questions":[{"question_id":q["id"],"order":0}]}).json()["item"]
    s = client.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    sid = s["id"]
    client.post(f"/api/exams/sessions/{sid}/submit", json={"answers":{q["id"]:"a"}, "client_submit_id":"sub1"})
    r = client.get("/api/exams/my")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert len(body.get("sessions", [])) >= 1
    assert len(body.get("submissions", [])) >= 1


def test_generic_restore_ignores_exams_collections(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    # create exams data
    client.post("/api/exams/exams", json={"title":"Secret","duration_minutes":10,"status":"draft"})
    before = client.get("/api/exams/overview").json()["counts"].get("exams_exams", 0)
    assert before >= 1
    backup = {
        "format": "mnh-calendar-backup",
        "documents": [
            {"col": "modules", "id": "M1", "data": {"title": "Module 1"}},
            {"col": "exams_exams", "id": "exam_evil", "data": {"title": "Injected"}},
        ],
    }
    r = client.post("/api/restore", json=backup)
    assert r.status_code == 200
    after = client.get("/api/exams/overview").json()["counts"].get("exams_exams", 0)
    assert after == before


def test_session_expiry_blocks_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    q = client.post("/api/exams/questions", json={"prompt":"2+2?","type":"mcq","options":[{"id":"a","text":"4"}],"correct_option_ids":["a"],"points":1}).json()["item"]
    exam = client.post("/api/exams/exams", json={"title":"Timed","duration_minutes":1,"status":"published","questions":[{"question_id":q["id"],"order":0}]}).json()["item"]
    s = client.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    sid = s["id"]
    import app.exams.store as store
    future = int(s["expires_at"]) + 1000
    monkeypatch.setattr(store, "now_ms", lambda: future)
    r = client.post(f"/api/exams/sessions/{sid}/submit", json={"answers":{q["id"]:"a"}, "client_submit_id":"sub1"})
    assert r.status_code == 409


def test_submit_conflict_returns_stale_session(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    q = client.post("/api/exams/questions", json={"prompt":"2+2?","type":"mcq","options":[{"id":"a","text":"4"}],"correct_option_ids":["a"],"points":1}).json()["item"]
    exam = client.post("/api/exams/exams", json={"title":"Math","duration_minutes":10,"status":"published","questions":[{"question_id":q["id"],"order":0}]}).json()["item"]
    s = client.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    sid = s["id"]
    stale = s.get("updated_at")
    # first submit succeeds and updates session
    r1 = client.post(f"/api/exams/sessions/{sid}/submit", json={"answers":{q["id"]:"a"}, "client_submit_id":"sub1", "expected_updated_at": stale})
    assert r1.status_code == 200
    # second submit with same stale expected_updated_at should report already submitted / conflict-safe
    r2 = client.post(f"/api/exams/sessions/{sid}/submit", json={"answers":{q["id"]:"a"}, "client_submit_id":"sub2", "expected_updated_at": stale})
    assert r2.status_code == 200
    body = r2.json()
    assert body.get("already_submitted") is True or body.get("conflict") is True


def test_analytics_and_grading(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    login_admin(client)
    q = client.post("/api/exams/questions", json={"prompt":"2+2?","type":"mcq","options":[{"id":"a","text":"4"},{"id":"b","text":"5"}],"correct_option_ids":["a"],"points":1}).json()["item"]
    exam = client.post("/api/exams/exams", json={"title":"Math","duration_minutes":10,"status":"published","questions":[{"question_id":q["id"],"order":0}]}).json()["item"]
    s = client.post("/api/exams/sessions/start", json={"exam_id": exam["id"]}).json()["item"]
    sub = client.post(f"/api/exams/sessions/{s['id']}/submit", json={"answers":{q["id"]:"a"}, "client_submit_id":"sub-grade"}).json()["submission"]
    g = client.post(f"/api/exams/submissions/{sub['id']}/grade", json={"percent": 88.5, "feedback": "Good", "status": "graded"})
    assert g.status_code == 200
    assert g.json()["item"]["score"]["percent"] == 88.5
    an = client.get("/api/exams/analytics")
    assert an.status_code == 200
    body = an.json()
    assert body["analytics"]["submissions"] >= 1
    assert any(x["exam_id"] == exam["id"] for x in body["by_exam"])


def test_sessions_monitor_requires_privileged_role(tmp_path, monkeypatch):
    monkeypatch.setenv("MNH_ADMIN_PASSWORD", "admin-pass")
    client = make_client(tmp_path, monkeypatch)
    r = client.get("/api/exams/sessions")
    assert r.status_code in (401, 403)
    login_admin(client)
    r2 = client.get("/api/exams/sessions")
    assert r2.status_code == 200
    assert r2.json()["ok"] is True
