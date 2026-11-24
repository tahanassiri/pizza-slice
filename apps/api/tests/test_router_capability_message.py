"""Capability-button failures stay a fixed Persian sentence. The model payload is not returned."""

from __future__ import annotations

from app.db.session import SessionLocal
from app.models.entities import Run
from app.providers.openai_compat import canonical_base
from app.services import admin_service

SENTINEL = "RAW-MODEL-PAYLOAD-do-not-show-7f3a"
RAW_JSON = (
    '{"RAW_MODEL_PAYLOAD":"' + SENTINEL + '",'
    '"choices":[{"message":{"content":"not-a-decision"}}]}'
)
MODEL = "openai/gpt-test"
OTHER = "meta/llama-test"


def _save_key_and_select(model: str = MODEL) -> None:
    db = SessionLocal()
    try:
        admin_service.set_router_key(db, "openrouter", "sk-test-not-a-live-key")
        admin_service.activate_router_model(db, "openrouter", model)
    finally:
        db.close()


def _reply(monkeypatch, payload):
    monkeypatch.setattr(
        "app.providers.openai_compat.OpenAICompatLLM.complete_json",
        lambda self, prompt: payload,
    )


def test_unreadable_decision_json_is_persian_and_does_not_echo_payload(client, admin_token, monkeypatch):
    _reply(monkeypatch, RAW_JSON)
    _save_key_and_select()
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post(
        "/api/admin/routers/openrouter/capability",
        headers=headers,
        json={"model": OTHER},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is False
    assert body["message_fa"] == admin_service.CAPABILITY_PARSE_FAIL_FA
    assert SENTINEL not in res.text
    assert "{" not in body["message_fa"]
    db = SessionLocal()
    try:
        assert admin_service.read_router_capability(db, "openrouter", OTHER) == "failed"
        assert admin_service.get_selected_model(db) == MODEL
        assert admin_service.get_selected_provider(db) == "openrouter"
        assert db.query(Run).count() == 0
    finally:
        db.close()


def test_parser_exception_and_non_text_payload_stay_off_the_response(client, admin_token, monkeypatch):
    _save_key_and_select()
    headers = {"Authorization": f"Bearer {admin_token}"}

    def _explode(_raw):
        raise ValueError(RAW_JSON)

    monkeypatch.setattr("app.agents.llm_decide.parse_model_decision", _explode)
    _reply(monkeypatch, RAW_JSON)
    res = client.post(
        "/api/admin/routers/openrouter/capability",
        headers=headers,
        json={"model": MODEL},
    )
    assert res.status_code == 200, res.text
    assert res.json()["message_fa"] == admin_service.CAPABILITY_PARSE_FAIL_FA
    assert SENTINEL not in res.text

    monkeypatch.undo()
    _reply(monkeypatch, [{"type": "text", "text": SENTINEL}])
    res = client.post(
        "/api/admin/routers/openrouter/capability",
        headers=headers,
        json={"model": MODEL},
    )
    assert res.status_code == 200, res.text
    assert res.json()["message_fa"] == admin_service.CAPABILITY_PARSE_FAIL_FA
    assert SENTINEL not in res.text
    db = SessionLocal()
    try:
        assert admin_service.read_router_capability(db, "openrouter", MODEL) == "failed"
        assert admin_service.get_selected_model(db) == MODEL
        assert db.query(Run).count() == 0
    finally:
        db.close()


def test_connection_ping_message_is_unchanged(client, admin_token, monkeypatch):
    _reply(monkeypatch, RAW_JSON)
    _save_key_and_select()
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post(
        "/api/admin/routers/openrouter/test",
        headers=headers,
        json={"model": MODEL},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["message_fa"] == (
        f"Verified — اتصال «{MODEL}» روی {canonical_base('openrouter')} برقرار شد. "
        "این آزمون اتصال است و هنوز مجوز پژوهش نیست."
    )
    assert SENTINEL not in res.text
    db = SessionLocal()
    try:
        assert admin_service.read_router_capability(db, "openrouter", MODEL) == "unchecked"
    finally:
        db.close()
