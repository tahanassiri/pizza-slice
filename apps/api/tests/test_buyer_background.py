import time
from threading import Event
from types import SimpleNamespace

from app.providers.base import ProviderResult
from app.services import runs


def test_buyer_search_has_durable_pending_and_result(client, monkeypatch):
    run = client.post("/api/runs", json={"product": "mineral paper"}).json()
    run_path = f"/api/runs/{run['run_id']}"
    # Let the stub analysis finish before replacing the search adapter.
    for _ in range(80):
        if client.get(run_path).json()["report"]:
            break
        time.sleep(0.025)
    else:
        raise AssertionError("Test analysis did not finish")

    started = Event()
    allow_finish = Event()

    def search_buyers(_product, _country):
        started.set()
        allow_finish.wait(timeout=2)
        return ProviderResult(ok=False, error_code="NO_BUYERS", message_fa="بدون نتیجه")

    monkeypatch.setattr(
        runs,
        "resolve_providers",
        lambda _db: SimpleNamespace(search=SimpleNamespace(search_buyers=search_buyers)),
    )
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
