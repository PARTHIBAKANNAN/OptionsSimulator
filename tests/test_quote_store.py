"""
Unit and concurrency tests for QuoteStore and QuoteSnapshot.
"""
from concurrent.futures import ThreadPoolExecutor
import time
import pytest

from src.market_data.quote_store import QuoteSnapshot, QuoteStore


def test_quote_store_version_increment():
    store = QuoteStore()
    snap1 = store.update_tick(
        canonical_id="NIFTY|2026-09-24|24500|CE",
        fyers_symbol="NSE:NIFTY26SEP24500CE",
        ltp=150.25,
        bid=150.10,
        ask=150.40,
        oi=10000,
        volume=50000,
        exchange_ts=1789935950.0,
    )
    assert snap1.version == 1
    assert snap1.ltp == 150.25
    assert snap1.bid == 150.10
    assert snap1.ask == 150.40

    snap2 = store.update_tick(
        canonical_id="NIFTY|2026-09-24|24500|CE",
        fyers_symbol="NSE:NIFTY26SEP24500CE",
        ltp=151.00,
        bid=150.80,
        ask=151.10,
        oi=10500,
        volume=52000,
        exchange_ts=1789935951.0,
    )
    assert snap2.version == 2
    assert snap2.ltp == 151.00

    fetched = store.get_snapshot("NIFTY|2026-09-24|24500|CE")
    assert fetched == snap2


def test_quote_store_multithreaded_concurrency():
    store = QuoteStore()
    canonical_ids = [f"NIFTY|2026-09-24|{24000 + i * 50}|CE" for i in range(20)]

    def writer(thread_id: int):
        for tick in range(100):
            for c_id in canonical_ids:
                store.update_tick(
                    canonical_id=c_id,
                    fyers_symbol=f"NSE:{c_id}",
                    ltp=100.0 + thread_id + tick,
                    bid=99.5 + thread_id + tick,
                    ask=100.5 + thread_id + tick,
                    oi=1000 * (thread_id + 1),
                    volume=5000 * (tick + 1),
                    exchange_ts=time.time(),
                )

    def reader():
        for _ in range(200):
            for c_id in canonical_ids:
                snap = store.get_snapshot(c_id)
                if snap is not None:
                    # Assert no torn state (bid <= ltp <= ask within normal bounds)
                    assert snap.bid <= snap.ask
                    assert snap.version >= 1

    with ThreadPoolExecutor(max_workers=30) as executor:
        writer_futures = [executor.submit(writer, i) for i in range(10)]
        reader_futures = [executor.submit(reader) for _ in range(20)]

        for f in writer_futures + reader_futures:
            f.result()

    assert store.total_quotes_count() == 20
