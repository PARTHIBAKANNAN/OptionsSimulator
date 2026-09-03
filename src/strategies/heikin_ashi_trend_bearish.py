"""Mirror of HeikinAshiTrendBullish: two consecutive bearish 15m Heikin Ashi candles, the latest
with little/no upper wick, confirmed by the 1H 50-EMA trend being down."""
from datetime import time as dtime
from typing import Optional

from src.strategies.base_strategy import BaseStrategy, Signal

MAX_WICK_TO_BODY_RATIO = 0.30  # Calibrated for realistic market noise

EXCLUDED_WEEKDAYS = {0, 1}  # Monday, Tuesday
DEAD_ZONE_START = dtime(10, 0)
DEAD_ZONE_END = dtime(12, 0)


class HeikinAshiTrendBearish(BaseStrategy):
    def __init__(self, name: str = "HEIKIN_ASHI_TREND_BEARISH", strike_step: int = 50, underlying: str = "NIFTY",
                 apply_day_time_filter: bool = False, min_cooldown_mins: int = 15):
        super().__init__(name=name, direction="PE", strike_step=strike_step, underlying=underlying,
                         min_cooldown_mins=min_cooldown_mins)
        self.apply_day_time_filter = apply_day_time_filter

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        if ts is None or not self.can_trigger(ts):
            return None
        if self.apply_day_time_filter:
            if ts.weekday() in EXCLUDED_WEEKDAYS:
                return None
            if DEAD_ZONE_START <= ts.time() < DEAD_ZONE_END:
                return None

        indicators = data_state.get("indicators", {})
        spot = data_state.get(f"{self.underlying.lower()}_price") or data_state.get("nifty_price")
        if spot is None or spot <= 0:
            return None

        ha = indicators.get("heikin_ashi_15m") or indicators.get("heikin_ashi_5m") or indicators.get("heikin_ashi")
        ema50 = indicators.get("ema_50_1h") or indicators.get("ema_50_5m") or indicators.get("ema_20_5m")
        if ha is None or ema50 is None:
            return None

        body = ha["open"] - ha["close"]
        current_bearish = body > 0
        prev_bearish = ha["prev_open"] > ha["prev_close"]
        if not (current_bearish and prev_bearish and spot < ema50):
            return None

        upper_wick = ha["high"] - ha["open"]
        if upper_wick > MAX_WICK_TO_BODY_RATIO * body:
            return None

        symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
        price = self.get_option_price(symbol, strike, spot, "PE", data_state)
        self.last_signal_time = ts
        return Signal(
            strategy=self.name,
            direction="PE",
            action="BUY",
            strike=symbol,
            confidence=0.70,
            rationale="Heikin Ashi bearish, low upper wick, price below 50-EMA",
            entry_price=price,
            timestamp=ts,
            underlying=self.underlying,
        )
