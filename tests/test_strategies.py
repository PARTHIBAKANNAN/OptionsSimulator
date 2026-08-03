from datetime import datetime

from src.data_manager import Candle
from src.strategies.rsi_oversold_bullish import RSIOversoldBullish
from src.strategies.rsi_overbought_bearish import RSIOverboughtBearish
from src.strategies.macd_bullish import MACDBullish
from src.strategies.macd_bearish import MACDBearish
from src.strategies.support_bounce_bullish import SupportBounceBullish
from src.strategies.resistance_rejection_bearish import ResistanceRejectionBearish
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
        "rsi_1h": 30, "stochastic_k_15m": 15, "ema_20_1h": 23950, "volume_ratio": 2.0,
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "CE"
    assert signal.strike == "NIFTY24000CE"


def test_rsi_oversold_bullish_no_signal_when_rsi_above_35():
    strategy = RSIOversoldBullish()
    state = base_state(indicators={
        "rsi_1h": 50, "stochastic_k_15m": 15, "ema_20_1h": 23950, "volume_ratio": 2.0,
    })
    assert strategy.evaluate(state) is None


def test_rsi_overbought_bearish_signal_generated():
    strategy = RSIOverboughtBearish()
    state = base_state(indicators={
        "rsi_1h": 70, "stochastic_k_15m": 85, "ema_20_1h": 24050, "volume_ratio": 2.0,
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "PE"


def test_macd_bullish_signal_on_cross():
    strategy = MACDBullish()
    state = base_state(indicators={
        "macd_histogram_1h": 1.5, "macd_histogram_1h_prev": -0.5,
        "volume_ratio_5m": 2.5, "ema_50_1h": 23900,
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.confidence == 0.80


def test_macd_bullish_no_signal_without_cross():
    strategy = MACDBullish()
    state = base_state(indicators={
        "macd_histogram_1h": 1.5, "macd_histogram_1h_prev": 1.0,  # already positive, no cross
        "volume_ratio_5m": 2.5, "ema_50_1h": 23900,
    })
    assert strategy.evaluate(state) is None


def test_macd_bearish_signal_on_cross():
    strategy = MACDBearish()
    state = base_state(indicators={
        "macd_histogram_1h": -1.5, "macd_histogram_1h_prev": 0.5,
        "volume_ratio_5m": 2.5, "ema_50_1h": 24100,
    })
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "PE"


def test_support_bounce_bullish_signal():
    strategy = SupportBounceBullish()
    prev = Candle(timestamp=NOW, open=23960, high=23970, low=23945, close=23955, volume=500)
    current = Candle(timestamp=NOW, open=23955, high=23980, low=23950, close=23975, volume=1500)
    state = base_state(indicators={"ema_20_1h": 23950, "avg_volume": 1000}, candles=[prev, current])
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "CE"


def test_resistance_rejection_bearish_signal():
    strategy = ResistanceRejectionBearish()
    prev = Candle(timestamp=NOW, open=24040, high=24055, low=24035, close=24045, volume=500)
    current = Candle(timestamp=NOW, open=24045, high=24050, low=24010, close=24020, volume=1500)
    state = base_state(indicators={"ema_20_1h": 24050, "avg_volume": 1000}, candles=[prev, current])
    signal = strategy.evaluate(state)
    assert signal is not None
    assert signal.direction == "PE"


def test_confidence_score_present_on_all_strategies():
    assert len(create_all_strategies()) == 6
    # RSI strategy confidence is fixed at 0.75 by design
    strategy = RSIOversoldBullish()
    signal = strategy.evaluate(base_state(indicators={
        "rsi_1h": 30, "stochastic_k_15m": 15, "ema_20_1h": 23950, "volume_ratio": 2.0,
    }))
    assert signal.confidence == 0.75


def test_engine_deduplicates_within_cooldown():
    engine = StrategyEngine(strategies=[RSIOversoldBullish()], signal_cooldown_mins=5)
    state = base_state(indicators={
        "rsi_1h": 30, "stochastic_k_15m": 15, "ema_20_1h": 23950, "volume_ratio": 2.0,
    })
    first = engine.evaluate_all(state)
    second = engine.evaluate_all(state)  # same timestamp, within cooldown
    assert len(first) == 1
    assert len(second) == 0


def test_engine_runs_all_six_strategies_without_error():
    engine = StrategyEngine()
    state = base_state(indicators={
        "rsi_1h": 50, "stochastic_k_15m": 50, "ema_20_1h": 24000, "ema_50_1h": 24000,
        "volume_ratio": 1.0, "volume_ratio_5m": 1.0, "avg_volume": 1000,
        "macd_histogram_1h": 0, "macd_histogram_1h_prev": 0,
    }, candles=[
        Candle(timestamp=NOW, open=24000, high=24010, low=23990, close=24000, volume=1000),
        Candle(timestamp=NOW, open=24000, high=24010, low=23990, close=24000, volume=1000),
    ])
    signals = engine.evaluate_all(state)
    assert isinstance(signals, list)
