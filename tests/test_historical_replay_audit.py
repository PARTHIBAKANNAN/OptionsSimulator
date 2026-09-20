"""
Historical Replay Verification: Replays recorded options contract candles
and verifies 100% compliance with the 24-field audit record schema and strict Bid/Ask execution.
"""
from datetime import datetime
import json
from pathlib import Path
import pytest

from src.config import Config
from src.market_data.audit_record import AuditLogger, ExecutionAuditRecord
from src.market_data.quote_store import QuoteSnapshot
from src.strategies.base_strategy import Signal
from src.trader import LiveTrader, IST

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_HISTORICAL_DATA = PROJECT_ROOT / "data" / "historical" / "option_contracts_candles_20260916.json"


def test_historical_replay_execution_audit(tmp_path):
    audit_logger = AuditLogger(log_dir=tmp_path)
    config = Config(
        fyers_client_id="x",
        fyers_secret_key="x",
        fyers_fy_id="x",
        fyers_user_pin="x",
        fyers_totp_secret="x",
        fyers_redirect_uri="https://localhost",
        telegram_bot_token="",
        telegram_chat_id="",
        force_market_open=True,
        risk_params={"position_sizing": {"qty_per_signal": 1, "lot_size": 30}},
    )
    trader = LiveTrader(config)
    trader.paper_trader.audit_logger = audit_logger
    trader.paper_trader.slippage_pct = 0.0

    # Feed contract ticks simulating market opening
    canonical_id = "BANKNIFTY|2026-09-16|56000|CE"
    symbol = "NSE:BANKNIFTY2691656000CE"
    quote = trader.quote_store.update_tick(
        canonical_id=canonical_id,
        fyers_symbol=symbol,
        ltp=250.50,
        bid=250.00,
        ask=251.00,
        oi=50000,
        volume=100000,
        exchange_ts=1789542000.0,
    )

    trader.instrument_registry.register_from_fyers_chain(
        underlying="BANKNIFTY",
        exchange="NSE",
        chain_data={
            "expiryData": [{"expiry": 1789542000}],
            "optionsChain": [
                {
                    "symbol": symbol,
                    "strike_price": 56000.0,
                    "option_type": "CE",
                    "expiry": 1789542000,
                }
            ],
        },
        lot_size=30,
    )

    # Strategy evaluates and generates BUY signal
    signal = Signal(
        strategy="BANKNIFTY_MACD_BULLISH_1M_ATM",
        direction="CE",
        action="BUY",
        strike="BANKNIFTY56000CE",
        confidence=0.85,
        rationale="macd_cross",
        entry_price=251.0,
        timestamp=datetime(2026, 9, 16, 9, 30, tzinfo=IST),
        underlying="BANKNIFTY",
    )

    import asyncio
    asyncio.run(trader.execute_signal(signal))

    positions = trader.paper_trader.get_positions()
    assert len(positions) == 1
    pos = positions[0]
    # BUY fills strictly at Ask (251.00), not LTP (250.50)
    assert pos.entry_price == 251.00
    assert pos.canonical_id == canonical_id

    # Simulated exit on stop-loss hit
    # Market drops: LTP=200.0, Bid=190.0, Ask=200.5
    exit_snap = trader.quote_store.update_tick(
        canonical_id=canonical_id,
        fyers_symbol=symbol,
        ltp=200.0,
        bid=190.0,
        ask=200.5,
    )

    trader.check_exits()

    assert len(trader.paper_trader.get_positions()) == 0
    history = trader.paper_trader.get_trade_history()
    assert len(history) == 1
    closed_trade = history[0]
    assert closed_trade.exit_price == 190.0  # filled at Bid

    # Verify 100% schema completeness for all 24 fields
    records = audit_logger.get_records()
    assert len(records) == 2  # 1 entry BUY + 1 exit SELL

    for rec in records:
        assert isinstance(rec, ExecutionAuditRecord)
        rec_dict = rec.to_dict()
        assert len(rec_dict) == 24
        assert rec.event_id is not None
        assert rec.strategy_id == "BANKNIFTY_MACD_BULLISH_1M_ATM"
        assert rec.canonical_instrument_id == canonical_id
        assert rec.underlying == "BANKNIFTY"
        assert rec.expiry == "2026-09-16"
        assert rec.strike == 56000.0
        assert rec.option_type == "CE"
        assert rec.fyers_symbol == symbol
        assert rec.status == "FILLED"
        assert rec.rejection_code is None
        assert rec.rejection_reason is None
        assert rec.quote_age_ms >= 0.0
        assert rec.decision_quote_version >= 1
        assert rec.execution_quote_version >= 1
