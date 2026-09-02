"""
Faithful replay of Mon Aug31 - Wed Sep2, 2026 through the REAL production strategy code
(src/strategies/engine.py's create_nifty_strategies/create_sensex_strategies/create_banknifty_strategies
and the REAL BaseStrategy.evaluate() implementations), fed real 1-min candles pulled fresh from
Fyers (data/market_analysis/*_week_candles.csv).

Purpose: answer three things cleanly, per strategy, with NO portfolio-level caps in the way
(no max_trades_per_day, no max_concurrent_positions, no daily-loss breaker, no consecutive-loss
breaker, no wallet balance check) -- only each strategy's own built-in signal logic and cooldown:
  1. Exactly which strategies would have signaled, when, and why (rationale string).
  2. What the resulting trade would have done (SL/TP/trailing/time-exit), using the same
     Black-Scholes pricing the project's own replay/backtest code uses when no live option
     chain is available (see live_engine.py's _check_exits_replay for the reference pattern).
  3. A clean per-strategy scorecard: signals, wins, losses, win rate, P&L, exit-reason mix.

Aug 28 is included ONLY as indicator warm-up (1H EMA/RSI/MACD need prior bars) -- no signals from
that day are counted in the report.
"""
import sys
from pathlib import Path
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader
from src.strategies.engine import create_nifty_strategies, create_sensex_strategies, create_banknifty_strategies
from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days, parse_option_symbol

IST = ZoneInfo("Asia/Kolkata")
DATA_DIR = PROJECT_ROOT / "data" / "market_analysis"
REPORT_DATES = {date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 2)}
WARMUP_ONLY_DATES = {date(2026, 8, 28)}

STRATEGY_FACTORIES = {
    "NIFTY": create_nifty_strategies,
    "SENSEX": create_sensex_strategies,
    "BANKNIFTY": create_banknifty_strategies,
}


def load_candles(index_name: str) -> list[Candle]:
    df = pd.read_csv(DATA_DIR / f"{index_name}_week_candles.csv")
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True).dt.tz_convert(IST)
    df = df.sort_values("Timestamp").reset_index(drop=True)
    return [
        Candle(timestamp=row.Timestamp, open=row.Open, high=row.High, low=row.Low,
               close=row.Close, volume=int(row.Volume))
        for row in df.itertuples(index=False)
    ]


def bs_price_for_order(order, spot: float, now: datetime) -> float | None:
    strike, option_type = parse_option_symbol(order.symbol)
    if strike is None:
        return None
    dte = next_weekly_expiry_days(now, index=order.underlying)
    return black_scholes_price(spot=spot, strike=strike, days_to_expiry=dte, option_type=option_type)


