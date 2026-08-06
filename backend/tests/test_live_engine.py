"""
Regression test for a real freeze bug: _check_exits_replay() didn't pass the simulated candle
timestamp to PaperTrader.update_positions(), so it defaulted to tz-naive datetime.now(). The
moment a position was open long enough to check its time-exit condition against its tz-aware
entry_time (from the replayed CSV), that raised TypeError — uncaught, this silently killed the
entire replay loop forever after exactly one trade. See docs/ARCHITECTURE.md.
"""
import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytz

from backend.app.live_engine import WebLiveEngine
from backend.app.state import pending_signals, shared_state
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


# ---- strategy_status_list: quantman-style per-strategy waiting/entered summary ----------------

def test_strategy_status_list_reports_waiting_for_every_registered_strategy_with_no_positions():
    engine = _make_engine()
    rows = engine._strategy_status_list(current_prices={})

    assert len(rows) == len(engine.strategy_engine.strategies)
    assert {r["strategy"] for r in rows} == {s.name for s in engine.strategy_engine.strategies}
    for row in rows:
        assert row["status"] == "WAITING"
        assert row["entry"] is None
        assert row["today_pnl"] == 0.0


def test_strategy_status_list_reports_signal_entered_with_contract_entry_ltp_and_pnl():
    engine = _make_engine()
    entry_time = IST.localize(datetime(2026, 8, 4, 10, 0))  # 2026-08-04 is a Tuesday (expiry day)
    engine.paper_trader.place_order(
        symbol="NIFTY24600CE", side="BUY", qty=1, price=200.0,
        stop_loss=160.0, take_profit=350.0, strategy="MACD_BULLISH", timestamp=entry_time,
    )

    rows = engine._strategy_status_list(current_prices={"NIFTY24600CE": 250.0})
    row = next(r for r in rows if r["strategy"] == "MACD_BULLISH")

    assert row["status"] == "SIGNAL_ENTERED"
    assert row["entry"]["contract"] == "NIFTY04Aug202624600CE"
    assert row["entry"]["ltp"] == 250.0
    assert row["entry"]["trade_pnl"] == pytest.approx((250.0 - row["entry"]["entry_price"]) * engine.paper_trader.lot_size)
    assert row["today_pnl"] == pytest.approx(row["entry"]["trade_pnl"])

    # every other strategy is untouched and still waiting
    others = [r for r in rows if r["strategy"] != "MACD_BULLISH"]
    assert all(r["status"] == "WAITING" for r in others)


def test_strategy_status_list_includes_realized_pnl_from_trades_closed_today():
    engine = _make_engine()
    # "today" in _strategy_status_list is real wall-clock IST, not a fixed historical date — the
    # closed trade must actually fall on today's date for the filter to pick it up.
    entry_time = datetime.now(IST)
    order = engine.paper_trader.place_order(
        symbol="NIFTY24600CE", side="BUY", qty=1, price=200.0,
        strategy="MACD_BULLISH", timestamp=entry_time,
    )
    engine.paper_trader.close_position(order.order_id, 230.0, timestamp=entry_time + timedelta(minutes=30))

    rows = engine._strategy_status_list(current_prices={})
    row = next(r for r in rows if r["strategy"] == "MACD_BULLISH")

    assert row["status"] == "WAITING"  # no longer open
    assert row["today_pnl"] == pytest.approx((230.0 - order.entry_price) * engine.paper_trader.lot_size)


def test_strategy_status_list_surfaces_last_closed_today_when_flat():
    # Item D: the expand affordance must stay available after a signal closes for the day, not
    # just while it's open -- the frontend needs somewhere to read that last signal's details from.
    engine = _make_engine()
    entry_time = datetime.now(IST)
    order = engine.paper_trader.place_order(
        symbol="NIFTY24600CE", side="BUY", qty=1, price=200.0, stop_loss=160.0, take_profit=350.0,
        strategy="MACD_BULLISH", timestamp=entry_time,
    )
    engine.paper_trader.close_position(order.order_id, 230.0, timestamp=entry_time + timedelta(minutes=30),
                                        reason="TAKE_PROFIT")

    rows = engine._strategy_status_list(current_prices={})
    row = next(r for r in rows if r["strategy"] == "MACD_BULLISH")

    assert row["entry"] is None
    assert row["last_closed_today"]["contract"].startswith("NIFTY")
    assert row["last_closed_today"]["exit_reason"] == "TAKE_PROFIT"
    assert row["last_closed_today"]["exit_price"] == 230.0
    assert row["last_closed_today"]["stop_loss"] == 160.0
    assert row["last_closed_today"]["take_profit"] == 350.0


