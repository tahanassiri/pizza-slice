"""In-process SSE fan-out. Heartbeats keep the connection alive — not fake progress."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any


class EventBroadcaster:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue[dict[str, Any] | None]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any] | None]:
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subs[run_id].add(q)
        return q

    async def unsubscribe(self, run_id: str, q: asyncio.Queue[dict[str, Any] | None]) -> None:
        async with self._lock:
            self._subs[run_id].discard(q)
            if not self._subs[run_id]:
                self._subs.pop(run_id, None)

    async def publish(self, run_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._subs.get(run_id, set()))
        for q in targets:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest-style: skip if subscriber is too slow
                pass

    async def close_run(self, run_id: str) -> None:
        async with self._lock:
            targets = list(self._subs.get(run_id, set()))
        for q in targets:
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass


broadcaster = EventBroadcaster()


async def sse_event_stream(
    *,
    run_id: str,
    initial_events: list[dict[str, Any]],
    heartbeat_seconds: float,
) -> AsyncIterator[dict[str, Any]]:
    """Yields dicts with keys: event (str), data (str), id (optional)."""
    import json

    for ev in initial_events:
        yield {
            "event": "run_event",
            "id": ev.get("event_id"),
            "data": json.dumps(ev, ensure_ascii=False),
        }

    q = await broadcaster.subscribe(run_id)
    try:
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=heartbeat_seconds)
            except TimeoutError:
                yield {
                    "event": "heartbeat",
                    "data": json.dumps({"ok": True}, ensure_ascii=False),
                }
                continue
            if item is None:
                break
            yield {
                "event": "run_event",
                "id": item.get("event_id"),
                "data": json.dumps(item, ensure_ascii=False),
            }
    finally:
        await broadcaster.unsubscribe(run_id, q)
