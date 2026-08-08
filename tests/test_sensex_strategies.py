from datetime import datetime
from datetime import time as dtime

from src.data_manager import Candle
from src.strategies.sensex_strategies import (
    SensexHeikinAshiTrendBearish, SensexHeikinAshiTrendBullish, SensexMACDBearish, SensexMACDBullish,
    SensexORBBearish, SensexORBBullish, SensexResistanceRejectionBearish, SensexSupportBounceBullish,
    create_all_sensex_strategies, create_live_sensex_strategies,
)

NOW = datetime(2026, 1, 1, 10, 0)
SPOT = 81500.0  # SENSEX trades roughly 3.3x NIFTY -- large enough to catch any NIFTY-strike leakage


def base_state(**overrides):
    state = {
        "nifty_price": SPOT,
        "timestamp": NOW,
        "indicators": {},
        "option_chain": {},
        "candles": [],
    }
    state.update(overrides)
    return state


def test_all_eight_sensex_strategies_are_distinct_and_named():
    strategies = create_all_sensex_strategies()
    names = {s.name for s in strategies}
    assert len(names) == 8
    assert all(name.startswith("SENSEX_") for name in names)
    assert {s.underlying for s in strategies} == {"SENSEX"}
    ce = {s.name for s in strategies if s.direction == "CE"}
    pe = {s.name for s in strategies if s.direction == "PE"}
    assert len(ce) == 4
    assert len(pe) == 4


def test_live_sensex_roster_is_the_curated_five_strategy_set():
    names = {s.name for s in create_live_sensex_strategies()}
    assert names == {
        "SENSEX_MACD_BULLISH", "SENSEX_SUPPORT_BOUNCE_BULLISH", "SENSEX_HEIKIN_ASHI_TREND_BEARISH",
        "SENSEX_MACD_BEARISH", "SENSEX_ORB_BEARISH",
    }


def test_sensex_heikin_ashi_bearish_defaults_to_unfiltered():
    # NIFTY's Mon/Tue + 10-12 exclusion was tuned on NIFTY's own data -- must not silently apply
    # to SENSEX until validated there too.
    strategy = SensexHeikinAshiTrendBearish()
    assert strategy.apply_day_time_filter is False


def test_sensex_heikin_ashi_bullish_signal_uses_sensex_symbol():
    strategy = SensexHeikinAshiTrendBullish()
    state = base_state(indicators={
        "ema_50_1h": 81400,
        "heikin_ashi_15m": {
            "open": 81500, "high": 81530, "low": 81499, "close": 81525,  # body 25, wick 1
            "prev_open": 81480, "prev_close": 81500,
        },
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.strategy == "SENSEX_HEIKIN_ASHI_TREND_BULLISH"
    assert signal.strike.startswith("SENSEX")


def test_sensex_heikin_ashi_bearish_signal_uses_sensex_symbol_and_ignores_nifty_day_filter():
    strategy = SensexHeikinAshiTrendBearish()
    # NOW is a Thursday at 10:00 -- inside NIFTY's excluded dead zone, but the SENSEX variant is
    # unfiltered, so it should still fire.
    state = base_state(indicators={
        "ema_50_1h": 81600,
        "heikin_ashi_15m": {
            "open": 81500, "high": 81501, "low": 81475, "close": 81480,  # body 20, wick 1
            "prev_open": 81515, "prev_close": 81500,
        },
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.strategy == "SENSEX_HEIKIN_ASHI_TREND_BEARISH"
    assert signal.strike.startswith("SENSEX")


def test_sensex_macd_bullish_signal_uses_sensex_symbol():
    strategy = SensexMACDBullish()
    state = base_state(indicators={
        "macd_histogram_15m": 1.5, "macd_histogram_15m_prev": -0.5, "ema_50_1h": 81000,
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.strategy == "SENSEX_MACD_BULLISH"
    assert signal.strike.startswith("SENSEX")
    assert "NIFTY" not in signal.strike


def test_sensex_macd_bearish_signal_uses_sensex_symbol():
    strategy = SensexMACDBearish()
    state = base_state(indicators={
        "macd_histogram_15m": -1.5, "macd_histogram_15m_prev": 0.5, "ema_50_1h": 82000,
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.strategy == "SENSEX_MACD_BEARISH"
    assert signal.strike.startswith("SENSEX")


def test_sensex_support_bounce_bullish_signal_uses_sensex_symbol():
    strategy = SensexSupportBounceBullish()
    prev = Candle(timestamp=NOW, open=81460, high=81470, low=81445, close=81455, volume=500)
    current = Candle(timestamp=NOW, open=81455, high=81480, low=81450, close=81475, volume=1500)
    state = base_state(indicators={"ema_20_1h": 81450, "ema_50_1h": 81400, "avg_volume": 1000},
                        candles=[prev, current])
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.strike.startswith("SENSEX")


def test_sensex_resistance_rejection_bearish_signal_uses_sensex_symbol():
    strategy = SensexResistanceRejectionBearish()
    prev = Candle(timestamp=NOW, open=81540, high=81555, low=81535, close=81545, volume=500)
    current = Candle(timestamp=NOW, open=81545, high=81550, low=81510, close=81520, volume=1500)
    state = base_state(indicators={"ema_20_1h": 81550, "ema_50_1h": 81600, "avg_volume": 1000},
                        candles=[prev, current])
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.strike.startswith("SENSEX")


def _orb_day_candles(day, range_high=81520, range_low=81485):
    return [
        Candle(timestamp=datetime.combine(day, dtime(9, 15)), open=81500, high=81510, low=81495, close=81505, volume=1000),
        Candle(timestamp=datetime.combine(day, dtime(9, 20)), open=81505, high=range_high, low=range_low, close=81510, volume=1000),
        Candle(timestamp=datetime.combine(day, dtime(9, 29)), open=81510, high=81515, low=81495, close=81512, volume=1000),
    ]


def test_sensex_orb_bullish_fires_on_breakout_with_sensex_symbol():
    strategy = SensexORBBullish()
    day = datetime(2026, 1, 1).date()
    candles = _orb_day_candles(day)
    for i in range(len(candles)):
        strategy.evaluate(base_state(indicators={"avg_volume": 1000}, candles=candles[: i + 1]))

    breakout = Candle(timestamp=datetime.combine(day, dtime(9, 40)), open=81512, high=81530, low=81511, close=81525, volume=1500)
    candles.append(breakout)
    signal = strategy.evaluate(base_state(indicators={"avg_volume": 1000}, candles=candles))
    assert signal is not None
    assert signal.direction == "CE"
    assert signal.strike.startswith("SENSEX")


def test_sensex_orb_bearish_fires_on_breakdown_with_sensex_symbol():
    strategy = SensexORBBearish()
    day = datetime(2026, 1, 1).date()
    candles = _orb_day_candles(day)
    for i in range(len(candles)):
        strategy.evaluate(base_state(indicators={"avg_volume": 1000}, candles=candles[: i + 1]))

    breakdown = Candle(timestamp=datetime.combine(day, dtime(9, 40)), open=81490, high=81492, low=81470, close=81475, volume=1500)
    candles.append(breakdown)
    signal = strategy.evaluate(base_state(indicators={"avg_volume": 1000}, candles=candles))
    assert signal is not None
    assert signal.direction == "PE"
    assert signal.strike.startswith("SENSEX")
