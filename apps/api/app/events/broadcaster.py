"""In-process SSE fan-out. Heartbeats keep the connection alive — not fake progress."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from threading import Lock
from typing import Any


class EventBroadcaster:
    def __init__(self) -> None:
        self._subs: dict[str, dict[asyncio.Queue[dict[str, Any] | None], asyncio.AbstractEventLoop]] = (
            defaultdict(dict)
        )
        self._lock = Lock()

    async def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any] | None]:
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=1)
        with self._lock:
            self._subs[run_id][q] = asyncio.get_running_loop()
        return q

    async def unsubscribe(self, run_id: str, q: asyncio.Queue[dict[str, Any] | None]) -> None:
        with self._lock:
            self._subs[run_id].pop(q, None)
            if not self._subs[run_id]:
                self._subs.pop(run_id, None)

    async def publish(self, run_id: str, event: dict[str, Any]) -> None:
        self._notify(run_id, event)

    async def close_run(self, run_id: str) -> None:
        self._notify(run_id, None)

    def _notify(self, run_id: str, event: dict[str, Any] | None) -> None:
        with self._lock:
            targets = list(self._subs.get(run_id, {}).items())
        for queue, loop in targets:
            try:
                loop.call_soon_threadsafe(self._enqueue, queue, event)
            except RuntimeError:
                # The subscriber's loop can close concurrently with notification.
                pass

    @staticmethod
    def _enqueue(queue: asyncio.Queue, event: dict[str, Any] | None) -> None:
        # A single wakeup is enough to reconcile every committed event.
        if event is None and queue.full():
            queue.get_nowait()
        if not queue.full():
            queue.put_nowait(event)


broadcaster = EventBroadcaster()


async def sse_event_stream(
    *,
    run_id: str,
    load_events: Callable[[str | None], Awaitable[list[dict[str, Any]]]],
    after_event_id: str | None,
    heartbeat_seconds: float,
) -> AsyncIterator[dict[str, Any]]:
    """Use live notifications to wake readers and the database to order events."""
    q = await broadcaster.subscribe(run_id)
    try:
        while True:
            for event in await load_events(after_event_id):
                after_event_id = event["event_id"]
                yield {
                    "event": "run_event",
                    "id": after_event_id,
                    "data": json.dumps(event, ensure_ascii=False),
                }

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
    finally:
        await broadcaster.unsubscribe(run_id, q)
