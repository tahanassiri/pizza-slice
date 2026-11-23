from __future__ import annotations

import asyncio
import time

import pytest

from app.db.session import SessionLocal
from app.events.store import list_events
from app.services import orchestrator, runs


@pytest.mark.asyncio
async def test_unexpected_pipeline_exception_is_persisted(client, monkeypatch):
    monkeypatch.setattr(runs, "schedule_pipeline", lambda _run_id: None)
    run_id = client.post(
        "/api/runs", json={"product": "پسته", "origin_country": "ایران"}
    ).json()["run_id"]

    def fail(_db):
        raise ValueError("private provider response")

    monkeypatch.setattr(orchestrator, "resolve_providers", fail)
    await orchestrator.run_pipeline(run_id)

    snapshot = client.get(f"/api/runs/{run_id}").json()
    assert snapshot["run"]["status"] == "failed"
    assert snapshot["run"]["error"]["code"] == "PIPELINE_ERROR"
    terminal = snapshot["events"][-1]
    assert terminal["status"] == "failed"
    assert terminal["error_code"] == "PIPELINE_ERROR"
    assert "private provider response" not in terminal["message_fa"]


def _wait_pipeline(client, run_id: str, timeout: float = 8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = client.get(f"/api/runs/{run_id}").json()
        if snap["events"]:
            last = snap["events"][-1]
            if last["status"] == "failed" or (
                last["phase"] == "report"
                and last["status"] in {"partial", "completed"}
                and snap.get("report") is not None
            ):
                return snap
        time.sleep(0.05)
    return client.get(f"/api/runs/{run_id}").json()


def _read_sse_until(client, path: str, *, headers=None, params=None, predicate, timeout=5.0):
    """Read ASGI body chunks directly because TestClient buffers open streams."""
    request = client.build_request("GET", path, headers=headers, params=params)

    async def read():
        disconnect = asyncio.Event()
        buf = ""
        request_sent = False

        async def receive():
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await disconnect.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            nonlocal buf
            if message["type"] == "http.response.start":
                assert message["status"] == 200
            if message["type"] == "http.response.body":
                buf += message.get("body", b"").decode("utf-8")
                if predicate(buf):
                    disconnect.set()

        scope = {
            "type": "http",
            "method": "GET",
            "path": request.url.path,
            "query_string": request.url.query,
            "headers": [(name.lower(), value) for name, value in request.headers.raw],
        }
        await asyncio.wait_for(client.app(scope, receive, send), timeout=timeout)
        assert predicate(buf), f"SSE predicate not met. buf={buf[:500]!r}"
        return buf

    return asyncio.run(read())


def test_create_run_and_snapshot(client):
    res = client.post(
        "/api/runs",
        json={"product": "پسته خام", "origin_country": "ایران"},
    )
    assert res.status_code == 200
    run_id = res.json()["run_id"]
    assert run_id.startswith("run_")

    snap = _wait_pipeline(client, run_id)
    assert snap["run"]["is_mock"] is False
    assert snap["run"]["product"] == "پسته خام"
    assert len(snap["events"]) >= 3
    assert snap["markets"] == []
    assert snap["run"]["status"] in {"partial", "completed", "running", "queued"}
    if snap.get("report"):
        assert snap["report"]["is_mock"] is False


def test_event_ordering_monotonic(client):
    run_id = client.post(
        "/api/runs",
        json={"product": "زعفران", "origin_country": "ایران"},
    ).json()["run_id"]
    snap = _wait_pipeline(client, run_id)
    events = snap["events"]
    assert len(events) >= 4
    ids = [e["event_id"] for e in events]
    assert len(ids) == len(set(ids))
    db = SessionLocal()
    try:
        ordered = list_events(db, run_id)
        assert [e.event_id for e in ordered] == ids
    finally:
        db.close()


def test_event_store_resume_cursor(client):
    run_id = client.post(
        "/api/runs",
        json={"product": "خرما", "origin_country": "ایران"},
    ).json()["run_id"]
    snap = _wait_pipeline(client, run_id)
    events = snap["events"]
    assert len(events) >= 3
    mid = events[1]["event_id"]
    db = SessionLocal()
    try:
        resumed = list_events(db, run_id, after_event_id=mid)
        assert [e.event_id for e in resumed] == [e["event_id"] for e in events[2:]]
    finally:
        db.close()


def test_sse_http_endpoint_content_and_heartbeat(client):
    run_id = client.post(
        "/api/runs",
        json={"product": "فرش", "origin_country": "ایران"},
    ).json()["run_id"]
    snap = _wait_pipeline(client, run_id)
    assert snap["events"]
    first_id = snap["events"][0]["event_id"]

    buf = _read_sse_until(
        client,
        f"/api/runs/{run_id}/events",
        params={"last_event_id": first_id},
        predicate=lambda b: "event: run_event" in b and "event: heartbeat" in b,
        timeout=6.0,
    )
    assert "event: run_event" in buf
    assert "event: heartbeat" in buf
    # Resume should not re-send the cursor event itself
    assert f"id: {first_id}\r\n" not in buf


def test_sse_header_resume_no_history_replay(client):
    run_id = client.post(
        "/api/runs",
        json={"product": "پسته", "origin_country": "ایران"},
    ).json()["run_id"]
    snap = _wait_pipeline(client, run_id)
    last = snap["events"][-1]["event_id"]

    buf = _read_sse_until(
        client,
        f"/api/runs/{run_id}/events",
        headers={"Last-Event-ID": last},
        params={"last_event_id": snap["events"][0]["event_id"]},
        predicate=lambda b: "event: heartbeat" in b,
        timeout=6.0,
    )
    assert "event: heartbeat" in buf
    for event in snap["events"]:
        assert f"id: {event['event_id']}\r\n" not in buf


def test_feasibility_deterministic(client):
    run_id = client.post(
        "/api/runs",
        json={"product": "پسته", "origin_country": "ایران"},
    ).json()["run_id"]
    _wait_pipeline(client, run_id)

    res = client.post(
        f"/api/runs/{run_id}/feasibility",
        json={
            "cost_updates": [
                {"id": "purchase", "amount": 10},
                {"id": "packaging", "amount": 1},
                {"id": "intl_freight", "amount": 2},
                {"id": "duty", "amount": 1},
            ]
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_mock_sample"] is False
    assert body["missing_inputs"]
    assert all(s["revenue"] is None for s in body["scenario_results"])


def test_select_country_buyers_honest_empty(client):
    run_id = client.post(
        "/api/runs",
        json={"product": "پسته", "origin_country": "ایران"},
    ).json()["run_id"]
    _wait_pipeline(client, run_id)
    res = client.post(
        f"/api/runs/{run_id}/select-country",
        json={"country_code": "AE"},
    )
    assert res.status_code == 200
    snap = res.json()
    assert snap["run"]["selected_country"] == "AE"
    assert snap["buyers"] == []
