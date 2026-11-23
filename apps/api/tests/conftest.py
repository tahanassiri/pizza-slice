from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

_fd, _db_path = tempfile.mkstemp(suffix="_nova_test.db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-admin-pass"
os.environ["SESSION_SECRET"] = "test-session-secret"
os.environ["ORCHESTRATOR_STEP_DELAY_MS"] = "0"
os.environ["SSE_HEARTBEAT_SECONDS"] = "1"
# Deterministic unit/integration tests use stub providers (no external network)
os.environ["PROVIDER_MODE"] = "stub"

from app.core.config import get_settings

get_settings.cache_clear()

from app.db.session import Base, SessionLocal, engine, get_db
from app.main import app
from app.services.admin_service import ensure_providers


@pytest.fixture(autouse=True)
def _reset_db():
    from app.core import request_budget

    # In-memory rate limits must not bleed across tests (full-suite 429s).
    with request_budget._lock:
        request_budget._requests.clear()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_providers(db)
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    res = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "test-admin-pass"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]
