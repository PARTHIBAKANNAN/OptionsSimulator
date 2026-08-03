"""
Shared state handed off between the Fyers callback thread (LiveEngine's WebSocket runs its own
thread, per fyers-apiv3's blocking .connect()) and the asyncio broadcaster/HTTP handlers —
mirrors TradeDashBoard's app/state.py MarketState pattern.
"""
import asyncio
import threading


class SharedState:
    def __init__(self):
        self._lock = threading.RLock()
        self._snapshot: dict = {}

    def update(self, snapshot: dict) -> None:
        with self._lock:
            self._snapshot = snapshot

    def get(self) -> dict:
        with self._lock:
            return dict(self._snapshot)


class PendingSignalRegistry:
    """
    A signal awaiting approval can be resolved by whichever channel responds first — the web
    (POST /api/paper/signals/{id}/approve|reject) or the existing Telegram Approve/Reject button.
    Both just call resolve() with the same signal_id; only the first call wins.
    """

    def __init__(self):
        self._pending: dict[str, dict] = {}
        self._futures: dict[str, asyncio.Future] = {}

    def register(self, signal_id: str, signal_data: dict, loop: asyncio.AbstractEventLoop) -> asyncio.Future:
        future = loop.create_future()
        self._pending[signal_id] = signal_data
        self._futures[signal_id] = future
        return future

    def resolve(self, signal_id: str, decision: str) -> bool:
        future = self._futures.get(signal_id)
        if future is None or future.done():
            return False
        future.set_result(decision)
        self._pending.pop(signal_id, None)
        return True

    def list_pending(self) -> list[dict]:
        return list(self._pending.values())


shared_state = SharedState()
pending_signals = PendingSignalRegistry()
