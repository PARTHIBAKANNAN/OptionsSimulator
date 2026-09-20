"""
Unit tests for strict Bid/Ask paper execution and 24-field ExecutionAuditRecord.
"""
from datetime import datetime
import time
import pytest

from src.market_data.audit_record import AuditLogger, ExecutionAuditRecord
from src.market_data.quote_store import QuoteSnapshot
from src.simulator.paper_trader import Order, PaperTrader, RiskLimitExceeded


def test_paper_trader_bid_ask_execution(tmp_path):
    audit_logger = AuditLogger(log_dir=tmp_path)
    trader = PaperTrader(
        initial_capital=1000000,
        slippage_pct=0.0,  # zero slippage to test exact price fill
        lot_size=65,
        audit_logger=audit_logger,
        enable_wallets=True,
    )

    quote = QuoteSnapshot(
        canonical_id="NIFTY|2026-09-24|24500|CE",
        fyers_symbol="NSE:NIFTY26SEP24500CE",
        ltp=150.25,
        bid=150.00,
        ask=150.50,
        open_interest=10000,
        volume=50000,
        exchange_timestamp=time.time(),
        receive_epoch_timestamp=time.time(),
        receive_monotonic_timestamp=time.monotonic(),
        version=3,
    )

    # Place BUY order with price = quote.ask (150.50)
    order = trader.place_order(
        symbol="NIFTY24500CE",
        side="BUY",
        qty=1,
        price=quote.ask,
        stop_loss=120.0,
        take_profit=200.0,
        strategy="NIFTY_EMA_CROSSOVER",
        timestamp=datetime.now(),
        lot_size=65,
        canonical_instrument_id=quote.canonical_id,
        fyers_symbol=quote.fyers_symbol,
        quote_snapshot=quote,
        decision_quote_version=3,
        execution_quote_version=3,
    )

    assert order.entry_price == 150.50
    assert order.status == "OPEN"
    assert order.canonical_id == "NIFTY|2026-09-24|24500|CE"
    assert order.fyers_symbol == "NSE:NIFTY26SEP24500CE"

    # Verify audit record
    records = audit_logger.get_records()
    assert len(records) == 1
    rec = records[0]
    assert isinstance(rec, ExecutionAuditRecord)
    assert rec.status == "FILLED"
    assert rec.strategy_id == "NIFTY_EMA_CROSSOVER"
    assert rec.canonical_instrument_id == "NIFTY|2026-09-24|24500|CE"
    assert rec.underlying == "NIFTY"
    assert rec.expiry == "2026-09-24"
    assert rec.strike == 24500.0
    assert rec.option_type == "CE"
    assert rec.fyers_symbol == "NSE:NIFTY26SEP24500CE"
    assert rec.side == "BUY"
    assert rec.quantity == 1
    assert rec.ltp == 150.25
    assert rec.bid == 150.00
    assert rec.ask == 150.50
    assert rec.decision_quote_version == 3
    assert rec.execution_quote_version == 3
    assert rec.execution_price == 150.50
    assert rec.rejection_code is None


def test_paper_trader_rejection_audit_record(tmp_path):
    audit_logger = AuditLogger(log_dir=tmp_path)
    trader = PaperTrader(
        initial_capital=1000000,
        min_entry_premium=200.0,  # floor of 200.0
        audit_logger=audit_logger,
        enable_wallets=True,
    )

    # Attempt to place order below minimum floor (150.0 < 200.0)
    with pytest.raises(RiskLimitExceeded):
        trader.place_order(
            symbol="NIFTY24500CE",
            side="BUY",
            qty=1,
            price=150.0,
            strategy="NIFTY_EMA_CROSSOVER",
            lot_size=65,
            canonical_instrument_id="NIFTY|2026-09-24|24500|CE",
            fyers_symbol="NSE:NIFTY26SEP24500CE",
        )

    records = audit_logger.get_records()
    assert len(records) == 1
    rec = records[0]
    assert rec.status == "REJECTED"
    assert rec.rejection_code == "REJECTED_MIN_PREMIUM_FLOOR"
    assert rec.execution_price is None
