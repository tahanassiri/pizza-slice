from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_run_cookie_grants_access_to_its_browser(client):
    response = client.post("/api/runs", json={"product": "test paper"})
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert "HttpOnly" in response.headers["set-cookie"]
    with TestClient(app) as other:
        assert other.get(f"/api/runs/{run_id}").status_code == 404
    assert client.get(f"/api/runs/{run_id}").status_code == 200


def test_run_admission_limit_returns_429_before_scheduling(client, monkeypatch):
    monkeypatch.setenv("RUN_REQUESTS_PER_HOUR", "1")
    get_settings.cache_clear()
    try:
        assert client.post("/api/runs", json={"product": "sample tea"}).status_code == 200
        limited = client.post("/api/runs", json={"product": "sample paper"})
        assert limited.status_code == 429
        assert int(limited.headers["Retry-After"]) > 0
    finally:
        get_settings.cache_clear()
