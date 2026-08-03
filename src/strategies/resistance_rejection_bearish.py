"""Mirror of SupportBounceBullish: price tests the 20-EMA from above and closes back below it on volume."""
from src.strategies.base_strategy import BaseStrategy, Signal


class ResistanceRejectionBearish(BaseStrategy):
    def __init__(self):
        super().__init__(name="RESISTANCE_REJECTION_BEARISH", direction="PE")

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

        if prev.high >= ema20 and current.close < ema20 and current.volume > avg_volume:
            nifty = current.close
            symbol, strike = self.select_strike(nifty, "PE")
            price = self.get_option_price(symbol, strike, nifty, "PE", data_state)
            return Signal(
                strategy=self.name,
                direction="PE",
                action="BUY",
                strike=symbol,
                confidence=0.70,
                rationale=f"Resistance rejection at 20-EMA, Close:{current.close:.1f} < EMA:{ema20:.1f}",
                entry_price=price,
                timestamp=data_state["timestamp"],
            )
        return None
