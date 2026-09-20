"""
Unit tests for Exit Model realism: trigger condition evaluated against LTP,
fill executed strictly at validated Bid.
"""
from datetime import datetime
import time
import pytest

from src.market_data.audit_record import AuditLogger
from src.market_data.quote_store import QuoteSnapshot
from src.simulator.paper_trader import PaperTrader


def test_exit_trigger_vs_bid_fill(tmp_path):
    audit_logger = AuditLogger(log_dir=tmp_path)
    trader = PaperTrader(
        initial_capital=1000000,
        slippage_pct=0.0,
        lot_size=65,
        audit_logger=audit_logger,
        enable_wallets=True,
    )

    entry_quote = QuoteSnapshot(
        canonical_id="NIFTY|2026-09-24|24500|CE",
        fyers_symbol="NSE:NIFTY26SEP24500CE",
        ltp=200.0,
        bid=199.5,
        ask=200.5,
        open_interest=10000,
        volume=50000,
        exchange_timestamp=time.time(),
        receive_epoch_timestamp=time.time(),
        receive_monotonic_timestamp=time.monotonic(),
        version=1,
    )

    order = trader.place_order(
        symbol="NIFTY24500CE",
        side="BUY",
        qty=1,
        price=200.5,
        stop_loss=190.0,  # SL trigger at 190.0
        take_profit=250.0,
        strategy="NIFTY_EMA_CROSSOVER",
        lot_size=65,
        canonical_instrument_id="NIFTY|2026-09-24|24500|CE",
        fyers_symbol="NSE:NIFTY26SEP24500CE",
        quote_snapshot=entry_quote,
    )

    assert order.status == "OPEN"
    assert order.entry_price == 200.5

    # Simulated sudden market drop:
    # Quote tick: LTP = 188.0 (crosses SL=190.0), but executable Bid = 178.0
    exit_quote = QuoteSnapshot(
        canonical_id="NIFTY|2026-09-24|24500|CE",
        fyers_symbol="NSE:NIFTY26SEP24500CE",
        ltp=188.0,
        bid=178.0,
        ask=188.5,
        open_interest=12000,
        volume=60000,
        exchange_timestamp=time.time(),
        receive_epoch_timestamp=time.time(),
        receive_monotonic_timestamp=time.monotonic(),
        version=2,
    )

    closed = trader.update_positions(
        current_prices={"NIFTY|2026-09-24|24500|CE": exit_quote},
        timestamp=datetime.now(),
    )

    assert len(closed) == 1
    closed_order = closed[0]
    assert closed_order.status == "CLOSED"
    assert closed_order.exit_reason == "STOP_LOSS"
    # Crucial assertion: fill executed at actual market Bid (178.0), NOT at the trigger price (190.0)!
    assert closed_order.exit_price == 178.0

    # Verify audit record for SELL fill
    records = audit_logger.get_records()
    assert len(records) == 2  # 1 BUY entry + 1 SELL exit
    exit_rec = records[1]
    assert exit_rec.side == "SELL"
    assert exit_rec.status == "FILLED"
    assert exit_rec.execution_price == 178.0
    assert exit_rec.bid == 178.0
    assert exit_rec.ltp == 188.0
