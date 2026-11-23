import json
import time
from threading import Event

from app.db.session import SessionLocal
from app.models.entities import Run
from app.services import runs


def _seed_market(run_id: str, country: str) -> None:
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run is not None
        run.markets_json = json.dumps(
            [
                {
                    "country_code": country,
                    "country_name_fa": country,
                    "rank": 1,
                    "evidence": ["ev_seed"],
                    "opportunities": [],
                    "risks": [],
                    "metrics": [
                        {"key": "recommendation", "label_fa": "وضعیت", "value": "recommended"}
                    ],
                    "confidence": "low",
                    "unknowns": [],
                    "sources": [],
                }
            ]
        )
        db.commit()


def test_buyer_search_has_durable_pending_and_result(client, monkeypatch):
    run = client.post("/api/runs", json={"product": "mineral paper"}).json()
    run_path = f"/api/runs/{run['run_id']}"
    for _ in range(80):
        if client.get(run_path).json()["report"]:
            break
        time.sleep(0.025)
    else:
        raise AssertionError("Test analysis did not finish")
    _seed_market(run["run_id"], "DE")

    started = Event()
    allow_finish = Event()

    def slow_hits(_executor, *, product, country_code):
        del product, country_code
        started.set()
        allow_finish.wait(timeout=2)
        return [], []

    monkeypatch.setattr("app.agents.buyer_runner.collect_buyer_hits", slow_hits)
    monkeypatch.setattr(runs, "resolve_providers", lambda _db: type("B", (), {"search": None, "trade_service": None, "llm": None, "mode": "stub"})())
    try:
        response = client.post(f"{run_path}/buyers", json={"country_code": "DE"})
        assert response.status_code == 200
        pending = response.json()["buyer_search"]
        assert pending["status"] in {"queued", "running"}
        assert started.wait(timeout=1)
        duplicate = client.post(f"{run_path}/buyers", json={"country_code": "DE"}).json()
        assert duplicate["buyer_search"]["id"] == pending["id"]
    finally:
        allow_finish.set()

    for _ in range(80):
        snapshot = client.get(run_path).json()
        if snapshot["buyer_search"]["status"] == "partial":
            assert snapshot["buyer_search"]["error"]["code"] == "NO_BUYERS"
            assert snapshot["buyers"] == []
            return
        time.sleep(0.025)
    raise AssertionError("Buyer search did not persist its terminal state")
