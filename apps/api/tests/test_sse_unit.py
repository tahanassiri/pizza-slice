from __future__ import annotations

import asyncio
import json

import pytest

from app.events.broadcaster import broadcaster, sse_event_stream


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

    agen = sse_event_stream(
        run_id=run_id,
        initial_events=initial,
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
        await broadcaster.publish(
            run_id,
            {
                "event_id": "evt_c",
                "run_id": run_id,
                "phase": "report",
                "status": "partial",
                "message_fa": "c",
                "timestamp": "2026-01-01T00:00:02+00:00",
            },
        )

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
    agen = sse_event_stream(run_id=run_id, initial_events=[], heartbeat_seconds=0.05)
    item = await agen.__anext__()
    assert item["event"] == "heartbeat"
    assert "phase" not in json.loads(item["data"])
    await agen.aclose()
