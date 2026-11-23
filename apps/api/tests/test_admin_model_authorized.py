"""Admin-selected models run even when the provider is billable."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

from app.providers.keyed import GEMINI_GENERATE_TIMEOUT, build_llm

CONCLUDE = json.dumps(
    {
        "action": "conclude",
        "rationale_fa": "شواهد امارات برای زعفران کافی نیست",
        "stop_reason": "insufficient_evidence",
        "market_proposals": [],
        "unknowns": ["تقاضای امارات نامشخص"],
        "conflicts": [],
    },
    ensure_ascii=False,
)


class _Resp:
    def __init__(self, status: int, text: str):
        self.status_code = status
        self.text = text

    def json(self):
        return json.loads(self.text)


def _gemini_ok() -> _Resp:
    body = json.dumps(
        {"candidates": [{"content": {"parts": [{"text": CONCLUDE}]}}]},
        ensure_ascii=False,
    )
    return _Resp(200, body)


def _wait_report(client, run_id: str) -> dict:
    snap = None
    for _ in range(80):
        snap = client.get(f"/api/runs/{run_id}").json()
        if snap.get("report"):
            return snap
        time.sleep(0.05)
    raise AssertionError(f"report missing: {snap}")


def test_gemini_generate_content_waits_longer_than_twenty_seconds():
    """The live hydrogen call ReadTimeout'd at the old 20s client timeout."""

    assert GEMINI_GENERATE_TIMEOUT == 120.0
    llm = build_llm("google", "not-a-live-key", "gemini-4-hydrogen")
    assert llm.timeout == 120.0
    with patch("app.providers.keyed.httpx.Client") as client_cls:
        post = client_cls.return_value.__enter__.return_value.post
        post.return_value = _gemini_ok()
        llm.classify_hs("زعفران", None)
        llm.decide_research_action({"product": "زعفران"})
    assert client_cls.call_count == 2
    for call in client_cls.call_args_list:
        assert call.kwargs["timeout"] == 120.0


def test_selected_gemini_is_called_without_a_no_cost_gate(client, admin_token, monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "auto")
    from app.core.config import get_settings

    get_settings.cache_clear()
    headers = {"Authorization": f"Bearer {admin_token}"}
    secret = "gemini-test-key-not-a-real-secret"
    selected = client.put(
        "/api/admin/model",
        headers=headers,
        json={"model": "gemini-4-hydrogen"},
    )
    assert selected.status_code == 200
    stored = client.put(
        "/api/admin/model/key",
        headers=headers,
        json={"model": "gemini-4-hydrogen", "api_key": secret},
    )
    assert stored.status_code == 200

    with patch("app.providers.keyed.httpx.Client") as client_cls:
        post = client_cls.return_value.__enter__.return_value.post
        post.return_value = _gemini_ok()
        run_id = client.post(
            "/api/runs",
            json={"product": "زعفران", "origin_country": "ایران"},
        ).json()["run_id"]
        snap = _wait_report(client, run_id)

    get_settings.cache_clear()
    assert post.called
    url = post.call_args.args[0]
    assert url.endswith("/gemini-4-hydrogen:generateContent")
    assert post.call_args.kwargs["headers"]["x-goog-api-key"] == secret
    text = json.dumps(snap, ensure_ascii=False)
    assert secret not in text
    assert "بدون‌هزینه" not in text
    assert "شواهد امارات برای زعفران کافی نیست" in snap["report"]["summary_fa"]
    assert snap["markets"] == []


def test_billing_failure_is_shown_and_not_retried_as_another_model(client, admin_token, monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "auto")
    from app.core.config import get_settings

    get_settings.cache_clear()
    headers = {"Authorization": f"Bearer {admin_token}"}
    client.put("/api/admin/model", headers=headers, json={"model": "gemini-4-hydrogen"})
    client.put(
        "/api/admin/model/key",
        headers=headers,
        json={"model": "gemini-4-hydrogen", "api_key": "gemini-test-key-not-a-real-secret"},
    )
    with patch("app.providers.keyed.httpx.Client") as client_cls:
        post = client_cls.return_value.__enter__.return_value.post
        post.return_value = _Resp(402, "billing account disabled")
        run_id = client.post(
            "/api/runs",
            json={"product": "زعفران", "origin_country": "ایران"},
        ).json()["run_id"]
        snap = _wait_report(client, run_id)
    get_settings.cache_clear()
    assert post.call_count == 1
    assert snap["run"]["error"]["code"] == "MODEL_BILLING"
    assert "Billing problem" in snap["report"]["summary_fa"]
    assert "بدون‌هزینه" not in snap["report"]["summary_fa"]
