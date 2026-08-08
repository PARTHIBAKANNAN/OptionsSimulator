"""Mirror of RSIOversoldBullish: RSI(1H) overbought + Stochastic(15m) extreme overbought + price
below both the 20-EMA and the slower 50-EMA (medium- and longer-term downtrend agreement)."""
from src.strategies.base_strategy import BaseStrategy, Signal


class RSIOverboughtBearish(BaseStrategy):
    def __init__(self):
        super().__init__(name="RSI_OVERBOUGHT_BEARISH", direction="PE")

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        nifty = data_state.get("nifty_price")
        if nifty is None:
            return None

        rsi = indicators.get("rsi_1h")
        stoch_k = indicators.get("stochastic_k_15m")
        ema20 = indicators.get("ema_20_1h")
        ema50 = indicators.get("ema_50_1h")
        volume_ratio = indicators.get("volume_ratio")
        if None in (rsi, stoch_k, ema20, ema50, volume_ratio):
            return None

        # Added the ema50 filter on top of the existing loosened thresholds (see
        # RSIOversoldBullish/docs/ARCHITECTURE.md): this dataset trended broadly bullish, so
        # bearish trades fighting BOTH the short and long trend were the biggest drawdown driver.
        #
        # Tried loosening stoch_k 65->60 to get more frequency (this is our best-quality strategy
        # by PF/win-rate but the thinnest by trade count). An isolated full-year test showed it was
        # a pure no-op: the 2 extra trades it unlocked both closed at exactly breakeven via the
        # trailing-stop clamp, with zero effect on P&L, PF, or drawdown. Reverted — no reason to
        # carry a deviation that provably changes nothing.
        if rsi > 55 and stoch_k > 65 and nifty <= ema20 * 1.005 and nifty < ema50 and volume_ratio > 1.1:
            symbol, strike = self.select_strike(nifty, "PE")
            price = self.get_option_price(symbol, strike, nifty, "PE", data_state)
            return Signal(
                strategy=self.name,
                direction="PE",
                action="BUY",
                strike=symbol,
                confidence=0.75,
                rationale=f"RSI:{rsi:.1f} overbought, Stoch:{stoch_k:.1f}, Volume:{volume_ratio:.2f}x",
                entry_price=price,
                timestamp=data_state["timestamp"],
                underlying=self.underlying,
            )
        return None
