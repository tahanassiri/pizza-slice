from __future__ import annotations

from unittest.mock import patch

from app.providers.keyed import KeyedGeminiLLM


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["service"] == "nova-export-api"


def test_admin_auth_required(client):
    res = client.get("/api/admin/providers")
    assert res.status_code == 401


def test_admin_login_fail(client):
    res = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert res.status_code == 401
    assert res.json()["code"] == "AUTH_FAILED"


def test_admin_login_and_providers(client, admin_token):
    res = client.get(
        "/api/admin/providers",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_mock_ui"] is False
    assert len(body["providers"]) >= 1
    # Trade sources: free_web + active_llm — no mandatory WITS/Comtrade/Tavily
    ids = {s["id"] for s in body.get("trade_sources") or []}
    assert "free_web" in ids
    assert "wits" not in ids
    assert "comtrade" not in ids
    raw = res.text.lower()
    assert "sk-" not in raw
    assert "encrypted_api_key" not in raw


def test_admin_model_key_presence_is_not_connection_success(client, admin_token):
    model = "gemini-3.8-flash"
    secret = "gemini-placeholder-no-live-request"
    headers = {"Authorization": f"Bearer {admin_token}"}
    stored = client.put(
        "/api/admin/model/key", headers=headers, json={"model": model, "api_key": secret}
    )
    assert stored.status_code == 200
    assert stored.json()["has_key_configured"] is True

    with patch("httpx.Client") as provider_http:
        result = client.post(
            "/api/admin/test-connection",
            headers=headers,
            json={"provider_id": f"model:{model}"},
        )
    provider_http.assert_not_called()
    assert result.status_code == 200
    assert result.json()["ok"] is False
    assert result.json()["checked"] is False
    assert secret not in result.text


def test_gemini_sends_key_in_header_and_keeps_url_clean():
    key = "gemini-placeholder-no-live-request"
    with patch("httpx.Client") as provider_http:
        post = provider_http.return_value.__enter__.return_value.post
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "080251"}]}}]
        }
        hs_code, _ = KeyedGeminiLLM(key).classify_hs("پسته", None)

    assert hs_code == "080251"
    assert post.call_args.args[0].endswith("/gemini-3.8-flash:generateContent")
    assert post.call_args.kwargs["headers"] == {"x-goog-api-key": key}


def test_admin_rejects_removed_trade_provider_keys(client, admin_token):
    """Tavily/Exa/Comtrade are not mandatory admin providers anymore."""
    for pid in ("tavily", "exa", "comtrade"):
        res = client.patch(
            f"/api/admin/providers/{pid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"api_key": "should-not-matter", "enabled": True},
        )
        # Either 404 (not seeded) or soft-disabled legacy row without enabling paid path
        assert res.status_code in {200, 404}
        if res.status_code == 200:
            # Legacy rows stay soft-disabled by ensure_providers
            settings = client.get(
                "/api/admin/providers", headers={"Authorization": f"Bearer {admin_token}"}
            ).json()
            # trade_sources must not advertise them as required
            ids = {s["id"] for s in settings.get("trade_sources") or []}
            assert pid not in ids
