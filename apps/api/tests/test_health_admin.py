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
    assert len(body["providers"]) >= 3
    # Never expose raw keys
    raw = res.text.lower()
    assert "sk-" not in raw
    assert "encrypted_api_key" not in raw


def test_admin_store_key_encrypted_not_returned(client, admin_token):
    secret = "sk-test-never-echo-this-value"
    res = client.patch(
        "/api/admin/providers/tavily",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"api_key": secret, "enabled": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["has_key_configured"] is True
    assert secret not in res.text
    assert body.get("api_key") is None

    with patch("httpx.Client") as provider_http:
        test = client.post(
            "/api/admin/test-connection",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"provider_id": "tavily"},
        )
    provider_http.assert_not_called()
    assert test.status_code == 200
    assert test.json()["ok"] is False
    assert test.json()["checked"] is False
    assert secret not in test.text
    settings = client.get(
        "/api/admin/providers", headers={"Authorization": f"Bearer {admin_token}"}
    ).json()
    tavily = next(row for row in settings["providers"] if row["id"] == "tavily")
    assert tavily["status"] == "untested"
    assert tavily["enabled"] and tavily["has_key_configured"]


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


def test_admin_comtrade_connection_reports_public_probe(client, admin_token):
    with patch("httpx.Client") as provider_http:
        get = provider_http.return_value.__enter__.return_value.get
        get.return_value.status_code = 200
        result = client.post(
            "/api/admin/test-connection",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"provider_id": "comtrade"},
        )

    assert result.status_code == 200
    assert result.json()["ok"] is True
    assert result.json()["checked"] is True
    assert get.call_args.args[0] == "https://comtradeapi.un.org/public/v1/preview/C/A/HS"


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


def test_admin_research_provider_keys_exa_comtrade(client, admin_token):
    """Tavily/Exa/UN Comtrade each accept encrypted per-provider keys from admin UI."""
    for pid, secret in (
        ("exa", "exa-test-secret-do-not-leak"),
        ("comtrade", "comtrade-test-secret-do-not-leak"),
    ):
        res = client.patch(
            f"/api/admin/providers/{pid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"api_key": secret},
        )
        assert res.status_code == 200, pid
        body = res.json()
        assert body["id"] == pid
        assert body["has_key_configured"] is True
        assert body["enabled"] is True  # auto-enable on key save
        assert secret not in res.text
        assert "encrypted_api_key" not in res.text.lower()

