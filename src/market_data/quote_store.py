"""
Immutable QuoteSnapshot and Thread-Safe QuoteStore for Nukebox options trading platform.

Enforces monotonic versioning and atomic snapshot updates. WebSocket is the sole
authority for live price mutations.
"""
from dataclasses import dataclass
import threading
import time
from typing import Dict, List, Optional


@dataclass(frozen=True, slots=True)
class QuoteSnapshot:
    canonical_id: str
    fyers_symbol: str
    ltp: float
    bid: float
    ask: float
    open_interest: int
    volume: int
    exchange_timestamp: float
    receive_epoch_timestamp: float
    receive_monotonic_timestamp: float
    version: int
    prev_close: float = 0.0
    pchange: float = 0.0

    @property
    def oi(self) -> int:
        """Compatibility alias for open_interest."""
        return self.open_interest

    @property
    def symbol(self) -> str:
        """Compatibility alias for fyers_symbol."""
        return self.fyers_symbol

    @property
    def spread(self) -> float:
        """Absolute spread (ask - bid)."""
        return max(0.0, self.ask - self.bid)

    @property
    def spread_bps(self) -> float:
        """Spread in basis points relative to ask."""
        if self.ask > 0:
            return ((self.ask - self.bid) / self.ask) * 10000.0
        return 0.0

    def age_ms(self) -> float:
        """Quote age in milliseconds computed via monotonic clock."""
        return (time.monotonic() - self.receive_monotonic_timestamp) * 1000.0


class QuoteStore:
    def __init__(self):
        self._snapshots_by_canonical: Dict[str, QuoteSnapshot] = {}
        self._snapshots_by_symbol: Dict[str, QuoteSnapshot] = {}
        self._lock = threading.RLock()

    def update_tick(
        self,
        canonical_id: str,
        fyers_symbol: str,
        ltp: float,
        bid: float,
        ask: float,
        oi: int = 0,
        volume: int = 0,
        exchange_ts: float = 0.0,
        prev_close: float = 0.0,
        pchange: float = 0.0,
    ) -> QuoteSnapshot:
        """
        Atomically updates the quote for a canonical instrument and increments its version.
        Captures monotonic time for freshness verification and epoch time for persistence.
        """
        epoch_now = time.time()
        mono_now = time.monotonic()
        if exchange_ts <= 0:
            exchange_ts = epoch_now

        with self._lock:
            prev = self._snapshots_by_canonical.get(canonical_id)
            ver = (prev.version + 1) if prev else 1

            # Retain non-zero volume/OI/prev_close if incoming tick omits them
            final_oi = oi if oi > 0 else (prev.open_interest if prev else 0)
            final_vol = volume if volume > 0 else (prev.volume if prev else 0)
            final_prev_close = prev_close if prev_close > 0 else (prev.prev_close if prev else 0.0)

            snapshot = QuoteSnapshot(
                canonical_id=canonical_id,
                fyers_symbol=fyers_symbol,
                ltp=float(ltp),
                bid=float(bid),
                ask=float(ask),
                open_interest=int(final_oi),
                volume=int(final_vol),
                exchange_timestamp=float(exchange_ts),
                receive_epoch_timestamp=epoch_now,
                receive_monotonic_timestamp=mono_now,
                version=ver,
                prev_close=float(final_prev_close),
                pchange=float(pchange),
            )
            self._snapshots_by_canonical[canonical_id] = snapshot
            self._snapshots_by_symbol[fyers_symbol] = snapshot
            return snapshot

    def get_snapshot(self, canonical_id: str) -> Optional[QuoteSnapshot]:
        with self._lock:
            return self._snapshots_by_canonical.get(canonical_id)

    def get_snapshot_by_symbol(self, fyers_symbol: str) -> Optional[QuoteSnapshot]:
        with self._lock:
            return self._snapshots_by_symbol.get(fyers_symbol)

    def get_all_snapshots(self) -> Dict[str, QuoteSnapshot]:
        with self._lock:
            return dict(self._snapshots_by_canonical)

    def get_all_snapshots_by_symbol(self) -> Dict[str, QuoteSnapshot]:
        with self._lock:
            return dict(self._snapshots_by_symbol)

    def get_active_quote_count(self, max_age_ms: float = 2000.0) -> int:
        """Returns number of snapshots received within max_age_ms."""
        mono_now = time.monotonic()
        with self._lock:
            return sum(
                1 for snap in self._snapshots_by_canonical.values()
                if (mono_now - snap.receive_monotonic_timestamp) * 1000.0 <= max_age_ms
            )

    def total_quotes_count(self) -> int:
        with self._lock:
            return len(self._snapshots_by_canonical)

    def clear(self) -> None:
        with self._lock:
            self._snapshots_by_canonical.clear()
            self._snapshots_by_symbol.clear()
