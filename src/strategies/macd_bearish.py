"""MACD histogram crosses below zero on 1H, with a volume spike on 5m and price below 50-EMA."""
from src.strategies.base_strategy import BaseStrategy, Signal


class MACDBearish(BaseStrategy):
    def __init__(self):
        super().__init__(name="MACD_BEARISH", direction="PE")

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        nifty = data_state.get("nifty_price")
        if nifty is None:
            return None

        macd_hist = indicators.get("macd_histogram_1h")
        macd_hist_prev = indicators.get("macd_histogram_1h_prev")
        volume_ratio = indicators.get("volume_ratio_5m")
        ema50 = indicators.get("ema_50_1h")
        if None in (macd_hist, macd_hist_prev, volume_ratio, ema50):
            return None

        if macd_hist < 0 and macd_hist_prev >= 0 and volume_ratio > 2.0 and nifty < ema50:
            symbol, strike = self.select_strike(nifty, "PE")
            price = self.get_option_price(symbol, strike, nifty, "PE", data_state)
            return Signal(
                strategy=self.name,
                direction="PE",
                action="BUY",
                strike=symbol,
                confidence=0.80,
                rationale=f"MACD cross, Volume:{volume_ratio:.2f}x, Price below 50-EMA",
                entry_price=price,
                timestamp=data_state["timestamp"],
            )
        return None
