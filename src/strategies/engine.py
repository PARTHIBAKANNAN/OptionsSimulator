"""Runs every registered strategy against the current data_state, deduping and rate-limiting signals."""
from datetime import datetime, timedelta

from src.strategies.base_strategy import BaseStrategy, Signal
from src.strategies.heikin_ashi_trend_bearish import HeikinAshiTrendBearish
from src.strategies.macd_bullish import MACDBullish
from src.strategies.orb_bullish import ORBBullish
from src.strategies.macd_bearish import MACDBearish


def create_all_strategies() -> list[BaseStrategy]:
    # Curated live roster, replacing the original 8-strategy NIFTY set after a full backtest
    # comparison across all of them plus a 2-year out-of-sample check on the two newer additions
    # (ORB_BULLISH already had a strike-step fix validated; HeikinAshiTrendBearish's profit factor
    # held up across both halves of its 2-year window). MACD_BULLISH/MACD_BEARISH were already the
    # strongest performers in the original comparison. SupportBounceBullish, RSIOverboughtBearish,
    # ResistanceRejectionBearish, ORBBearish, and RSIOversoldBullish (no genuine out-of-sample edge)
    # are dropped from the live roster -- see docs/ARCHITECTURE.md. HeikinAshiTrendBullish has not
    # been validated the same way as its bearish counterpart and stays excluded.
    return [
        ORBBullish(),
        MACDBullish(),
        HeikinAshiTrendBearish(),
        MACDBearish(),
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
