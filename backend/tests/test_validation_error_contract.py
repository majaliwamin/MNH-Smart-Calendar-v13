"""Validation errors must be readable to web, PWA and native clients."""
from fastapi.testclient import TestClient

from app import config
from app.main import app


def test_validation_errors_are_one_readable_sentence():
    with TestClient(app) as client:
        client.get("/api/class-rep/auth/me")
        response = client.post("/api/class-rep/chat", json={
            "message": "hello",
            "history": [{"role": "bad", "content": "x"}],
        })
    assert response.status_code == 422
    body = response.json()
    assert isinstance(body["detail"], str)
    assert "[object Object]" not in body["detail"]
    assert "history" in body["detail"] and "role" in body["detail"]
    assert body["error"] == body["detail"]
    assert response.headers["x-mnh-build"] == config.BUILD_ID
