"""Mirror of SupportBounceBullish: price tests the 20-EMA from above and closes back below it on
volume, only when the broader 1H 50-EMA trend is also down."""
from typing import Optional

from src.strategies.base_strategy import BaseStrategy, Signal


class ResistanceRejectionBearish(BaseStrategy):
    def __init__(self, name: str = "RESISTANCE_REJECTION_BEARISH", strike_step: int = 50, underlying: str = "NIFTY"):
        super().__init__(name=name, direction="PE", strike_step=strike_step, underlying=underlying)

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        ema20 = indicators.get("ema_20_1h") or indicators.get("ema_20_5m") or indicators.get("ema_20")
        ema50 = indicators.get("ema_50_1h") or indicators.get("ema_50_5m") or indicators.get("ema_20_5m")
        avg_volume = indicators.get("avg_volume")
        if ema20 is None or ema50 is None:
            return None

        current, prev = candles[-1], candles[-2]
        candle_range = current.high - current.low
        if candle_range <= 0 or current.close <= 0:
            return None

        closes_strong = (current.high - current.close) / candle_range >= 0.60
        volume_confirmed = avg_volume is None or current.volume > avg_volume

        if (prev.high >= ema20 and current.close < ema20 and current.close < ema50
                and volume_confirmed and closes_strong):
            spot = current.close
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name,
                direction="PE",
                action="BUY",
                strike=symbol,
                confidence=0.70,
                rationale=f"Resistance rejection at 20-EMA, Close:{current.close:.1f} < EMA:{ema20:.1f}",
                entry_price=price,
                timestamp=ts,
                underlying=self.underlying,
            )
        return None
