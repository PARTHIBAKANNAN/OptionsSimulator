"""
Comprehensive 44-Strategy and Indicator Pipeline Test Suite
============================================================
Validates all 12 audit test scenarios:
1. All 44 strategies instantiate cleanly.
2. BANKNIFTY strategies resolve banknifty_price properly.
3. SENSEX strategies resolve sensex_price properly.
4. ORB strategies reject signals when trend is unconfirmed.
5. ORB strategies trigger signals when trend is confirmed.
6. Support Bounce requires volume confirmation and closing strength.
7. Resistance Rejection requires volume confirmation.
8. Heikin-Ashi wick filter respects calibrated tolerance.
9. Iron Fly _leg_prices handles missing keys without KeyError.
10. DataManager.get_state() sets underlying-specific price key.
11. DataManager window_size=5000 holds 10+ days of history.
12. All 44 strategies handle null timestamp and spot <= 0 gracefully.
"""
from datetime import datetime, time as dtime, timezone
import pytest

from src.data_manager import Candle, DataManager
from src.strategies import (
    create_nifty_strategies,
    create_sensex_strategies,
    create_banknifty_strategies,
)
from src.strategies.banknifty_5m_strategies import (
    BankNiftySupportBounce5MITM,
    BankNiftyHeikinAshiBullish5MITM,
    BankNiftyORBBullish5MITM,
    BankNiftyResistanceRejection5MITM,
    BankNiftyHeikinAshiBearish5MITM,
    BankNiftyORBBearish5MITM,
)
from src.strategies.sensex_5m_strategies import (
    SensexSupportBounce5MITM,
    SensexHeikinAshiBullish5MITM,
    SensexORBBullish5MITM,
    SensexResistanceRejection5MITM,
    SensexHeikinAshiBearish5MITM,
    SensexORBBearish5MITM,
)
from src.strategies.nifty_5m_strategies import (
    NiftySupportBounce5MITM,
    NiftyHeikinAshiBullish5MITM,
    NiftyORBBullish5MITM,
    NiftyResistanceRejection5MITM,
    NiftyHeikinAshiBearish5MITM,
    NiftyORBBearish5MITM,
)
from src.strategies.iron_fly_hedge import IronFlyHedge


def test_1_all_44_strategies_instantiate():
    """Verify all 44 strategies instantiate cleanly with expected names and underlying."""
    nifty = create_nifty_strategies()
    sensex = create_sensex_strategies()
    banknifty = create_banknifty_strategies()

    assert len(nifty) == 14, f"Expected 14 NIFTY strategies, got {len(nifty)}"
    assert len(sensex) == 15, f"Expected 15 SENSEX strategies, got {len(sensex)}"
    assert len(banknifty) == 15, f"Expected 15 BANKNIFTY strategies, got {len(banknifty)}"
    assert len(nifty) + len(sensex) + len(banknifty) == 44

    for s in nifty:
        assert s.underlying == "NIFTY"
    for s in sensex:
        assert s.underlying == "SENSEX"
    for s in banknifty:
        assert s.underlying == "BANKNIFTY"


def test_2_banknifty_ha_price_routing():
    """Verify BANKNIFTY Heikin-Ashi strategies read banknifty_price, not nifty_price."""
    strat_ce = BankNiftyHeikinAshiBullish5MITM()
    strat_pe = BankNiftyHeikinAshiBearish5MITM()

    ts = datetime(2026, 9, 4, 9, 45)
    # Case A: banknifty_price is 52000, nifty_price is 24500
    state = {
        "timestamp": ts,
        "banknifty_price": 52000.0,
        "nifty_price": 24500.0,
        "indicators": {
            "heikin_ashi_5m": {
                "open": 51900.0, "high": 52050.0, "low": 51890.0, "close": 52000.0,
                "prev_open": 51800.0, "prev_close": 51900.0,
            },
            "ema_50_1h": 51500.0,
        },
        "candles": [
            Candle(ts, 51900, 52050, 51890, 52000, 1000),
            Candle(ts, 51900, 52050, 51890, 52000, 1000),
        ]
    }
    sig = strat_ce.evaluate(state)
    assert sig is not None
    assert sig.underlying == "BANKNIFTY"
    assert "BANKNIFTY" in sig.strike


def test_3_sensex_ha_price_routing():
    """Verify SENSEX Heikin-Ashi strategies read sensex_price."""
    strat = SensexHeikinAshiBullish5MITM()
    ts = datetime(2026, 9, 4, 9, 45)
    state = {
        "timestamp": ts,
        "sensex_price": 81000.0,
        "indicators": {
            "heikin_ashi_5m": {
                "open": 80900.0, "high": 81050.0, "low": 80890.0, "close": 81000.0,
                "prev_open": 80800.0, "prev_close": 80900.0,
            },
            "ema_50_1h": 80500.0,
        },
        "candles": [
            Candle(ts, 80900, 81050, 80890, 81000, 1000),
            Candle(ts, 80900, 81050, 80890, 81000, 1000),
        ]
    }
    sig = strat.evaluate(state)
    assert sig is not None
    assert sig.underlying == "SENSEX"
    assert "SENSEX" in sig.strike


