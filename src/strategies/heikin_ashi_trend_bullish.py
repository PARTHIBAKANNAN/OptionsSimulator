"""Heikin Ashi (smoothed, lagging candles -- see src/utils/indicators.py's heikin_ashi docstring)
trend-continuation signal on 15m: two consecutive bullish HA candles, the latest with little/no
lower wick -- the textbook "strong uptrend intact" pattern -- confirmed by the 1H 50-EMA trend so
this stays trend-following, not a bet on HA's own lag catching a reversal early."""
from src.strategies.base_strategy import BaseStrategy, Signal

# A lower wick this small relative to the candle's body still counts as "no wick" -- HA candles
# are a smoothed transform, exact-zero wicks are rare even in a clean trend.
MAX_WICK_TO_BODY_RATIO = 0.15


class HeikinAshiTrendBullish(BaseStrategy):
    def __init__(self, name: str = "HEIKIN_ASHI_TREND_BULLISH", strike_step: int = 50, underlying: str = "NIFTY",
                 min_cooldown_mins: int = 15):
        super().__init__(name=name, direction="CE", strike_step=strike_step, underlying=underlying,
                          min_cooldown_mins=min_cooldown_mins)

    def evaluate(self, data_state: dict):
        timestamp = data_state.get("timestamp")
        # See HeikinAshiTrendBearish's matching comment: this condition is a state (2 consecutive
        # bullish HA candles + trend filter), not an edge, so it needs its own cooldown or it
        # re-qualifies on every tick a real uptrend is intact.
        if not self.can_trigger(timestamp):
            return None
        indicators = data_state.get("indicators") or {}
        nifty = data_state.get(f"{self.underlying.lower()}_price") or data_state.get("nifty_price")
        if nifty is None or nifty <= 0:
            return None

        # 1. ADX Trend Strength Filter
        adx_val = indicators.get("adx_14_5m") or indicators.get("adx_14_1m")
        if not self.is_trend_confirmed(adx_val, min_adx=20.0):
            return None

        # 2. VWAP Proximity Filter (avoid chasing extended moves)
        vwap_val = indicators.get("vwap_5m") or indicators.get("vwap")
        if not self.is_vwap_acceptable(nifty, vwap_val, max_dist_pct=0.40):
            return None

        # 3. Midday Volume Filter
        vol_ratio = indicators.get("volume_ratio_5m") or indicators.get("volume_ratio")
        if not self.is_volume_acceptable(vol_ratio, timestamp, min_morning=1.0, min_midday=1.4):
            return None

        ha = indicators.get("heikin_ashi_15m") or indicators.get("heikin_ashi_5m")
        ema50 = indicators.get("ema_50_1h") or indicators.get("ema_50_5m")
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
            underlying=self.underlying,
        )
