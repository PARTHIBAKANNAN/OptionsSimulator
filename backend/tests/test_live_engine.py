"""
Regression test for a real freeze bug: _check_exits_replay() didn't pass the simulated candle
timestamp to PaperTrader.update_positions(), so it defaulted to tz-naive datetime.now(). The
moment a position was open long enough to check its time-exit condition against its tz-aware
entry_time (from the replayed CSV), that raised TypeError — uncaught, this silently killed the
entire replay loop forever after exactly one trade. See docs/ARCHITECTURE.md.
"""
from datetime import datetime, timedelta

import pytest
import pytz

from backend.app.live_engine import WebLiveEngine
from src.config import Config
from src.data_manager import Candle

IST = pytz.timezone("Asia/Kolkata")


def _make_engine() -> WebLiveEngine:
    config = Config(
        fyers_client_id="x", fyers_secret_key="x", fyers_fy_id="x", fyers_user_pin="x",
        fyers_totp_secret="x", fyers_redirect_uri="https://example.com/callback",
        telegram_bot_token="", telegram_chat_id="", force_market_open=False,
        risk_params={
            "position_sizing": {"qty_per_signal": 1, "lot_size": 75, "max_concurrent_positions": 5, "max_daily_loss": 5000},
            "exit_rules": {"stop_loss_pts": 50, "take_profit_pts": 150, "time_exit_mins": 120},
            "polling": {"option_chain_interval_secs": 10},
        },
    )
    return WebLiveEngine(config, data_engine_enabled=False)


@pytest.mark.asyncio
async def test_check_exits_replay_closes_a_time_expired_position_without_raising():
    engine = _make_engine()

    entry_time = IST.localize(datetime(2026, 5, 8, 9, 15))  # tz-aware, matching real CSV data
    order = engine.paper_trader.place_order(
        symbol="NIFTY24200PE", side="BUY", qty=1, price=160.0,
        stop_loss=110.0, take_profit=310.0, strategy="TEST", timestamp=entry_time,
    )
    assert order.status == "OPEN"

    # Feed a candle far enough past entry_time to trigger the 120-min time exit — this is the
    # exact scenario that used to raise TypeError and kill the whole replay loop.
    later = entry_time + timedelta(minutes=130)
    candle = Candle(timestamp=later, open=24200, high=24210, low=24190, close=24200, volume=1000)
    engine.data_manager.replay_candle(candle)

    engine._check_exits_replay()  # must not raise

    closed = engine.paper_trader.get_trade_history()
    assert len(closed) == 1
    assert closed[0].exit_reason == "TIME_EXIT"


@pytest.mark.asyncio
async def test_check_exits_replay_leaves_position_open_before_time_exit():
    engine = _make_engine()

    entry_time = IST.localize(datetime(2026, 5, 8, 9, 15))
    engine.paper_trader.place_order(
        symbol="NIFTY24200PE", side="BUY", qty=1, price=160.0,
        stop_loss=110.0, take_profit=310.0, strategy="TEST", timestamp=entry_time,
    )

    soon = entry_time + timedelta(minutes=5)
    candle = Candle(timestamp=soon, open=24200, high=24210, low=24190, close=24200, volume=1000)
    engine.data_manager.replay_candle(candle)

    engine._check_exits_replay()

    assert len(engine.paper_trader.get_positions()) == 1
    assert len(engine.paper_trader.get_trade_history()) == 0