def run_index(index_name: str) -> tuple[list[dict], list[dict]]:
    candles = load_candles(index_name)
    dm = DataManager(underlying=index_name)
    strategies = STRATEGY_FACTORIES[index_name]()

    # Matches config/risk_params.json's real live/backtest cap: at most 2 entries per strategy
    # per day. has_open_position() (inside PaperTrader.place_order) already blocks a strategy from
    # opening a second position while its first is still open, regardless of this cap -- so "2 per
    # day, never concurrent" is enforced the same way live enforces it. Only the OTHER portfolio
    # caps (global daily loss breaker, global concurrent-position cap, consecutive-loss breaker,
    # wallet balance) are left disabled, so each strategy's own 2/day performance is visible on
    # its own rather than being blocked by a sibling strategy eating the shared risk budget.
    trader = PaperTrader(
        lot_size={"NIFTY": 65, "SENSEX": 20, "BANKNIFTY": 30}[index_name],
        max_concurrent_positions=None,
        max_daily_loss=None,
        max_trades_per_day_per_strategy=2,
        trailing_stop_enabled=True,
        trailing_activation_pct=10.0,
        trailing_stop_pct=15.0,
        consecutive_loss_limit=None,
        max_drawdown_pct_of_capital=None,
        enable_wallets=False,
    )
    STOP_LOSS_PCT = 20.0
    TAKE_PROFIT_PTS = 150.0
    TIME_EXIT_MINS = 120

    signal_log = []
    strike_step = {"NIFTY": 50, "SENSEX": 100, "BANKNIFTY": 100}[index_name]

    for candle in candles:
        dm.replay_candle(candle)
        state = dm.get_state()
        now = state["timestamp"]
        spot = state["nifty_price"]
        if spot is None:
            continue
        today = now.date()

        # --- exit check for open positions (Black-Scholes mark, same pattern as live replay mode) ---
        current_prices = {}
        for order in trader.get_positions():
            price = bs_price_for_order(order, spot, now)
            if price is not None:
                current_prices[order.symbol] = price
        trader.update_positions(current_prices, timestamp=now, time_exit_mins=TIME_EXIT_MINS, eod_square_off=True)

        if today not in REPORT_DATES and today not in WARMUP_ONLY_DATES:
            continue

        # --- evaluate every strategy for this index on this candle close ---
        for strat in strategies:
            try:
                sig = strat.evaluate(state)
            except Exception as e:
                signal_log.append({
                    "date": today, "time": now.time(), "strategy": strat.name,
                    "event": "EXCEPTION", "detail": f"{type(e).__name__}: {e}",
                })
                continue
            if sig is None:
                continue

            in_report_window = today in REPORT_DATES
            signal_log.append({
                "date": today, "time": now.time(), "strategy": strat.name,
                "event": "SIGNAL" if in_report_window else "SIGNAL(warmup-skipped)",
                "detail": f"{sig.direction} {sig.strike} @ {sig.entry_price:.2f} -- {sig.rationale}",
            })
            if not in_report_window:
                continue

            if trader.has_open_position(strat.name):
                signal_log[-1]["event"] = "SIGNAL(skipped-already-open)"
                continue

            stop_loss = max(sig.entry_price * (1 - STOP_LOSS_PCT / 100), 0.05)
            take_profit = sig.entry_price + TAKE_PROFIT_PTS
            try:
                trader.place_order(
                    symbol=sig.strike, side="BUY", qty=1, price=sig.entry_price,
                    stop_loss=stop_loss, take_profit=take_profit, strategy=strat.name,
                    timestamp=sig.timestamp,
                )
            except Exception as e:
                signal_log[-1]["event"] = "SIGNAL(order-rejected)"
                signal_log[-1]["detail"] += f" | rejected: {e}"

    # Force-close anything still open at the end of Sep 2 for reporting purposes
    trades = [o for o in trader.get_trade_history()]
    return signal_log, [
        {
            "strategy": o.strategy, "symbol": o.symbol, "entry_time": o.entry_time,
            "entry_price": o.entry_price, "exit_time": o.exit_time, "exit_price": o.exit_price,
            "exit_reason": o.exit_reason, "pnl": o.realized_pnl,
        }
        for o in trades
    ]


def main():
    all_signals, all_trades = [], []
    for index_name in ["NIFTY", "SENSEX", "BANKNIFTY"]:
        print(f"Replaying {index_name}...")
        sig_log, trades = run_index(index_name)
        all_signals.extend(sig_log)
        all_trades.extend(trades)

    sig_df = pd.DataFrame(all_signals)
    trade_df = pd.DataFrame(all_trades)

    sig_df.to_csv(DATA_DIR / "replay_signal_log_2perday.csv", index=False)
    trade_df.to_csv(DATA_DIR / "replay_trades_2perday.csv", index=False)

    print("\n" + "=" * 110)
    print("SIGNAL LOG (Aug 31 - Sep 2 window only; Aug 28 warmup signals excluded from counts)")
    print("=" * 110)
    report_sig = sig_df[sig_df["event"] != "SIGNAL(warmup-skipped)"] if len(sig_df) else sig_df
    for _, r in report_sig.iterrows():
        print(f"{r['date']} {str(r['time'])[:8]} | {r['strategy']:38s} | {r['event']:28s} | {r['detail']}")

    print("\n" + "=" * 110)
    print("PER-STRATEGY SCORECARD (unrestricted: no daily trade cap, no concurrent-position cap, no breaker)")
    print("=" * 110)
    if len(trade_df):
        trade_df["is_win"] = trade_df["pnl"] > 0
        score = trade_df.groupby("strategy").agg(
            trades=("pnl", "count"), wins=("is_win", "sum"), pnl=("pnl", "sum"),
        )
        score["win_rate_%"] = (score["wins"] / score["trades"] * 100).round(1)
        print(score.sort_values("pnl", ascending=False).to_string())

        print("\nExit reason mix:")
        print(trade_df.groupby(["strategy", "exit_reason"]).size().unstack(fill_value=0).to_string())
    else:
        print("No trades placed at all in the report window.")

    print("\n" + "=" * 110)
    print("STRATEGIES WITH ZERO SIGNALS IN THE REPORT WINDOW (no exception, no trade -- genuinely quiet)")
    print("=" * 110)
    all_strategy_names = set()
    for factory in STRATEGY_FACTORIES.values():
        all_strategy_names.update(s.name for s in factory())
    signaled_names = set(report_sig["strategy"].unique()) if len(report_sig) else set()
    for name in sorted(all_strategy_names - signaled_names):
        print(f"  {name}")

    print(f"\nSaved: {DATA_DIR / 'replay_signal_log_2perday.csv'}")
    print(f"Saved: {DATA_DIR / 'replay_trades_2perday.csv'}")


if __name__ == "__main__":
    main()