def test_strategy_status_list_entry_includes_time_and_sl_tp():
    engine = _make_engine()
    entry_time = datetime.now(IST)
    engine.paper_trader.place_order(
        symbol="NIFTY24600CE", side="BUY", qty=1, price=200.0, stop_loss=160.0, take_profit=350.0,
        strategy="MACD_BULLISH", timestamp=entry_time,
    )

    rows = engine._strategy_status_list(current_prices={"NIFTY24600CE": 210.0})
    row = next(r for r in rows if r["strategy"] == "MACD_BULLISH")

    assert row["entry"]["entry_time"] == entry_time.isoformat()
    assert row["entry"]["stop_loss"] == 160.0
    assert row["entry"]["take_profit"] == 350.0
    assert row["last_closed_today"] is None


# ---- Restore-on-boot: wallets and orphaned open positions survive a restart -------------------

@pytest.mark.asyncio
async def test_restore_state_does_nothing_without_a_configured_db():
    engine = _make_engine(data_engine_enabled=True)
    with patch("backend.app.live_engine.db.get_pool", side_effect=RuntimeError):
        await engine._restore_state()  # must not raise
    assert engine.paper_trader.get_positions() == []


@pytest.mark.asyncio
async def test_restore_state_loads_wallet_balance_and_reopens_orphaned_positions():
    engine = _make_engine(data_engine_enabled=True)
    # Simulate what capital_by_strategy would have seeded before the (simulated) restart.
    engine.paper_trader.wallet_balance["MACD_BULLISH"] = 85000.0

    fake_pool = MagicMock()
    fake_pool.fetch = AsyncMock(side_effect=[
        [{"strategy": "MACD_BULLISH", "balance": 78000.0}],
        [{
            "order_id": "abc-123", "symbol": "NIFTY24500CE", "side": "BUY", "qty": 1,
            "lot_size": 65, "entry_price": 100.0,
            "entry_time": pytz.utc.localize(datetime(2026, 8, 5, 9, 20)),
            "stop_loss": 80.0, "take_profit": 150.0, "strategy": "MACD_BULLISH", "entry_charges": 25.0,
        }],
    ])

    with patch("backend.app.live_engine.db.get_pool", return_value=fake_pool):
        await engine._restore_state()

    assert engine.paper_trader.wallet_balance["MACD_BULLISH"] == 78000.0
    positions = engine.paper_trader.get_positions()
    assert len(positions) == 1
    assert positions[0].order_id == "abc-123"
    assert positions[0].entry_charges == 25.0
    assert positions[0].status == "OPEN"


@pytest.mark.asyncio
async def test_restore_state_ignores_wallet_rows_for_unseeded_strategies():
    # A strategy with no capital_by_strategy entry has no wallet at all (see PaperTrader) -- a
    # stale DB row for it must not create one out of nowhere.
    engine = _make_engine(data_engine_enabled=True)
    fake_pool = MagicMock()
    fake_pool.fetch = AsyncMock(side_effect=[
        [{"strategy": "SOME_OLD_STRATEGY", "balance": 1000.0}],
        [],
    ])
    with patch("backend.app.live_engine.db.get_pool", return_value=fake_pool):
        await engine._restore_state()
    assert "SOME_OLD_STRATEGY" not in engine.paper_trader.wallet_balance


@pytest.mark.asyncio
async def test_restore_state_only_queries_positions_opened_today():
    # Regression: an unscoped "WHERE status = 'OPEN'" resurrected 11 never-closed positions left
    # over from replay-mode test runs (entry_time values from May-July, replayed CSV dates) as if
    # they were live open positions, on every restart -- 13 phantom positions exceeded
    # max_concurrent_positions and silently blocked every real signal from firing at all. The
    # query must filter to today (IST) so old test/crash artifacts are never restored.
    engine = _make_engine(data_engine_enabled=True)
    fake_pool = MagicMock()
    fake_pool.fetch = AsyncMock(side_effect=[[], []])

    with patch("backend.app.live_engine.db.get_pool", return_value=fake_pool):
        with patch("backend.app.live_engine.datetime") as mock_dt:
            mock_dt.now.return_value = IST.localize(datetime(2026, 8, 6, 9, 0))
            await engine._restore_state()

    positions_query, today_param = fake_pool.fetch.call_args_list[1].args
    assert "entry_time AT TIME ZONE" in positions_query
    assert today_param == date(2026, 8, 6)


