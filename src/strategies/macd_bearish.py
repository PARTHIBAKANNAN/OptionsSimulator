"""MACD histogram crosses below zero on 15m (fast enough to give this strategy a real sample
size), confirmed by the slower 1H 50-EMA trend."""
from src.strategies.base_strategy import BaseStrategy, Signal


class MACDBearish(BaseStrategy):
    def __init__(self):
        super().__init__(name="MACD_BEARISH", direction="PE")

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        nifty = data_state.get("nifty_price")
        if nifty is None:
            return None

        macd_hist = indicators.get("macd_histogram_15m")
        macd_hist_prev = indicators.get("macd_histogram_15m_prev")
        ema50 = indicators.get("ema_50_1h")
        if None in (macd_hist, macd_hist_prev, ema50):
            return None

        # Mirror of MACDBullish's 15m-timeframe switch — see there and docs/ARCHITECTURE.md.
        if macd_hist < 0 and macd_hist_prev >= 0 and nifty < ema50:
            symbol, strike = self.select_strike(nifty, "PE")
            price = self.get_option_price(symbol, strike, nifty, "PE", data_state)
            return Signal(
                strategy=self.name,
                direction="PE",
                action="BUY",
                strike=symbol,
                confidence=0.80,
                rationale="MACD bearish cross, price below 50-EMA",
                entry_price=price,
                timestamp=data_state["timestamp"],
            )
        return None
