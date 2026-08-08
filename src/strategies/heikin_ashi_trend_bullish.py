"""Heikin Ashi (smoothed, lagging candles -- see src/utils/indicators.py's heikin_ashi docstring)
trend-continuation signal on 15m: two consecutive bullish HA candles, the latest with little/no
lower wick -- the textbook "strong uptrend intact" pattern -- confirmed by the 1H 50-EMA trend so
this stays trend-following, not a bet on HA's own lag catching a reversal early."""
from src.strategies.base_strategy import BaseStrategy, Signal

# A lower wick this small relative to the candle's body still counts as "no wick" -- HA candles
# are a smoothed transform, exact-zero wicks are rare even in a clean trend.
MAX_WICK_TO_BODY_RATIO = 0.15


class HeikinAshiTrendBullish(BaseStrategy):
    def __init__(self):
        super().__init__(name="HEIKIN_ASHI_TREND_BULLISH", direction="CE")

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        nifty = data_state.get("nifty_price")
        if nifty is None:
            return None

        ha = indicators.get("heikin_ashi_15m")
        ema50 = indicators.get("ema_50_1h")
        if ha is None or ema50 is None:
            return None

        body = ha["close"] - ha["open"]
        current_bullish = body > 0
        prev_bullish = ha["prev_close"] > ha["prev_open"]
        if not (current_bullish and prev_bullish and nifty > ema50):
            return None

        lower_wick = ha["open"] - ha["low"]
        if lower_wick > MAX_WICK_TO_BODY_RATIO * body:
            return None

        symbol, strike = self.select_strike(nifty, "CE")
        price = self.get_option_price(symbol, strike, nifty, "CE", data_state)
        return Signal(
            strategy=self.name,
            direction="CE",
            action="BUY",
            strike=symbol,
            confidence=0.70,
            rationale="Heikin Ashi bullish, no lower wick, price above 50-EMA",
            entry_price=price,
            timestamp=data_state["timestamp"],
        )
