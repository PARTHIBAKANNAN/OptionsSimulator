"""Runs every registered strategy against the current data_state, deduping and rate-limiting signals."""
from datetime import datetime, timedelta

from src.strategies.base_strategy import BaseStrategy, Signal
from src.strategies.rsi_oversold_bullish import RSIOversoldBullish
from src.strategies.macd_bullish import MACDBullish
from src.strategies.support_bounce_bullish import SupportBounceBullish
from src.strategies.rsi_overbought_bearish import RSIOverboughtBearish
from src.strategies.macd_bearish import MACDBearish
from src.strategies.resistance_rejection_bearish import ResistanceRejectionBearish


def create_all_strategies() -> list[BaseStrategy]:
    return [
        RSIOversoldBullish(),
        MACDBullish(),
        SupportBounceBullish(),
        RSIOverboughtBearish(),
        MACDBearish(),
        ResistanceRejectionBearish(),
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
