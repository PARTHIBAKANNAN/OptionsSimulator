# Strategies

Six intraday strategies run in parallel: 3 bullish (buy CE), 3 bearish (buy PE). Each strategy
evaluates independently on every tick/candle and produces at most one `Signal` every 5 minutes
(cooldown enforced in `StrategyEngine`). All entries are ATM strikes.

## Bullish (CE)

### `RSI_OVERSOLD_BULLISH`
Oversold bounce. Fires when:
- RSI(14, 1H) < 35
- Stochastic %K(14,3,3, 15m) < 20
- NIFTY price > 20-EMA (1H) — still in uptrend structure
- Volume ratio > 1.5x average

Confidence: 0.75

> **Observed on the May–Aug 2026 backtest data:** this strategy never fired — not a bug. Whenever
> RSI(1H) < 35 and Stoch(15m) < 20 occurred, NIFTY was consistently 250–400 points *below* its own
> 20-EMA (never above), i.e. genuinely in a drawdown, not a shallow pullback within an uptrend. The
> "oversold bounce within an uptrend" pattern this strategy targets apparently didn't occur in this
> particular 63-day window. Worth re-checking against a different period before concluding the
> strategy itself is broken.

### `MACD_BULLISH`
Momentum cross with volume confirmation. Fires when:
- MACD histogram (1H) crosses above zero this candle (was ≤0, now >0)
- Volume ratio (5m) > 2.0x average
- NIFTY price > 50-EMA (1H)

Confidence: 0.80

### `SUPPORT_BOUNCE_BULLISH`
Price tests the 20-EMA and holds. Fires when:
- Previous candle's low touched/broke the 20-EMA (1H)
- Current candle closes above the 20-EMA
- Current candle's volume > 20-period average volume

Confidence: 0.70

## Bearish (PE)

### `RSI_OVERBOUGHT_BEARISH`
Mirror of `RSI_OVERSOLD_BULLISH`. Fires when RSI(14,1H) > 65, Stochastic %K(15m) > 80, price < 20-EMA,
volume ratio > 1.5x. Confidence: 0.75.

### `MACD_BEARISH`
Mirror of `MACD_BULLISH`. Fires when the MACD histogram (1H) crosses below zero, volume ratio (5m)
> 2.0x, price < 50-EMA. Confidence: 0.80.

### `RESISTANCE_REJECTION_BEARISH`
Mirror of `SUPPORT_BOUNCE_BULLISH`. Fires when the previous candle's high touched/broke the 20-EMA
and the current candle closes back below it on above-average volume. Confidence: 0.70.

> This strategy isn't in the original `IMPLEMENTATION_PLAN.md` Phase 2 spec (which only defined 5
> strategies: 3 CE + 2 PE) — added to match the 3 CE + 3 PE target every other planning doc
> describes. See `docs/ARCHITECTURE.md`.

## Risk parameters (`config/risk_params.json`)

| Parameter | Default | Meaning |
|---|---|---|
| `qty_per_signal` | 1 | Contracts per signal |
| `lot_size` | 65 | NIFTY lot size |
| `max_concurrent_positions` | 5 | Hard cap on open positions at once |
| `max_daily_loss` | ₹5,000 | Trading halts for the day once realized loss hits this |
| `max_trades_per_day_per_strategy` | 2 | Each strategy may open at most this many new positions per calendar day |
| `stop_loss_pct` | 20 | Stop-loss as a % of entry premium (not index points) |
| `take_profit_pts` | 150 | **Option premium** points above entry |
| `time_exit_mins` | 120 | Force-close any position still open after this long |
| `trailing_stop_enabled` | true | Once armed, trails the stop below the peak premium instead of relying only on `take_profit_pts` |
| `trailing_activation_pct` | 10 | Minimum profit (% of entry) before the trailing stop arms |
| `trailing_stop_pct` | 15 | Distance the trailing stop trails below the peak premium once armed |

## Backtest ranking

`src/backtester/report.py` ranks each direction (CE/PE) by profit factor, then win rate, and selects
the top 3 of each for `data/backtest_results/report.json`. This ranking is a starting point, not a
verdict — validate on out-of-sample data before trusting it for live paper trading.