@pytest.mark.asyncio
async def test_db_execute_is_a_noop_in_replay_mode():
    # Replay mode must never write to the same Postgres table live trading uses -- this exact gap
    # is what let 11 replay-test orders pollute options_positions in the first place.
    engine = _make_engine(data_engine_enabled=False)
    with patch("backend.app.live_engine.db.get_pool") as mock_get_pool:
        await engine._db_execute("INSERT INTO options_positions (order_id) VALUES ($1)", "x")
    mock_get_pool.assert_not_called()


@pytest.mark.asyncio
async def test_db_execute_writes_in_live_mode():
    engine = _make_engine(data_engine_enabled=True)
    fake_pool = MagicMock()
    fake_pool.execute = AsyncMock()
    with patch("backend.app.live_engine.db.get_pool", return_value=fake_pool):
        await engine._db_execute("INSERT INTO options_positions (order_id) VALUES ($1)", "x")
    fake_pool.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_wallet_db_upserts_current_balance_for_seeded_strategies():
    engine = _make_engine(data_engine_enabled=True)
    engine.paper_trader.wallet_balance["MACD_BULLISH"] = 12345.67
    engine.paper_trader.capital_by_strategy["MACD_BULLISH"] = 85000.0
    engine._db_execute = AsyncMock()

    await engine._save_wallet_db("MACD_BULLISH")

    engine._db_execute.assert_awaited_once()
    query, strategy, balance, allocated = engine._db_execute.call_args.args
    assert "options_wallets" in query
    assert (strategy, balance, allocated) == ("MACD_BULLISH", 12345.67, 85000.0)


@pytest.mark.asyncio
async def test_save_wallet_db_is_a_noop_for_strategies_without_a_wallet():
    engine = _make_engine(data_engine_enabled=True)
    engine._db_execute = AsyncMock()

    await engine._save_wallet_db("NO_WALLET_STRATEGY")

    engine._db_execute.assert_not_awaited()


# ---- Keep publishing state while the market is closed (fixes the "dashes/stopped" bug) --------

def test_on_market_closed_tick_still_publishes_every_strategy_as_waiting():
    engine = _make_engine(data_engine_enabled=True)
    engine._on_market_closed_tick()

    state = shared_state.get()
    assert len(state["strategy_status"]) == len(engine.strategy_engine.strategies)
    assert all(row["status"] == "WAITING" for row in state["strategy_status"])


# ---- NIFTY header: prev close / change / % / sparkline / real exchange-hours state ------------

def test_publish_state_computes_nifty_change_and_pct_from_prev_close():
    engine = _make_engine(data_engine_enabled=True)
    engine.data_manager.replay_candle(Candle(timestamp=datetime(2026, 8, 4, 15, 29), open=24000,
                                              high=24005, low=23995, close=24000, volume=1000))
    engine.data_manager.replay_candle(Candle(timestamp=datetime(2026, 8, 5, 9, 15), open=24000,
                                              high=24130, low=23990, close=24120, volume=1000))

    with patch("backend.app.live_engine.datetime") as mock_dt:
        mock_dt.now.return_value = IST.localize(datetime(2026, 8, 5, 9, 20))
        engine._publish_state()

    state = shared_state.get()
    assert state["nifty_prev_close"] == 24000
    assert state["nifty_change"] == 120
    assert state["nifty_change_pct"] == 0.5
    assert state["nifty_sparkline"] == [24120]


def test_publish_state_exchange_open_true_when_force_market_open_regardless_of_wall_clock():
    engine = _make_engine(data_engine_enabled=True)
    engine.config.force_market_open = True
    engine._publish_state()
    assert shared_state.get()["exchange_open"] is True


def test_publish_state_exchange_open_reflects_real_market_hours():
    engine = _make_engine(data_engine_enabled=True)
    with patch("backend.app.live_engine.datetime") as mock_dt:
        mock_dt.now.return_value = IST.localize(datetime(2026, 8, 4, 12, 0))  # Tuesday, midday
        engine._publish_state()
    assert shared_state.get()["exchange_open"] is True

    with patch("backend.app.live_engine.datetime") as mock_dt:
        mock_dt.now.return_value = IST.localize(datetime(2026, 8, 4, 20, 0))  # well after close
        engine._publish_state()
    assert shared_state.get()["exchange_open"] is False
