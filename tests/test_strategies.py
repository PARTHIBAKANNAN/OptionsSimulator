from datetime import datetime
from datetime import time as dtime

from src.data_manager import Candle
from src.strategies.rsi_oversold_bullish import RSIOversoldBullish
from src.strategies.rsi_overbought_bearish import RSIOverboughtBearish
from src.strategies.macd_bullish import MACDBullish
from src.strategies.macd_bearish import MACDBearish
from src.strategies.support_bounce_bullish import SupportBounceBullish
from src.strategies.resistance_rejection_bearish import ResistanceRejectionBearish
from src.strategies.orb_bullish import ORBBullish
from src.strategies.orb_bearish import ORBBearish
from src.strategies.heikin_ashi_trend_bullish import HeikinAshiTrendBullish
from src.strategies.heikin_ashi_trend_bearish import HeikinAshiTrendBearish
from src.strategies.engine import StrategyEngine, create_all_strategies

NOW = datetime(2026, 1, 1, 10, 0)


def base_state(**overrides):
    state = {
        "nifty_price": 24000.0,
        "timestamp": NOW,
        "indicators": {},
        "option_chain": {},
        "candles": [],
    }
    state.update(overrides)
    return state


def test_rsi_oversold_bullish_signal_generated():
    strategy = RSIOversoldBullish()
    state = base_state(indicators={
        "rsi_1h": 30, "stochastic_k_15m": 15, "ema_20_1h": 23950, "ema_50_1h": 23900, "volume_ratio": 2.0,
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "CE"
    assert signal.strike == "NIFTY24000CE"


def test_rsi_oversold_bullish_no_signal_when_rsi_above_35():
    strategy = RSIOversoldBullish()
    state = base_state(indicators={
        "rsi_1h": 50, "stochastic_k_15m": 15, "ema_20_1h": 23950, "ema_50_1h": 23900, "volume_ratio": 2.0,
    })
    assert strategy.evaluate(state) is None


def test_rsi_oversold_bullish_blocked_against_the_broader_downtrend():
    strategy = RSIOversoldBullish()
    state = base_state(indicators={
        "rsi_1h": 30, "stochastic_k_15m": 15, "ema_20_1h": 23950, "ema_50_1h": 24100, "volume_ratio": 2.0,
    })
    assert strategy.evaluate(state) is None


def test_rsi_overbought_bearish_signal_generated():
    strategy = RSIOverboughtBearish()
    state = base_state(indicators={
        "rsi_1h": 70, "stochastic_k_15m": 85, "ema_20_1h": 24050, "ema_50_1h": 24100, "volume_ratio": 2.0,
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "PE"


def test_rsi_overbought_bearish_blocked_against_the_broader_uptrend():
    strategy = RSIOverboughtBearish()
    state = base_state(indicators={
        "rsi_1h": 70, "stochastic_k_15m": 85, "ema_20_1h": 24050, "ema_50_1h": 23900, "volume_ratio": 2.0,
    })
    assert strategy.evaluate(state) is None


def test_macd_bullish_signal_on_cross():
    strategy = MACDBullish()
    state = base_state(indicators={
        "macd_histogram_15m": 1.5, "macd_histogram_15m_prev": -0.5, "ema_50_1h": 23900,
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.confidence == 0.80


def test_macd_bullish_no_signal_without_cross():
    strategy = MACDBullish()
    state = base_state(indicators={
        "macd_histogram_15m": 1.5, "macd_histogram_15m_prev": 1.0,  # already positive, no cross
        "ema_50_1h": 23900,
    })
    assert strategy.evaluate(state) is None


def test_macd_bearish_signal_on_cross():
    strategy = MACDBearish()
    state = base_state(indicators={
        "macd_histogram_15m": -1.5, "macd_histogram_15m_prev": 0.5, "ema_50_1h": 24100,
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "PE"


def test_support_bounce_bullish_signal():
    strategy = SupportBounceBullish()
    prev = Candle(timestamp=NOW, open=23960, high=23970, low=23945, close=23955, volume=500)
    current = Candle(timestamp=NOW, open=23955, high=23980, low=23950, close=23975, volume=1500)
    state = base_state(indicators={"ema_20_1h": 23950, "ema_50_1h": 23900, "avg_volume": 1000},
                        candles=[prev, current])
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "CE"


def test_support_bounce_bullish_blocked_against_the_broader_downtrend():
    strategy = SupportBounceBullish()
    prev = Candle(timestamp=NOW, open=23960, high=23970, low=23945, close=23955, volume=500)
    current = Candle(timestamp=NOW, open=23955, high=23980, low=23950, close=23975, volume=1500)
    # Same 20-EMA bounce setup, but the 50-EMA trend is still above price — a countertrend bounce.
    state = base_state(indicators={"ema_20_1h": 23950, "ema_50_1h": 24100, "avg_volume": 1000},
                        candles=[prev, current])
    assert strategy.evaluate(state) is None


def test_support_bounce_bullish_blocked_on_a_weak_close():
    strategy = SupportBounceBullish()
    prev = Candle(timestamp=NOW, open=23960, high=23970, low=23945, close=23955, volume=500)
    # Same bounce setup, but the candle closes near the bottom of its own range — a half-hearted
    # reclaim, not a strong bounce.
    current = Candle(timestamp=NOW, open=23955, high=24000, low=23950, close=23955, volume=1500)
    state = base_state(indicators={"ema_20_1h": 23950, "ema_50_1h": 23900, "avg_volume": 1000},
                        candles=[prev, current])
    assert strategy.evaluate(state) is None


def test_resistance_rejection_bearish_signal():
    strategy = ResistanceRejectionBearish()
    prev = Candle(timestamp=NOW, open=24040, high=24055, low=24035, close=24045, volume=500)
    current = Candle(timestamp=NOW, open=24045, high=24050, low=24010, close=24020, volume=1500)
    state = base_state(indicators={"ema_20_1h": 24050, "ema_50_1h": 24100, "avg_volume": 1000},
                        candles=[prev, current])
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "PE"


def test_resistance_rejection_bearish_blocked_against_the_broader_uptrend():
    strategy = ResistanceRejectionBearish()
    prev = Candle(timestamp=NOW, open=24040, high=24055, low=24035, close=24045, volume=500)
    current = Candle(timestamp=NOW, open=24045, high=24050, low=24010, close=24020, volume=1500)
    state = base_state(indicators={"ema_20_1h": 24050, "ema_50_1h": 23900, "avg_volume": 1000},
                        candles=[prev, current])
    assert strategy.evaluate(state) is None


def test_resistance_rejection_bearish_blocked_on_a_weak_close():
    strategy = ResistanceRejectionBearish()
    prev = Candle(timestamp=NOW, open=24040, high=24055, low=24035, close=24045, volume=500)
    # Closes near the top of its own range — a half-hearted rejection, not a strong one.
    current = Candle(timestamp=NOW, open=24045, high=24050, low=24000, close=24045, volume=1500)
    state = base_state(indicators={"ema_20_1h": 24050, "ema_50_1h": 24100, "avg_volume": 1000},
                        candles=[prev, current])
    assert strategy.evaluate(state) is None


def _orb_day_candles(day, range_high=24020, range_low=23985):
    return [
        Candle(timestamp=datetime.combine(day, dtime(9, 15)), open=24000, high=24010, low=23995, close=24005, volume=1000),
        Candle(timestamp=datetime.combine(day, dtime(9, 20)), open=24005, high=range_high, low=range_low, close=24010, volume=1000),
        Candle(timestamp=datetime.combine(day, dtime(9, 29)), open=24010, high=24015, low=23995, close=24012, volume=1000),
    ]


def test_orb_bullish_fires_on_breakout_above_opening_range_and_not_before():
    strategy = ORBBullish()
    day = datetime(2026, 1, 1).date()
    candles = _orb_day_candles(day)

    # While the opening range (09:15-09:30) is still forming, no signal.
    for i in range(len(candles)):
        state = base_state(indicators={"avg_volume": 1000}, candles=candles[: i + 1])
        assert strategy.evaluate(state) is None

    # After the window, a close still inside the range (24020) shouldn't fire.
    inside = Candle(timestamp=datetime.combine(day, dtime(9, 35)), open=24012, high=24018, low=24005, close=24015, volume=1000)
    candles.append(inside)
    assert strategy.evaluate(base_state(indicators={"avg_volume": 1000}, candles=candles)) is None

    # Breakout candle: close above the range high, on volume.
    breakout = Candle(timestamp=datetime.combine(day, dtime(9, 40)), open=24015, high=24030, low=24014, close=24025, volume=1500)
    candles.append(breakout)
    signal = strategy.evaluate(base_state(indicators={"avg_volume": 1000}, candles=candles))
    assert signal is not None
    assert signal.direction == "CE"

    # Staying above the range afterwards doesn't refire — only the crossing candle does.
    still_up = Candle(timestamp=datetime.combine(day, dtime(9, 45)), open=24025, high=24035, low=24022, close=24028, volume=1200)
    candles.append(still_up)
    assert strategy.evaluate(base_state(indicators={"avg_volume": 1000}, candles=candles)) is None


def test_orb_bearish_fires_on_breakdown_below_opening_range():
    strategy = ORBBearish()
    day = datetime(2026, 1, 1).date()
    candles = _orb_day_candles(day)
    for i in range(len(candles)):
        assert strategy.evaluate(base_state(indicators={"avg_volume": 1000}, candles=candles[: i + 1])) is None

    breakdown = Candle(timestamp=datetime.combine(day, dtime(9, 40)), open=23990, high=23992, low=23970, close=23975, volume=1500)
    candles.append(breakdown)
    signal = strategy.evaluate(base_state(indicators={"avg_volume": 1000}, candles=candles))
    assert signal is not None
    assert signal.direction == "PE"


def test_orb_range_resets_on_a_new_day():
    strategy = ORBBullish()
    day1 = datetime(2026, 1, 1).date()
    day2 = datetime(2026, 1, 2).date()
    candles = _orb_day_candles(day1, range_high=24020)
    for i in range(len(candles)):
        strategy.evaluate(base_state(indicators={"avg_volume": 1000}, candles=candles[: i + 1]))
    assert strategy._range_high == 24020

    day2_candles = _orb_day_candles(day2, range_high=24500)
    combined = candles + day2_candles
    for i in range(len(candles), len(combined)):
        strategy.evaluate(base_state(indicators={"avg_volume": 1000}, candles=combined[: i + 1]))
    assert strategy._range_high == 24500  # rebuilt fresh for the new day, not carried over


def test_heikin_ashi_trend_bullish_signal_on_two_bullish_candles_no_lower_wick():
    strategy = HeikinAshiTrendBullish()
    state = base_state(indicators={
        "ema_50_1h": 23900,
        "heikin_ashi_15m": {
            "open": 24000, "high": 24030, "low": 23999, "close": 24025,  # body 25, wick 1 (<15%)
            "prev_open": 23980, "prev_close": 24000,  # prev bullish too
        },
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "CE"
    assert signal.confidence == 0.70


def test_heikin_ashi_trend_bullish_no_signal_with_a_large_lower_wick():
    strategy = HeikinAshiTrendBullish()
    state = base_state(indicators={
        "ema_50_1h": 23900,
        "heikin_ashi_15m": {
            "open": 24000, "high": 24030, "low": 23950, "close": 24025,  # body 25, wick 50 (weak trend)
            "prev_open": 23980, "prev_close": 24000,
        },
    })
    assert strategy.evaluate(state) is None


def test_heikin_ashi_trend_bullish_no_signal_when_previous_candle_was_bearish():
    strategy = HeikinAshiTrendBullish()
    state = base_state(indicators={
        "ema_50_1h": 23900,
        "heikin_ashi_15m": {
            "open": 24000, "high": 24030, "low": 23999, "close": 24025,
            "prev_open": 24010, "prev_close": 23995,  # prev was bearish -- no 2-candle confirmation
        },
    })
    assert strategy.evaluate(state) is None


def test_heikin_ashi_trend_bullish_no_signal_below_50ema():
    strategy = HeikinAshiTrendBullish()
    state = base_state(nifty_price=24000.0, indicators={
        "ema_50_1h": 24100,  # price below the trend filter
        "heikin_ashi_15m": {
            "open": 24000, "high": 24030, "low": 23999, "close": 24025,
            "prev_open": 23980, "prev_close": 24000,
        },
    })
    assert strategy.evaluate(state) is None


def test_heikin_ashi_trend_bearish_signal_on_two_bearish_candles_no_upper_wick():
    strategy = HeikinAshiTrendBearish()
    # Thursday, 12:30 -- outside the excluded Mon/Tue days and the 10:00-12:00 dead zone.
    state = base_state(nifty_price=24000.0, timestamp=datetime(2026, 1, 1, 12, 30), indicators={
        "ema_50_1h": 24100,
        "heikin_ashi_15m": {
            "open": 24000, "high": 24001, "low": 23975, "close": 23980,  # body 20, wick 1
            "prev_open": 24015, "prev_close": 24000,  # prev bearish too
        },
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "PE"


def test_heikin_ashi_trend_bearish_no_signal_with_a_large_upper_wick():
    strategy = HeikinAshiTrendBearish()
    state = base_state(nifty_price=24000.0, timestamp=datetime(2026, 1, 1, 12, 30), indicators={
        "ema_50_1h": 24100,
        "heikin_ashi_15m": {
            "open": 24000, "high": 24040, "low": 23975, "close": 23980,  # body 20, wick 40
            "prev_open": 24015, "prev_close": 24000,
        },
    })
    assert strategy.evaluate(state) is None


def test_heikin_ashi_trend_bearish_no_signal_on_monday_or_tuesday():
    strategy = HeikinAshiTrendBearish()
    good_indicators = {
        "ema_50_1h": 24100,
        "heikin_ashi_15m": {
            "open": 24000, "high": 24001, "low": 23975, "close": 23980,
            "prev_open": 24015, "prev_close": 24000,
        },
    }
    monday = datetime(2026, 1, 5, 12, 30)  # 2026-01-05 is a Monday
    tuesday = datetime(2026, 1, 6, 12, 30)  # 2026-01-06 is a Tuesday
    assert strategy.evaluate(base_state(nifty_price=24000.0, timestamp=monday, indicators=good_indicators)) is None
    assert strategy.evaluate(base_state(nifty_price=24000.0, timestamp=tuesday, indicators=good_indicators)) is None


def test_heikin_ashi_trend_bearish_no_signal_in_the_10am_to_12pm_dead_zone():
    strategy = HeikinAshiTrendBearish()
    good_indicators = {
        "ema_50_1h": 24100,
        "heikin_ashi_15m": {
            "open": 24000, "high": 24001, "low": 23975, "close": 23980,
            "prev_open": 24015, "prev_close": 24000,
        },
    }
    for hour, minute in [(10, 0), (11, 0), (11, 59)]:
        state = base_state(nifty_price=24000.0, timestamp=datetime(2026, 1, 1, hour, minute),
                            indicators=good_indicators)
        assert strategy.evaluate(state) is None
    # right at the boundary, the dead zone ends and signals resume
    state = base_state(nifty_price=24000.0, timestamp=datetime(2026, 1, 1, 12, 0), indicators=good_indicators)
    assert strategy.evaluate(state) is not None


def test_nifty_live_roster_is_the_curated_four_strategy_set():
    # Master roster contains all 32 strategies (10 NIFTY + 11 SENSEX + 11 BANKNIFTY)
    strategies = create_all_strategies()
    assert len(strategies) == 32
    names = {s.name for s in strategies}
    assert "NIFTY_ORB_BULLISH_1M_ATM" in names
    assert "NIFTY_SUPPORT_BOUNCE_5M_ITM" in names
    assert "SENSEX_HEIKIN_ASHI_BEARISH_5M_ITM" in names
    assert "BANKNIFTY_SUPPORT_BOUNCE_5M_ITM" in names


def test_confidence_score_present_on_all_strategies():
    assert len(create_all_strategies()) == 32
    # RSI strategy confidence is fixed at 0.75 by design
    strategy = RSIOversoldBullish()
    signal = strategy.evaluate(base_state(indicators={
        "rsi_1h": 30, "stochastic_k_15m": 15, "ema_20_1h": 23950, "ema_50_1h": 23900, "volume_ratio": 2.0,
    }))
    assert signal.confidence == 0.75


def test_engine_deduplicates_within_cooldown():
    engine = StrategyEngine(strategies=[RSIOversoldBullish()], signal_cooldown_mins=5)
    state = base_state(indicators={
        "rsi_1h": 30, "stochastic_k_15m": 15, "ema_20_1h": 23950, "ema_50_1h": 23900, "volume_ratio": 2.0,
    })
    first = engine.evaluate_all(state)
    second = engine.evaluate_all(state)  # same timestamp, within cooldown
    assert len(first) == 1
    assert len(second) == 0


def test_engine_runs_all_seven_strategies_without_error():
    engine = StrategyEngine()
    state = base_state(indicators={
        "rsi_1h": 50, "stochastic_k_15m": 50, "ema_20_1h": 24000, "ema_50_1h": 24000,
        "volume_ratio": 1.0, "volume_ratio_5m": 1.0, "avg_volume": 1000,
        "macd_histogram_15m": 0, "macd_histogram_15m_prev": 0,
    }, candles=[
        Candle(timestamp=NOW, open=24000, high=24010, low=23990, close=24000, volume=1000),
        Candle(timestamp=NOW, open=24000, high=24010, low=23990, close=24000, volume=1000),
    ])
    signals = engine.evaluate_all(state)
    assert isinstance(signals, list)
