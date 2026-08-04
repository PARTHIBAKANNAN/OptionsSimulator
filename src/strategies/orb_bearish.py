"""Opening Range Breakout (bearish): mirror of ORBBullish — a close breaking back below the
first 15 minutes' opening-range low, on volume, signals a bearish continuation."""
from datetime import time as dtime

from src.strategies.base_strategy import BaseStrategy, Signal

ORB_WINDOW_START = dtime(9, 15)
ORB_WINDOW_END = dtime(9, 30)


class ORBBearish(BaseStrategy):
    def __init__(self):
        super().__init__(name="ORB_BEARISH", direction="PE")
        self._range_day = None
        self._range_high = None
        self._range_low = None

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        current, prev = candles[-1], candles[-2]
        day = current.timestamp.date()
        t = current.timestamp.time()

        if day != self._range_day:
            self._range_day = day
            self._range_high = None
            self._range_low = None

        if t < ORB_WINDOW_START:
            return None
        if t < ORB_WINDOW_END:
            self._range_high = current.high if self._range_high is None else max(self._range_high, current.high)
            self._range_low = current.low if self._range_low is None else min(self._range_low, current.low)
            return None

        if self._range_low is None:
            return None

        avg_volume = indicators.get("avg_volume")
        if avg_volume is None:
            return None

        if prev.close >= self._range_low > current.close and current.volume > avg_volume:
            nifty = current.close
            symbol, strike = self.select_strike(nifty, "PE")
            price = self.get_option_price(symbol, strike, nifty, "PE", data_state)
            return Signal(
                strategy=self.name,
                direction="PE",
                action="BUY",
                strike=symbol,
                confidence=0.70,
                rationale=f"ORB breakdown below opening range low {self._range_low:.1f}",
                entry_price=price,
                timestamp=data_state["timestamp"],
            )
        return None
