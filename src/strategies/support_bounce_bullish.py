"""Price tests the 20-EMA (previous candle low touches/breaks it) then closes back above it on volume."""
from src.strategies.base_strategy import BaseStrategy, Signal


class SupportBounceBullish(BaseStrategy):
    def __init__(self):
        super().__init__(name="SUPPORT_BOUNCE_BULLISH", direction="CE")

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        ema20 = indicators.get("ema_20_1h")
        avg_volume = indicators.get("avg_volume")
        if ema20 is None or avg_volume is None:
            return None

        current, prev = candles[-1], candles[-2]

        if prev.low <= ema20 and current.close > ema20 and current.volume > avg_volume:
            nifty = current.close
            symbol, strike = self.select_strike(nifty, "CE")
            price = self.get_option_price(symbol, strike, nifty, "CE", data_state)
            return Signal(
                strategy=self.name,
                direction="CE",
                action="BUY",
                strike=symbol,
                confidence=0.70,
                rationale=f"Support bounce at 20-EMA, Close:{current.close:.1f} > EMA:{ema20:.1f}",
                entry_price=price,
                timestamp=data_state["timestamp"],
            )
        return None
