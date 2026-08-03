"""
Ticks every `stream_interval` seconds, diffs the current snapshot against the last one, and fans
a single serialized JSON frame out to every subscriber's bounded queue. Frame types: "snapshot"
(full state, sent on connect/resync), "delta" (only changed top-level keys), "heartbeat" (sent
after 5s of no changes, so clients can detect a dead connection). Mirrors TradeDashBoard's
actual broadcaster (a native WebSocket fanout, despite "SSE" in older env-var naming/comments).
"""
import asyncio
import json
from typing import Callable

HEARTBEAT_SECS = 5.0


class Broadcaster:
    def __init__(self, snapshot_provider: Callable[[], dict], interval: float, max_queue: int = 50):
        self._snapshot_provider = snapshot_provider
        self._interval = interval
        self._max_queue = max_queue
        self._subscribers: set[asyncio.Queue] = set()
        self._prev_snapshot: dict = {}
        self._seq = 0
        self._task: asyncio.Task | None = None

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def snapshot_frame(self) -> str:
        self._seq += 1
        self._prev_snapshot = dict(self._snapshot_provider())
        return json.dumps({"type": "snapshot", "seq": self._seq, "data": self._prev_snapshot})

    async def start(self) -> None:
        # dict(...) copies — if snapshot_provider ever returns the same live mutable object on
        # every call instead of a fresh dict, storing it by reference here would silently alias
        # _prev_snapshot to it, so every future diff compares the object against itself and never
        # detects a change.
        self._prev_snapshot = dict(self._snapshot_provider())
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        loop = asyncio.get_event_loop()
        last_change_time = loop.time()
        while True:
            await asyncio.sleep(self._interval)
            curr = self._snapshot_provider()
            changed = {k: v for k, v in curr.items() if self._prev_snapshot.get(k) != v}
            now = loop.time()

            if changed:
                self._seq += 1
                self._fanout(json.dumps({"type": "delta", "seq": self._seq, "data": changed}))
                last_change_time = now
            elif now - last_change_time >= HEARTBEAT_SECS:
                self._seq += 1
                self._fanout(json.dumps({"type": "heartbeat", "seq": self._seq}))
                last_change_time = now

            self._prev_snapshot = dict(curr)

    def _fanout(self, frame: str) -> None:
        for queue in list(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()  # drop the oldest — client will resync on the next gap
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(frame)
