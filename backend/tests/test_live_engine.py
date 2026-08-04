"""
Regression test for a real freeze bug: _check_exits_replay() didn't pass the simulated candle
timestamp to PaperTrader.update_positions(), so it defaulted to tz-naive datetime.now(). The
moment a position was open long enough to check its time-exit condition against its tz-aware
entry_time (from the replayed CSV), that raised TypeError — uncaught, this silently killed the
entire replay loop forever after exactly one trade. See docs/ARCHITECTURE.md.
"""
import asyncio
from datetime import datetime, timedelta

import pytest
import pytz

from backend.app.live_engine import WebLiveEngine
from backend.app.state import pending_signals
from src.config import Config
from src.data_manager import Candle
from src.strategies.base_strategy import Signal

IST = pytz.timezone("Asia/Kolkata")


def _make_engine(data_engine_enabled: bool = False, extra_risk_params: dict = None) -> WebLiveEngine:
    risk_params = {
        "position_sizing": {"qty_per_signal": 1, "lot_size": 75, "max_concurrent_positions": 5, "max_daily_loss": 5000},
        "exit_rules": {"stop_loss_pct": 20, "take_profit_pts": 150, "time_exit_mins": 120},
        "polling": {"option_chain_interval_secs": 10},
    }
    if extra_risk_params:
        risk_params.update(extra_risk_params)
    config = Config(
        fyers_client_id="x", fyers_secret_key="x", fyers_fy_id="x", fyers_user_pin="x",
        fyers_totp_secret="x", fyers_redirect_uri="https://example.com/callback",
        telegram_bot_token="", telegram_chat_id="", force_market_open=False,
        risk_params=risk_params,
    )
    return WebLiveEngine(config, data_engine_enabled=data_engine_enabled)


def _make_signal(strategy: str = "TEST") -> Signal:
    return Signal(
        strategy=strategy, direction="CE", action="BUY", strike="NIFTY24500CE",
        confidence=0.75, rationale="test", entry_price=100.0,
        timestamp=IST.localize(datetime(2026, 5, 8, 10, 0)),
    )


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


@pytest.mark.asyncio
async def test_auto_mode_defaults_to_true_and_auto_approves_live_signals():
    # data_engine_enabled=True (live data) with no "live_mode" key at all in risk_params ->
    # auto_approve must default to True (see src/trader.py LiveTrader.__init__).
    engine = _make_engine(data_engine_enabled=True)
    assert engine.auto_mode is True

    signal = _make_signal()
    await engine.execute_signal(signal)

    positions = engine.paper_trader.get_positions()
    assert len(positions) == 1
    assert positions[0].strategy == "TEST"
    # Never registered as a pending approval -- it was auto-approved immediately.
    assert pending_signals.list_pending() == []


@pytest.mark.asyncio
async def test_auto_mode_false_falls_back_to_manual_approval_path():
    engine = _make_engine(data_engine_enabled=True, extra_risk_params={"live_mode": {"auto_approve": False}})
    assert engine.auto_mode is False

    signal = _make_signal(strategy="MANUAL_TEST")
    task = asyncio.create_task(engine.execute_signal(signal))
    await asyncio.sleep(0.05)  # let it register as pending before we inspect/resolve it

    pending = pending_signals.list_pending()
    assert len(pending) == 1
    assert pending[0]["strategy"] == "MANUAL_TEST"
    assert engine.paper_trader.get_positions() == []  # not placed yet -- still awaiting approval

    signal_id = pending[0]["id"]
    pending_signals.resolve(signal_id, "approve")
    await task

    assert len(engine.paper_trader.get_positions()) == 1


@pytest.mark.asyncio
async def test_replay_mode_auto_approves_regardless_of_auto_mode_setting():
    engine = _make_engine(data_engine_enabled=False, extra_risk_params={"live_mode": {"auto_approve": False}})
    signal = _make_signal()
    await engine.execute_signal(signal)
    assert len(engine.paper_trader.get_positions()) == 1


def test_circuit_breaker_config_wired_into_live_engines_paper_trader():
    engine = _make_engine(extra_risk_params={
        "circuit_breaker": {
            "consecutive_loss_limit": 3, "consecutive_loss_cooldown_days": 1,
            "max_drawdown_pct_of_capital": 25, "drawdown_cooldown_days": 3,
            "drawdown_breaker_grace_trades": 3,
        },
    })
    trader = engine.paper_trader
    assert trader.consecutive_loss_limit == 3
    assert trader.consecutive_loss_cooldown_days == 1
    assert trader.max_drawdown_pct_of_capital == 25
    assert trader.drawdown_cooldown_days == 3
    assert trader.drawdown_breaker_grace_trades == 3


def test_circuit_breaker_disabled_by_default_when_no_config_section():
    engine = _make_engine()
    trader = engine.paper_trader
    assert trader.consecutive_loss_limit is None
    assert trader.max_drawdown_pct_of_capital is None
