"""RSI(14, 1H) oversold + Stochastic(15m) extreme oversold + price above both the 20-EMA and the
slower 50-EMA (medium- and longer-term uptrend agreement) + volume confirmation."""
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
        ema50 = indicators.get("ema_50_1h")
        volume_ratio = indicators.get("volume_ratio")
        if None in (rsi, stoch_k, ema20, ema50, volume_ratio):
            return None

        # Thresholds loosened from the textbook 35/20/1.5x: a 90-day backtest showed the original
        # 4-way conjunction essentially never co-occurs (0 trades) — see docs/ARCHITECTURE.md.
        #
        # Added the ema50 filter mirroring RSIOverboughtBearish's fix: a full-year backtest showed
        # this strategy had zero genuine out-of-sample edge (only profitable on the exact 90-day
        # window it was originally tuned on) — buying RSI dips without confirming the BROADER
        # trend (not just the 20-EMA) let it buy into stalling/rolling-over moves. Its mirror
        # already required this; this one didn't. See docs/ARCHITECTURE.md.
        if rsi < 45 and stoch_k < 30 and nifty >= ema20 * 0.995 and nifty > ema50 and volume_ratio > 1.1:
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
                underlying=self.underlying,
            )
        return None
