"""MACD histogram crosses above zero on 15m (fast enough to give this strategy a real sample
size), confirmed by the slower 1H 50-EMA trend."""
from src.strategies.base_strategy import BaseStrategy, Signal


class MACDBullish(BaseStrategy):
    def __init__(self, name: str = "MACD_BULLISH", strike_step: int = 50, underlying: str = "NIFTY"):
        super().__init__(name=name, direction="CE", strike_step=strike_step, underlying=underlying)

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

        # Switched from the 1H histogram (crossed only ~1-4 times in a 90-day backtest — too thin
        # a sample to trust) to 15m, which gives ~4x more bars to cross on, while still requiring
        # agreement with the slower 1H 50-EMA trend so this stays a trend-following signal, not
        # noise. Also dropped the same-candle volume-spike requirement — see docs/ARCHITECTURE.md.
        if macd_hist > 0 and macd_hist_prev <= 0 and nifty > ema50:
            symbol, strike = self.select_strike(nifty, "CE")
            price = self.get_option_price(symbol, strike, nifty, "CE", data_state)
            return Signal(
                strategy=self.name,
                direction="CE",
                action="BUY",
                strike=symbol,
                confidence=0.80,
                rationale="MACD bullish cross, price above 50-EMA",
                entry_price=price,
                timestamp=data_state["timestamp"],
            )
        return None
