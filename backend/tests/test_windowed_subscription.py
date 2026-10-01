"""
Windowed WebSocket subscription (single free-tier Fyers socket). The live feed must carry only
the 3 indices, ATM +/- N strikes, open positions, and short-lived JIT entry pins -- NOT the full
~549-symbol chain that starved individual contracts (197 REJECTED_STALE_QUOTE / 42 signals on
2026-10-01). OI/discovery still comes from the full REST option-chain poll. See
NUKEBOX_REMEDIATION_PLAN.md Issues 2 & 3.
"""
from datetime import date
from unittest.mock import MagicMock

from backend.app.live_engine import WebLiveEngine
from src.config import Config
from src.market_data.instrument_registry import Instrument
from src.trader import INDEX_SYMBOLS


def _make_engine(window: int = 10) -> WebLiveEngine:
    config = Config(
        fyers_client_id="x", fyers_secret_key="x", fyers_fy_id="x", fyers_user_pin="x",
        fyers_totp_secret="x", fyers_redirect_uri="https://example.com/callback",
        telegram_bot_token="", telegram_chat_id="", force_market_open=False,
        risk_params={
            "position_sizing": {"qty_per_signal": 1, "lot_size": 75, "max_concurrent_positions": 5,
                                 "max_daily_loss": 5000},
            "exit_rules": {"stop_loss_pct": 20, "take_profit_pts": 150, "time_exit_mins": 120},
            "polling": {"option_chain_interval_secs": 10, "atm_window_strikes": window},
        },
    )
    return WebLiveEngine(config, data_engine_enabled=True)


def _register_nifty_chain(engine, lo: int = 22000, hi: int = 23100, step: int = 50) -> None:
    for strike in range(lo, hi + 1, step):
        for ot in ("CE", "PE"):
            inst = Instrument(
                underlying="NIFTY", expiry=date(2026, 10, 6), strike=float(strike),
                option_type=ot, exchange="NSE",
                fyers_symbol=f"NSE:NIFTY26O06{strike}{ot}", lot_size=65,
            )
            engine.instrument_registry._by_canonical_id[inst.canonical_id] = inst


def test_window_config_is_read():
    assert _make_engine(window=10).atm_window_strikes == 10
    assert _make_engine(window=6).atm_window_strikes == 6


def test_desired_ws_symbols_windows_around_atm():
    engine = _make_engine(window=10)
    _register_nifty_chain(engine)
    engine.data_managers["NIFTY"]._live_ltp = 22550.0  # ATM = 22550, window = [22050, 23050]

    desired = engine._desired_ws_symbols()

    for sym in INDEX_SYMBOLS.values():
        assert sym in desired, "all 3 indices must always be on the feed"
    assert "NSE:NIFTY26O0622550CE" in desired   # ATM
    assert "NSE:NIFTY26O0622050PE" in desired    # lower edge (ATM - 10*50)
    assert "NSE:NIFTY26O0623050CE" in desired    # upper edge (ATM + 10*50)
    assert "NSE:NIFTY26O0622000CE" not in desired  # below window
    assert "NSE:NIFTY26O0623100PE" not in desired  # above window


def test_smaller_window_subscribes_fewer_symbols():
    big = _make_engine(window=10)
    small = _make_engine(window=6)
    for e in (big, small):
        _register_nifty_chain(e)
        e.data_managers["NIFTY"]._live_ltp = 22550.0
    assert len(big._desired_ws_symbols()) > len(small._desired_ws_symbols())


def test_open_position_outside_window_is_always_kept():
    engine = _make_engine(window=10)
    _register_nifty_chain(engine)
    engine.data_managers["NIFTY"]._live_ltp = 22550.0
    engine.paper_trader.place_order(
        symbol="NIFTY21000CE", side="BUY", qty=1, price=1555.0,
        stop_loss=1200.0, take_profit=1800.0, strategy="TEST",
        fyers_symbol="NSE:NIFTY26O0621000CE",
    )
    desired = engine._desired_ws_symbols()
    assert "NSE:NIFTY26O0621000CE" in desired, "open positions must never be pruned off the feed"


def test_sync_subscriptions_adds_then_prunes_as_spot_moves():
    engine = _make_engine(window=10)
    _register_nifty_chain(engine)
    engine.data_managers["NIFTY"]._live_ltp = 22550.0
    engine.fyers = MagicMock()
    engine._connected = True

    engine._sync_subscriptions()
    subbed = set().union(*(set(c.args[0]) for c in engine.fyers.subscribe_symbols.call_args_list))
    assert "NSE:NIFTY26O0622550CE" in subbed
    assert "NSE:NIFTY26O0622550CE" in engine._monitored_symbols
    # the whole chain is NOT dumped onto the socket
    assert "NSE:NIFTY26O0622000CE" not in engine._monitored_symbols

    # spot drops a lot -> old upper-edge strike falls out and must be unsubscribed
    engine.data_managers["NIFTY"]._live_ltp = 22000.0  # new window [21500, 22500]
    engine._sync_subscriptions()
    unsubbed = set().union(*(set(c.args[0]) for c in engine.fyers.unsubscribe_symbols.call_args_list)) \
        if engine.fyers.unsubscribe_symbols.call_args_list else set()
    assert "NSE:NIFTY26O0623050CE" in unsubbed
    assert "NSE:NIFTY26O0623050CE" not in engine._monitored_symbols


def test_sync_noop_when_not_connected():
    engine = _make_engine(window=10)
    _register_nifty_chain(engine)
    engine.data_managers["NIFTY"]._live_ltp = 22550.0
    engine.fyers = MagicMock()
    engine._connected = False
    engine._sync_subscriptions()
    engine.fyers.subscribe_symbols.assert_not_called()
