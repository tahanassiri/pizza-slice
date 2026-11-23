from __future__ import annotations

import asyncio
import json

import pytest

from app.events.broadcaster import broadcaster, sse_event_stream


@pytest.mark.asyncio
async def test_publish_wakes_subscriber_on_its_own_loop(monkeypatch):
    run_id = "run_cross_loop"
    loop = asyncio.get_running_loop()
    queue = await broadcaster.subscribe(run_id)
    put = queue.put_nowait

    def put_on_owner_loop(item):
        assert asyncio.get_running_loop() is loop
        put(item)

    monkeypatch.setattr(queue, "put_nowait", put_on_owner_loop)
    try:
        event = {"event_id": "evt_thread"}
        await asyncio.to_thread(lambda: asyncio.run(broadcaster.publish(run_id, event)))
        assert await asyncio.wait_for(queue.get(), timeout=0.5) == event
    finally:
        await broadcaster.unsubscribe(run_id, queue)


@pytest.mark.asyncio
async def test_persisted_events_are_read_in_order_after_replay_starts():
    run_id = "run_handoff"
    rows = [{"event_id": "evt_old"}]

    async def load_events(after):
        return rows[next((i + 1 for i, row in enumerate(rows) if row["event_id"] == after), 0):]

    stream = sse_event_stream(
        run_id=run_id,
        load_events=load_events,
        after_event_id=None,
        heartbeat_seconds=0.02,
    )
    try:
        assert (await anext(stream))["id"] == "evt_old"
        rows.extend([{"event_id": "evt_gap"}, {"event_id": "evt_later"}])
        # The latest notification arrives first and the earlier one is lost.
        await broadcaster.publish(run_id, rows[-1])
        assert (await anext(stream))["id"] == "evt_gap"
        assert (await anext(stream))["id"] == "evt_later"
        assert (await anext(stream))["event"] == "heartbeat"
        rows.append({"event_id": "evt_without_notification"})
        assert (await anext(stream))["id"] == "evt_without_notification"
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_sse_stream_orders_resume_then_live_then_heartbeat():
    run_id = "run_sse_unit"
    initial = [
        {
            "event_id": "evt_a",
            "run_id": run_id,
            "phase": "search",
            "status": "running",
            "message_fa": "a",
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
        {
            "event_id": "evt_b",
            "run_id": run_id,
            "phase": "search",
            "status": "completed",
            "message_fa": "b",
            "timestamp": "2026-01-01T00:00:01+00:00",
        },
    ]

    async def load_events(after):
        return initial[next((i + 1 for i, row in enumerate(initial) if row["event_id"] == after), 0):]

    agen = sse_event_stream(
        run_id=run_id,
        load_events=load_events,
        after_event_id=None,
        heartbeat_seconds=0.2,
    )

    first = await agen.__anext__()
    second = await agen.__anext__()
    assert first["event"] == "run_event"
    assert first["id"] == "evt_a"
    assert json.loads(first["data"])["event_id"] == "evt_a"
    assert second["id"] == "evt_b"

    # Publish live event after subscription is active (third pull waits on queue)
    async def _publish_soon():
        await asyncio.sleep(0.05)
        initial.append(
            {
                "event_id": "evt_c",
                "run_id": run_id,
                "phase": "report",
                "status": "partial",
                "message_fa": "c",
                "timestamp": "2026-01-01T00:00:02+00:00",
            }
        )
        await broadcaster.publish(run_id, initial[-1])

    task = asyncio.create_task(_publish_soon())
    third = await agen.__anext__()
    await task
    assert third["event"] == "run_event"
    assert third["id"] == "evt_c"

    hb = await agen.__anext__()
    assert hb["event"] == "heartbeat"
    assert json.loads(hb["data"])["ok"] is True

    await agen.aclose()


@pytest.mark.asyncio
async def test_heartbeat_is_not_progress_event():
    run_id = "run_hb_only"

    async def load_events(_after):
        return []

    agen = sse_event_stream(
        run_id=run_id, load_events=load_events, after_event_id=None, heartbeat_seconds=0.05
    )
    item = await agen.__anext__()
    assert item["event"] == "heartbeat"
    assert "phase" not in json.loads(item["data"])
    await agen.aclose()