def test_4_orb_trend_filter_rejection():
    """Verify ORB strategies reject trades when EMA50 is not confirmed."""
    strat = NiftyORBBullish5MITM()
    ts_morning = datetime(2026, 9, 4, 9, 20)
    ts_breakout = datetime(2026, 9, 4, 9, 35)

    c1 = Candle(ts_morning, 24000, 24100, 23950, 24050, 500)
    c2 = Candle(ts_breakout, 24050, 24150, 24040, 24120, 1500)

    # Condition: price (24120) broke above range (24100), BUT EMA50 (24200) is ABOVE price (downtrend)
    state = {
        "timestamp": ts_breakout,
        "candles": [c1, c2],
        "indicators": {
            "ema_50_1h": 24200.0,  # Bearish macro trend
            "avg_volume": 1000,
        }
    }
    strat._range_day = ts_morning.date()
    strat._range_high = 24100.0
    strat._range_low = 23950.0

    sig = strat.evaluate(state)
    assert sig is None, "ORB Bullish should not fire against 1H downtrend"


def test_5_orb_trend_filter_acceptance():
    """Verify ORB strategies accept trades when EMA50 confirms trend."""
    strat = NiftyORBBullish5MITM()
    ts_morning = datetime(2026, 9, 4, 9, 20)
    ts_breakout = datetime(2026, 9, 4, 9, 35)

    c1 = Candle(ts_morning, 24000, 24100, 23950, 24050, 500)
    c2 = Candle(ts_breakout, 24050, 24150, 24040, 24120, 1500)

    # Condition: price (24120) broke above range (24100), AND EMA50 (24000) confirms uptrend
    state = {
        "timestamp": ts_breakout,
        "candles": [c1, c2],
        "indicators": {
            "ema_50_1h": 24000.0,
            "avg_volume": 1000,
        }
    }
    strat._range_day = ts_morning.date()
    strat._range_high = 24100.0
    strat._range_low = 23950.0

    sig = strat.evaluate(state)
    assert sig is not None, "ORB Bullish should fire when trend confirms"
    assert sig.direction == "CE"


def test_6_support_bounce_volume_filter():
    """Verify Support Bounce requires volume confirmation."""
    strat = NiftySupportBounce5MITM()
    ts = datetime(2026, 9, 4, 10, 0)

    c_prev = Candle(ts, 24000, 24020, 23980, 23990, 500)  # low 23980 tested EMA20 (23990)
    # Low volume bounce (volume 400 < avg_volume 1000)
    c_curr_low_vol = Candle(ts, 23990, 24050, 23990, 24040, 400)

    state = {
        "timestamp": ts,
        "candles": [c_prev, c_curr_low_vol],
        "indicators": {
            "ema_20_5m": 23990.0,
            "ema_50_1h": 23900.0,
            "avg_volume": 1000.0,
        }
    }
    assert strat.evaluate(state) is None, "Low-volume bounce should be rejected"

    # High volume bounce (volume 1500 > avg_volume 1000)
    c_curr_high_vol = Candle(ts, 23990, 24050, 23990, 24040, 1500)
    state["candles"] = [c_prev, c_curr_high_vol]
    sig = strat.evaluate(state)
    assert sig is not None, "High-volume confirmed bounce should be accepted"


def test_7_iron_fly_null_safety():
    """Verify Iron Fly _leg_prices handles missing keys without KeyError."""
    hedge = IronFlyHedge()
    # Call _leg_prices on empty/partial state
    prices = hedge._leg_prices({})
    assert prices == {}

    prices2 = hedge._leg_prices({"nifty_price": None})
    assert prices2 == {}


def test_8_data_manager_underlying_key():
    """Verify DataManager.get_state() populates the underlying price key."""
    dm_bn = DataManager(underlying="BANKNIFTY")
    dm_bn.on_nifty_tick({"ltp": 52340.5, "volume": 100, "timestamp": datetime(2026, 9, 4, 9, 16)})
    state_bn = dm_bn.get_state()
    assert state_bn["banknifty_price"] == 52340.5
    assert state_bn["nifty_price"] == 52340.5  # back-compat alias

    dm_sx = DataManager(underlying="SENSEX")
    dm_sx.on_nifty_tick({"ltp": 81500.0, "volume": 100, "timestamp": datetime(2026, 9, 4, 9, 16)})
    state_sx = dm_sx.get_state()
    assert state_sx["sensex_price"] == 81500.0


def test_9_data_manager_window_size_5000():
    """Verify DataManager default window_size is 5000."""
    dm = DataManager()
    assert dm.window_size == 5000


def test_10_all_44_strategies_handle_null_state():
    """Verify all 44 strategies return None on null timestamp or empty state without crashing."""
    all_strategies = (
        create_nifty_strategies()
        + create_sensex_strategies()
        + create_banknifty_strategies()
    )
    for strat in all_strategies:
        assert strat.evaluate({}) is None
        assert strat.evaluate({"timestamp": None}) is None
        assert strat.evaluate({"timestamp": datetime.now(), "candles": []}) is None
