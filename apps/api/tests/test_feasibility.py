import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.db.session import SessionLocal
from app.models.entities import Run
from app.schemas.contracts import Feasibility
from app.services import runs
from app.services.orchestrator import run_pipeline


@pytest.fixture
def run_id(client, monkeypatch):
    monkeypatch.setattr(runs, "schedule_pipeline", lambda _: None)
    return client.post("/api/runs", json={"product": "پسته"}).json()["run_id"]


def cost_updates():
    return [
        {"id": key, "amount": amount}
        for key, amount in (
            ("purchase", 1), ("packaging", 1), ("intl_freight", 1), ("duty", 1),
            ("inland", 0), ("insurance", 0), ("fees", 0),
        )
    ]


def recalculate(client, run_id, **payload):
    return client.post(f"/api/runs/{run_id}/feasibility", json=payload)


def test_unknown_costs_require_explicit_zero(client, run_id):
    response = recalculate(
        client, run_id,
        input_assumptions={"quantity": 100, "target_sell_price_usd": 0},
        cost_updates=cost_updates()[:4],
    )
    assert response.status_code == 200, response.text
    assert response.json()["missing_inputs"] == ["حمل داخلی", "بیمه", "کارمزدها"]
    assert all(row["total_cost"] is None for row in response.json()["scenario_results"])

    response = recalculate(client, run_id, cost_updates=cost_updates()[4:])
    assert response.status_code == 200, response.text
    assert response.json()["missing_inputs"] == []
    base = next(row for row in response.json()["scenario_results"] if row["id"] == "base")
    assert (base["revenue"], base["total_cost"], base["margin"], base["margin_pct"]) == (0, 400, -400, None)


def test_reopened_legacy_run_suppresses_totals_for_unknown_optional_cost(client, run_id):
    saved = recalculate(
        client, run_id,
        input_assumptions={"quantity": 100, "target_sell_price_usd": 10},
        cost_updates=cost_updates(),
    ).json()
    assert saved["scenario_results"][1]["margin"] == 600
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        legacy = Feasibility.model_validate(saved)
        inland = next(cost for cost in legacy.cost_items if cost.id == "inland")
        inland.required = False
        inland.amount = None
        legacy_json = legacy.model_dump_json()
        run.feasibility_json = legacy_json
        db.commit()

    snapshot = client.get(f"/api/runs/{run_id}").json()
    assert snapshot["feasibility"]["missing_inputs"] == ["حمل داخلی"]
    assert all(row["margin"] is None for row in snapshot["feasibility"]["scenario_results"])
    with SessionLocal() as db:
        assert db.get(Run, run_id).feasibility_json == legacy_json


@pytest.mark.parametrize("payload", [
    {"input_assumptions": {"quantity": -2}},
    {"input_assumptions": {"target_sell_price_usd": "bad"}},
    {"input_assumptions": {"target_sell_price_usd": "NaN"}},
    {"input_assumptions": {"fx_rate_usd_irr": 0}},
    {"cost_updates": [{"id": "purchase", "amount": -2}]},
    {"cost_updates": [{"id": "purchase", "currency": "XYZ", "amount": 2}]},
])
def test_invalid_finance_returns_client_error(client, run_id, payload):
    response = recalculate(client, run_id, **payload)
    assert response.status_code == 422, response.text
    assert isinstance(response.json(), dict)


def test_raw_nonfinite_finance_returns_client_error(client, run_id):
    response = client.post(
        f"/api/runs/{run_id}/feasibility",
        content='{"input_assumptions":{"quantity":1e999}}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422, response.text
    assert isinstance(response.json(), dict)


def test_fx_converts_irr_cost_to_usd(client, run_id):
    updates = cost_updates()
    updates[0].update(amount=500, currency="IRR")
    response = recalculate(
        client, run_id,
        input_assumptions={"quantity": 100, "target_sell_price_usd": 10, "unit": "بسته", "incoterm": "CIF"},
        cost_updates=updates,
    )
    assert response.status_code == 200, response.text
    assert response.json()["missing_inputs"] == ["نرخ تبدیل ریال به دلار"]

    response = recalculate(client, run_id, input_assumptions={"fx_rate_usd_irr": 100})
    assert response.status_code == 200, response.text
    finance = response.json()
    assert finance["incoterm"] == "CIF"
    assert finance["cost_items"][0]["unit"] == "بسته"
    base = next(row for row in finance["scenario_results"] if row["id"] == "base")
    assert (base["total_cost"], base["margin"]) == (800, 200)


def test_reports_use_finance_saved_before_and_after_finalization(client, run_id):
    response = recalculate(
        client, run_id,
        input_assumptions={"quantity": 100, "target_sell_price_usd": 10},
        cost_updates=cost_updates(),
    )
    assert response.status_code == 200, response.text
    finance = response.json()
    asyncio.run(run_pipeline(run_id))
    snapshot = client.get(f"/api/runs/{run_id}").json()
    assert snapshot["feasibility"] == snapshot["report"]["feasibility"] == finance

    response = recalculate(client, run_id, input_assumptions={"target_sell_price_usd": None})
    assert response.status_code == 200, response.text
    assert response.json()["missing_inputs"] == ["قیمت فروش هدف"]
    assert client.get(f"/api/runs/{run_id}/report").json()["feasibility"] == response.json()


def test_concurrent_finance_edits_preserve_distinct_inputs(client, run_id, monkeypatch):
    start = Barrier(2)
    original_recompute = runs.recompute

    def recompute_together(current, updates):
        if current.input_assumptions["quantity"] is None or current.input_assumptions["target_sell_price_usd"] is None:
            start.wait(timeout=5)
        return original_recompute(current, updates)

    monkeypatch.setattr(runs, "recompute", recompute_together)
    changes = [{"quantity": 100}, {"target_sell_price_usd": 10}]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda change: recalculate(client, run_id, input_assumptions=change), changes))
    assert all(response.status_code == 200 for response in responses)
    assumptions = client.get(f"/api/runs/{run_id}").json()["feasibility"]["input_assumptions"]
    assert (assumptions["quantity"], assumptions["target_sell_price_usd"]) == (100, 10)
