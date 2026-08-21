"""Runs every registered strategy against the current data_state, deduping and rate-limiting signals."""
from datetime import datetime, timedelta

from src.strategies.base_strategy import BaseStrategy, Signal
from src.strategies.heikin_ashi_trend_bearish import HeikinAshiTrendBearish
from src.strategies.macd_bullish import MACDBullish
from src.strategies.orb_bullish import ORBBullish
from src.strategies.macd_bearish import MACDBearish


from src.strategies.nifty_5m_strategies import (
    NiftySupportBounce5MITM,
    NiftyHeikinAshiBullish5MITM,
    NiftyORBBullish5MITM,
    NiftyResistanceRejection5MITM,
    NiftyHeikinAshiBearish5MITM,
    NiftyORBBearish5MITM,
)
from src.strategies.sensex_5m_strategies import (
    SensexSupportBounce5MITM,
    SensexHeikinAshiBullish5MITM,
    SensexORBBullish5MITM,
    SensexResistanceRejection5MITM,
    SensexHeikinAshiBearish5MITM,
    SensexORBBearish5MITM,
)
from src.strategies.sensex_strategies import (
    SensexMACDBullish,
    SensexSupportBounceBullish,
    SensexHeikinAshiTrendBearish,
    SensexMACDBearish,
    SensexORBBearish,
)


def create_all_strategies() -> list[BaseStrategy]:
    """Returns the full master roster of 21 active strategies:
    - 9 Standard 1-Minute ATM Baseline Strategies (4 NIFTY + 5 SENSEX)
    - 12 High-Conviction 5-Minute ITM Strategies (6 NIFTY + 6 SENSEX)
    """
    return [
        # --- 9 Existing 1-Minute ATM Baseline Strategies ---
        ORBBullish(name="NIFTY_ORB_BULLISH_1M_ATM"),
        MACDBullish(name="NIFTY_MACD_BULLISH_1M_ATM"),
        HeikinAshiTrendBearish(name="NIFTY_HEIKIN_ASHI_BEARISH_1M_ATM"),
        MACDBearish(name="NIFTY_MACD_BEARISH_1M_ATM"),
        SensexMACDBullish(name="SENSEX_MACD_BULLISH_1M_ATM"),
        SensexSupportBounceBullish(name="SENSEX_SUPPORT_BOUNCE_1M_ATM"),
        SensexHeikinAshiTrendBearish(name="SENSEX_HEIKIN_ASHI_BEARISH_1M_ATM"),
        SensexMACDBearish(name="SENSEX_MACD_BEARISH_1M_ATM"),
        SensexORBBearish(name="SENSEX_ORB_BEARISH_1M_ATM"),

        # --- 12 New 5-Minute ITM Suite (6 NIFTY + 6 SENSEX) ---
        NiftySupportBounce5MITM(),
        NiftyHeikinAshiBullish5MITM(),
        NiftyORBBullish5MITM(),
        NiftyResistanceRejection5MITM(),
        NiftyHeikinAshiBearish5MITM(),
        NiftyORBBearish5MITM(),

        SensexSupportBounce5MITM(),
        SensexHeikinAshiBullish5MITM(),
        SensexORBBullish5MITM(),
        SensexResistanceRejection5MITM(),
        SensexHeikinAshiBearish5MITM(),
        SensexORBBearish5MITM(),
    ]


def create_live_strategies() -> list[BaseStrategy]:
    return create_all_strategies()


class StrategyEngine:
    def __init__(self, strategies: list[BaseStrategy] = None, signal_cooldown_mins: int = 5, logger=None):
        self.strategies = strategies if strategies is not None else create_all_strategies()
        self.signal_cooldown = timedelta(minutes=signal_cooldown_mins)
        self.logger = logger

    def evaluate_all(self, data_state: dict) -> list[Signal]:
        signals = []
        for strategy in self.strategies:
            try:
                signal = strategy.evaluate(data_state)
            except Exception as e:
                if self.logger:
                    self.logger.log_error(f"Strategy {strategy.name} raised: {e}", {"strategy": strategy.name})
                continue

            if signal is None:
                continue

            if strategy.last_signal_time and signal.timestamp - strategy.last_signal_time < self.signal_cooldown:
                continue

            strategy.last_signal_time = signal.timestamp
            signals.append(signal)
            if self.logger:
                self.logger.log_signal(strategy.name, {
                    "strike": signal.strike, "entry_price": signal.entry_price,
                    "confidence": signal.confidence, "rationale": signal.rationale,
                })
        return signals
