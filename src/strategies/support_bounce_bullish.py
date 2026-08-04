"""Price tests the 20-EMA (previous candle low touches/breaks it) then closes back above it on
volume, only when the broader 1H 50-EMA trend is also up."""
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
        ema50 = indicators.get("ema_50_1h")
        avg_volume = indicators.get("avg_volume")
        if ema20 is None or ema50 is None or avg_volume is None:
            return None

        current, prev = candles[-1], candles[-2]

        # Added the ema50 trend filter: without it, this bounced-buy on every 20-EMA reclaim even
        # against the broader trend ("dead cat bounce in a downtrend"), which a 90-day backtest
        # showed was the main driver of its stop-loss rate and drawdown. See docs/ARCHITECTURE.md.
        #
        # Also require the breakout candle to close strong (in the top 40% of its own range), not
        # just tick above the EMA — a weak close there is a half-hearted bounce likely to fail;
        # this was the difference between a small net loss and a solid profit in backtesting.
        candle_range = current.high - current.low
        closes_strong = candle_range <= 0 or (current.close - current.low) / candle_range >= 0.6

        # Tried tightening this to 1.2x average volume (this strategy's mirror,
        # ResistanceRejectionBearish, uses identical structural filters and performs much better,
        # so the gap looked like it might be a quality issue) — an isolated full-year test showed
        # it made things WORSE (P&L dropped ~72%, PF fell to near-breakeven): the extra volume
        # requirement filtered out more good trades than bad ones. Reverted. The gap vs its mirror
        # looks like a genuine market-regime asymmetry (support bounces are weaker setups than
        # resistance rejections in this dataset), not something this filter fixes.
        if (prev.low <= ema20 and current.close > ema20 and current.close > ema50
                and current.volume > avg_volume and closes_strong):
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
