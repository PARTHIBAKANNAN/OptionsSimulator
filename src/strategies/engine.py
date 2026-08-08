"""Runs every registered strategy against the current data_state, deduping and rate-limiting signals."""
from datetime import datetime, timedelta

from src.strategies.base_strategy import BaseStrategy, Signal
from src.strategies.heikin_ashi_trend_bearish import HeikinAshiTrendBearish
from src.strategies.macd_bullish import MACDBullish
from src.strategies.support_bounce_bullish import SupportBounceBullish
from src.strategies.orb_bullish import ORBBullish
from src.strategies.rsi_overbought_bearish import RSIOverboughtBearish
from src.strategies.macd_bearish import MACDBearish
from src.strategies.resistance_rejection_bearish import ResistanceRejectionBearish
from src.strategies.orb_bearish import ORBBearish


def create_all_strategies() -> list[BaseStrategy]:
    # RSIOversoldBullish is deliberately excluded: a full-year out-of-sample backtest showed it
    # has no genuine edge (only profitable on the exact 90-day window it was originally tuned on,
    # net negative everywhere else, 300+ days continuously underwater). Dropped rather than run
    # live — see docs/ARCHITECTURE.md.
    #
    # HeikinAshiTrendBearish cleared its own 2-year out-of-sample check (profit factor held up
    # across both halves) and is going live for a 1-2 month paper-trading pilot alongside
    # ORB_BULLISH. HeikinAshiTrendBullish has not been validated the same way and stays excluded.
    return [
        MACDBullish(),
        SupportBounceBullish(),
        ORBBullish(),
        RSIOverboughtBearish(),
        MACDBearish(),
        ResistanceRejectionBearish(),
        ORBBearish(),
        HeikinAshiTrendBearish(),
    ]


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
