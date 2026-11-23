"""Phase D acceptance scenarios (blueprint §7 Phase D / §8)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from app.core.security import create_admin_session, validate_admin_session
from app.db.session import SessionLocal
from app.events.store import list_events


def _wait(client, run_id: str, timeout: float = 10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = client.get(f"/api/runs/{run_id}").json()
        if snap["run"]["phase"] == "report" and snap.get("report") is not None:
            return snap
        if snap["run"]["status"] in {"failed"}:
            return snap
        time.sleep(0.05)
    return client.get(f"/api/runs/{run_id}").json()


def test_invalid_product_rejected(client):
    res = client.post("/api/runs", json={"product": " ", "origin_country": "ایران"})
    assert res.status_code == 400
    assert res.json()["code"] == "INVALID_PRODUCT"


def test_ten_sequential_runs_isolated(client):
    products = [
        "پسته",
        "زعفران",
        "خرما",
        "فرش",
        "گلاب",
        "پسته شور",
        "رب گوجه",
        "کشمش",
        "زیره",
        "هل",
    ]
    run_ids = []
    for p in products:
        rid = client.post(
            "/api/runs", json={"product": p, "origin_country": "ایران"}
        ).json()["run_id"]
        run_ids.append(rid)

    snaps = [_wait(client, rid) for rid in run_ids]
    # No cross-contamination of products
    for rid, snap, product in zip(run_ids, snaps, products):
        assert snap["run"]["id"] == rid
        assert snap["run"]["product"] == product
        assert all(e["run_id"] == rid for e in snap["events"])
        assert snap["run"]["is_mock"] is False

    # Event stores remain partitioned
    db = SessionLocal()
    try:
        for rid in run_ids:
            ev = list_events(db, rid)
            assert ev
            assert all(e.run_id == rid for e in ev)
    finally:
        db.close()


def test_provider_missing_key_honest_buyers(client):
    rid = client.post(
        "/api/runs", json={"product": "پسته", "origin_country": "ایران"}
    ).json()["run_id"]
    _wait(client, rid)
    snap = client.post(
        f"/api/runs/{rid}/select-country", json={"country_code": "AE"}
    ).json()
    assert snap["buyers"] == []
    # Honest empty — no fabricated companies
    assert snap["run"]["selected_country"] == "AE"


def test_quota_exhausted_surface(client, monkeypatch):
    """Budget exhaustion / provider rate-limit surfaces honestly — no fake markets."""
    from app.tools.budget import BudgetExceeded, consume, ensure_run_budget
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        b = ensure_run_budget(db, "run_quota_d")
        b.max_search_queries = 1
        b.search_queries_used = 0
        db.commit()
        consume(db, b, kind="search", units=1, run_id="run_quota_d", tool_name="search_web")
        try:
            consume(db, b, kind="search", units=1, run_id="run_quota_d", tool_name="search_web")
            assert False, "expected BudgetExceeded"
        except BudgetExceeded:
            pass

    # Legacy KeyedTavilySearch still fails honestly if somehow called
    class RateLimited:
        status_code = 429

        def json(self):
            return {}

    with patch("httpx.Client") as client_cls:
        http = MagicMock()
        http.__enter__.return_value = http
        http.post.return_value = RateLimited()
        client_cls.return_value = http
        from app.providers.keyed import KeyedTavilySearch

        result = KeyedTavilySearch("tvly-test-key").search_markets("پسته", "ایران")
        assert result.ok is False
        assert result.error_code == "RATE_LIMITED"


def test_admin_session_ttl_and_revoke(client, admin_token):
    assert validate_admin_session(admin_token)
    client.post("/api/admin/logout", headers={"Authorization": f"Bearer {admin_token}"})
    assert not validate_admin_session(admin_token)
    # New session works
    token2 = create_admin_session()
    assert validate_admin_session(token2)


def test_feasibility_full_calc_deterministic(client):
    rid = client.post(
        "/api/runs", json={"product": "پسته", "origin_country": "ایران"}
    ).json()["run_id"]
    _wait(client, rid)

    res = client.post(
        f"/api/runs/{rid}/feasibility",
        json={
            "input_assumptions": {
                "quantity": 1000,
                "target_sell_price_usd": 12,
            },
            "cost_updates": [
                {"id": "purchase", "amount": 5},
                {"id": "packaging", "amount": 0.5},
                {"id": "intl_freight", "amount": 1.5},
                {"id": "duty", "amount": 0.5},
                {"id": "inland", "amount": 0},
                {"id": "insurance", "amount": 0},
                {"id": "fees", "amount": 0},
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_mock_sample"] is False
    assert body["missing_inputs"] == []
    base = next(s for s in body["scenario_results"] if s["id"] == "base")
    assert base["revenue"] == 12000
    assert base["total_cost"] == 7500  # 1000 * (5+0.5+1.5+0.5)
    assert base["margin"] == 4500


def test_report_printable_fields(client):
    rid = client.post(
        "/api/runs", json={"product": "زعفران", "origin_country": "ایران"}
    ).json()["run_id"]
    snap = _wait(client, rid)
    report = snap.get("report") or client.get(f"/api/runs/{rid}/report").json()
    assert report["product"] == "زعفران"
    assert report["origin_country"] == "ایران"
    assert "summary_fa" in report
    assert "risks_fa" in report
    assert "assumptions_fa" in report
    assert "sources" in report
    assert report["is_mock"] is False
