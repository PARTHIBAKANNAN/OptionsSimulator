"""MACD histogram crosses below zero on 15m (fast enough to give this strategy a real sample
size), confirmed by the slower 1H 50-EMA trend."""
from typing import Optional

from src.strategies.base_strategy import BaseStrategy, Signal


class MACDBearish(BaseStrategy):
    def __init__(self, name: str = "MACD_BEARISH", strike_step: int = 50, underlying: str = "NIFTY"):
        super().__init__(name=name, direction="PE", strike_step=strike_step, underlying=underlying)

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        spot = data_state.get(f"{self.underlying.lower()}_price") or data_state.get("nifty_price")
        if spot is None or spot <= 0:
            return None

        macd_hist = indicators.get("macd_histogram_15m")
        macd_hist_prev = indicators.get("macd_histogram_15m_prev")
        ema50 = indicators.get("ema_50_1h") or indicators.get("ema_50_5m") or indicators.get("ema_20_5m")
        if None in (macd_hist, macd_hist_prev, ema50):
            return None

        if macd_hist < 0 and macd_hist_prev >= 0 and spot < ema50:
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name,
                direction="PE",
                action="BUY",
                strike=symbol,
                confidence=0.80,
                rationale="MACD bearish cross, price below 50-EMA",
                entry_price=price,
                timestamp=ts,
                underlying=self.underlying,
            )
        return None
