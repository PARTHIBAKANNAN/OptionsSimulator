"""RSI(14, 1H) oversold + Stochastic(15m) extreme oversold + price above 20-EMA + volume confirmation."""
from src.strategies.base_strategy import BaseStrategy, Signal


class RSIOversoldBullish(BaseStrategy):
    def __init__(self):
        super().__init__(name="RSI_OVERSOLD_BULLISH", direction="CE")

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        nifty = data_state.get("nifty_price")
        if nifty is None:
            return None

        rsi = indicators.get("rsi_1h")
        stoch_k = indicators.get("stochastic_k_15m")
        ema20 = indicators.get("ema_20_1h")
        volume_ratio = indicators.get("volume_ratio")
        if None in (rsi, stoch_k, ema20, volume_ratio):
            return None

        if rsi < 35 and stoch_k < 20 and nifty > ema20 and volume_ratio > 1.5:
            symbol, strike = self.select_strike(nifty, "CE")
            price = self.get_option_price(symbol, strike, nifty, "CE", data_state)
            return Signal(
                strategy=self.name,
                direction="CE",
                action="BUY",
                strike=symbol,
                confidence=0.75,
                rationale=f"RSI:{rsi:.1f} oversold, Stoch:{stoch_k:.1f}, Volume:{volume_ratio:.2f}x",
                entry_price=price,
                timestamp=data_state["timestamp"],
            )
        return None
