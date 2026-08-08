"""Mirror of HeikinAshiTrendBullish: two consecutive bearish 15m Heikin Ashi candles, the latest
with little/no upper wick, confirmed by the 1H 50-EMA trend being down."""
from datetime import time as dtime

from src.strategies.base_strategy import BaseStrategy, Signal

MAX_WICK_TO_BODY_RATIO = 0.15

# Trade-log analysis (Quantman full-year backtest) showed Monday+Tuesday and the 10:00-12:00
# window are net losers while every other day/time is profitable -- excluded rather than tuned.
EXCLUDED_WEEKDAYS = {0, 1}  # Monday, Tuesday
DEAD_ZONE_START = dtime(10, 0)
DEAD_ZONE_END = dtime(12, 0)


class HeikinAshiTrendBearish(BaseStrategy):
    def __init__(self):
        super().__init__(name="HEIKIN_ASHI_TREND_BEARISH", direction="PE")

    def evaluate(self, data_state: dict):
        timestamp = data_state.get("timestamp")
        if timestamp is None:
            return None
        if timestamp.weekday() in EXCLUDED_WEEKDAYS:
            return None
        if DEAD_ZONE_START <= timestamp.time() < DEAD_ZONE_END:
            return None

        indicators = data_state.get("indicators", {})
        nifty = data_state.get("nifty_price")
        if nifty is None:
            return None

        ha = indicators.get("heikin_ashi_15m")
        ema50 = indicators.get("ema_50_1h")
        if ha is None or ema50 is None:
            return None

        body = ha["open"] - ha["close"]
        current_bearish = body > 0
        prev_bearish = ha["prev_close"] < ha["prev_open"]
        if not (current_bearish and prev_bearish and nifty < ema50):
            return None

        upper_wick = ha["high"] - ha["open"]
        if upper_wick > MAX_WICK_TO_BODY_RATIO * body:
            return None

        symbol, strike = self.select_strike(nifty, "PE")
        price = self.get_option_price(symbol, strike, nifty, "PE", data_state)
        return Signal(
            strategy=self.name,
            direction="PE",
            action="BUY",
            strike=symbol,
            confidence=0.70,
            rationale="Heikin Ashi bearish, no upper wick, price below 50-EMA",
            entry_price=price,
            timestamp=data_state["timestamp"],
        )
