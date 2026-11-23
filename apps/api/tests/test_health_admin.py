from __future__ import annotations


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

    test = client.post(
        "/api/admin/test-connection",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"provider_id": "tavily"},
    )
    assert test.status_code == 200
    assert secret not in test.text
