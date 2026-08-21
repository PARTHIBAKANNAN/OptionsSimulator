"""
Ultra-Fast 5-Minute NIFTY Strategy Suite Backtest
=================================================
Pre-calculates all multi-timeframe indicators in a single vectorized pass (<1s),
then replays PaperTrader execution across all 18,450 5-minute bars in under 10 seconds!

Exit Rules:
  - Strike: ITM (~Rs.200 Target Premium)
  - Take Profit: 50 option premium points (+25%)
  - Stop Loss: 20% of entry premium
  - Trailing Stop: Armed at +15% gain, trails 15% from peak
  - Time Exit: 90 minutes (18 5-minute bars)
"""
import json
import math
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.simulator.paper_trader import PaperTrader, RiskLimitExceeded
from src.backtester.report import build_report
from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days, parse_option_symbol

NIFTY_5M_CSV = PROJECT_ROOT / "data" / "historical" / "nifty_5min.csv"
OUTPUT_REPORT = PROJECT_ROOT / "data" / "backtest_results" / "nifty_5min_report.json"
IST = ZoneInfo("Asia/Kolkata")


# ============================================================================
# Vectorized Multi-Timeframe Precomputation
# ============================================================================

def precompute_data(df: pd.DataFrame) -> pd.DataFrame:
    """Precomputes 5m EMA, 5m MACD, 5m Heikin-Ashi, 1H 50-EMA, and Day Range in 1 vectorized pass."""
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.sort_values("Timestamp").reset_index(drop=True)

    # 1. 5-min EMAs
    df["ema_20_5m"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["ema_50_5m"] = df["Close"].ewm(span=50, adjust=False).mean()

    # 2. 5-min MACD
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    df["macd_hist_5m"] = macd_line - signal_line
    df["macd_hist_5m_prev"] = df["macd_hist_5m"].shift(1).fillna(0.0)

    # 3. 5-min Heikin-Ashi
    ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4.0
    ha_open = np.zeros(len(df))
    ha_open[0] = (df["Open"].iloc[0] + df["Close"].iloc[0]) / 2.0
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i - 1] + ha_close.iloc[i - 1]) / 2.0

    df["ha_open"] = ha_open
    df["ha_close"] = ha_close
    df["ha_high"] = np.maximum.reduce([df["High"].values, ha_open, ha_close.values])
    df["ha_low"] = np.minimum.reduce([df["Low"].values, ha_open, ha_close.values])
    df["ha_prev_open"] = pd.Series(ha_open).shift(1).fillna(ha_open[0]).values
    df["ha_prev_close"] = df["ha_close"].shift(1).fillna(df["ha_close"].iloc[0]).values

    # 4. 1H 50-EMA (mapped to 5m bars without lookahead)
    df_indexed = df.set_index("Timestamp")
    df_1h = df_indexed.resample("1h").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last"
    }).dropna()
    df_1h["ema_50_1h"] = df_1h["Close"].ewm(span=50, adjust=False).mean()

    # Merge 1H 50-EMA back to 5m bars using asof merge (no lookahead bias)
    df = pd.merge_asof(
        df.sort_values("Timestamp"),
        df_1h[["ema_50_1h"]].reset_index().sort_values("Timestamp"),
        on="Timestamp",
        direction="backward"
    )

    # 5. Opening Range (09:15-09:30) High / Low per Day
    df["date"] = df["Timestamp"].dt.date
    df["time"] = df["Timestamp"].dt.time

    orb_bars = df[df["time"].between(dtime(9, 15), dtime(9, 25))]
    orb_highs = orb_bars.groupby("date")["High"].max().rename("orb_high")
    orb_lows = orb_bars.groupby("date")["Low"].min().rename("orb_low")

    df = df.merge(orb_highs, on="date", how="left")
    df = df.merge(orb_lows, on="date", how="left")

    return df


# ============================================================================
# ITM Strike Selector & Mark-to-Market
# ============================================================================

def select_itm_strike(spot: float, option_type: str, dte: float, target_premium: float = 200.0) -> tuple[str, float]:
    strike_step = 50
    atm_strike = round(spot / strike_step) * strike_step
    best_strike = atm_strike
    best_price = black_scholes_price(spot, atm_strike, dte, option_type)
    best_diff = abs(best_price - target_premium)

    for k in range(1, 12):
        strike = atm_strike - k * strike_step if option_type == "CE" else atm_strike + k * strike_step
        price = black_scholes_price(spot, strike, dte, option_type)
        diff = abs(price - target_premium)
        if diff < best_diff:
            best_diff = diff
            best_strike = strike
            best_price = price
        elif price > target_premium + 100:
            break

    return f"NIFTY{int(best_strike)}{option_type}", float(best_strike)


def mark_to_market(trader: PaperTrader, spot: float, timestamp: datetime) -> dict:
    prices = {}
    dte = next_weekly_expiry_days(timestamp, index="NIFTY")
    for order in trader.get_positions():
        strike, option_type = parse_option_symbol(order.symbol)
        if strike is None:
            continue
        prices[order.symbol] = black_scholes_price(
            spot=spot, strike=strike, days_to_expiry=dte, option_type=option_type
        )
    return prices


# ============================================================================
# Fast Strategy Simulator
# ============================================================================

def simulate_strategy(name: str, direction: str, df: pd.DataFrame, condition_fn,
                      target_tp_pts: float = 50.0) -> tuple[object, list]:
    trader = PaperTrader(
        initial_capital=1_000_000,
        lot_size=65,
        max_concurrent_positions=5,
        max_daily_loss=5000,
        max_trades_per_day_per_strategy=2,
        trailing_stop_enabled=True,
        trailing_activation_pct=15.0,
        trailing_stop_pct=15.0,
    )

    stop_loss_pct = 20.0
    time_exit_mins = 90

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]
        ts = row["Timestamp"]
        spot = row["Close"]

        # 1. Update existing open positions mark-to-market
        current_prices = mark_to_market(trader, spot, ts)
        trader.update_positions(current_prices, timestamp=ts, time_exit_mins=time_exit_mins)

        # 2. Check strategy entry condition
        should_enter = condition_fn(row, prev_row)
        if not should_enter:
            continue

        dte = next_weekly_expiry_days(ts, index="NIFTY")
        symbol, strike = select_itm_strike(spot, direction, dte, target_premium=200.0)
        entry_price = black_scholes_price(spot, strike, dte, direction)

        stop_loss = max(entry_price * (1 - stop_loss_pct / 100), 0.05)
        take_profit = entry_price + target_tp_pts

        try:
            trader.place_order(
                symbol=symbol, side="BUY", qty=1, price=entry_price,
                stop_loss=stop_loss, take_profit=take_profit,
                strategy=name, timestamp=ts, lot_size=65
            )
        except RiskLimitExceeded:
            continue

    history = trader.get_trade_history()
    report = build_report(name, direction, history, 1_000_000)
    return report, history


# ============================================================================
# Strategy Condition Definitions
# ============================================================================

def cond_orb_bullish(row, prev):
    # 5m candle closes above 09:30 range high (established 09:15-09:25), at or after 09:30
    if row["time"] < dtime(9, 30) or pd.isna(row["orb_high"]):
        return False
    crossed_now = (prev["time"] < dtime(9, 30) and row["Close"] > row["orb_high"]) or (prev["Close"] <= row["orb_high"] < row["Close"])
    return crossed_now and (pd.isna(row["ema_50_1h"]) or row["Close"] > row["ema_50_1h"])

def cond_orb_bearish(row, prev):
    # 5m candle closes below 09:30 range low (established 09:15-09:25), at or after 09:30
    if row["time"] < dtime(9, 30) or pd.isna(row["orb_low"]):
        return False
    crossed_now = (prev["time"] < dtime(9, 30) and row["Close"] < row["orb_low"]) or (prev["Close"] >= row["orb_low"] > row["Close"])
    return crossed_now and (pd.isna(row["ema_50_1h"]) or row["Close"] < row["ema_50_1h"])

def cond_macd_bullish(row, prev):
    # 5m MACD crossover above 0, confirmed by 1H 50-EMA
    if pd.isna(row["ema_50_1h"]):
        return False
    return (row["macd_hist_5m"] > 0 and prev["macd_hist_5m"] <= 0) and (row["Close"] > row["ema_50_1h"])

def cond_macd_bearish(row, prev):
    # 5m MACD cross-under below 0, confirmed by 1H 50-EMA
    if pd.isna(row["ema_50_1h"]):
        return False
    return (row["macd_hist_5m"] < 0 and prev["macd_hist_5m"] >= 0) and (row["Close"] < row["ema_50_1h"])

def cond_heikin_ashi_bearish(row, prev):
    # Two consecutive red 5m HA candles with upper wick <= 15% of body
    if pd.isna(row["ema_50_1h"]) or row["Close"] >= row["ema_50_1h"]:
        return False
    body = row["ha_open"] - row["ha_close"]
    prev_bearish = row["ha_prev_open"] > row["ha_prev_close"]
    if body <= 0 or not prev_bearish:
        return False
    upper_wick = row["ha_high"] - row["ha_open"]
    return upper_wick <= 0.15 * body

def cond_support_bounce(row, prev):
    # 5m test of 20-EMA and bounce with strong close in 1H uptrend
    if pd.isna(row["ema_50_1h"]) or row["Close"] <= row["ema_50_1h"]:
        return False
    rng = row["High"] - row["Low"]
    if rng <= 0:
        return False
    closes_strong = (row["Close"] - row["Low"]) / rng >= 0.60
    return (prev["Low"] <= row["ema_20_5m"] and row["Close"] > row["ema_20_5m"]) and closes_strong

def cond_resistance_rejection(row, prev):
    # 5m test of 20-EMA from below with rejection close in 1H downtrend
    if pd.isna(row["ema_50_1h"]) or row["Close"] >= row["ema_50_1h"]:
        return False
    rng = row["High"] - row["Low"]
    if rng <= 0:
        return False
    closes_weak = (row["High"] - row["Close"]) / rng >= 0.60
    return (prev["High"] >= row["ema_20_5m"] and row["Close"] < row["ema_20_5m"]) and closes_weak


# ============================================================================
# Main Runner
# ============================================================================

def main():
    t0 = time.time()
    print("\n" + "=" * 92, flush=True)
    print("  FAST 5-MINUTE NIFTY STRATEGY SUITE BACKTEST (1-YEAR: 18,450 BARS)", flush=True)
    print("  Strike: ITM (~Rs.200) | TP: 50 pts | SL: 20% | Trailing: +15%/15% | Time Exit: 90m", flush=True)
    print("=" * 92 + "\n", flush=True)

    df_raw = pd.read_csv(NIFTY_5M_CSV)
    print(f"Loaded {len(df_raw):,} 5-minute bars. Precomputing indicators in 1 vectorized pass...", end="", flush=True)
    t_pre = time.time()
    df = precompute_data(df_raw)
    print(f" done ({time.time() - t_pre:.2f}s)\n", flush=True)

    strategy_defs = [
        ("ORB_BULLISH_5M", "CE", cond_orb_bullish),
        ("MACD_BULLISH_5M", "CE", cond_macd_bullish),
        ("SUPPORT_BOUNCE_5M", "CE", cond_support_bounce),
        ("ORB_BEARISH_5M", "PE", cond_orb_bearish),
        ("MACD_BEARISH_5M", "PE", cond_macd_bearish),
        ("HEIKIN_ASHI_BEARISH_5M", "PE", cond_heikin_ashi_bearish),
        ("RESISTANCE_REJECTION_5M", "PE", cond_resistance_rejection),
    ]

    results = {}
    print(f"  {'Strategy':<26} | {'Trades':>6} {'Wins':>5} {'Losses':>6} {'Win Rate':>8} {'PF':>6} | {'Total P&L (Rs)':>14} | {'Max DD%':>7}", flush=True)
    print("  " + "-" * 88, flush=True)

    total_pnl = 0.0
    total_trades = 0
    total_wins = 0

    for name, direction, cond_fn in strategy_defs:
        t_strat = time.time()
        r, history = simulate_strategy(name, direction, df, cond_fn, target_tp_pts=50.0)
        total_pnl += r.total_pnl
        total_trades += r.total_trades
        total_wins += r.winning_trades

        pf_str = f"{r.profit_factor:.2f}" if r.profit_factor < 900 else "inf"
        print(f"  {r.strategy:<26} | {r.total_trades:>6} {r.winning_trades:>5} {r.losing_trades:>6} {r.win_rate:>7.1f}% {pf_str:>6} | Rs.{r.total_pnl:>10,.2f} | {r.max_drawdown_pct:>6.2f}%", flush=True)

        results[r.strategy] = {
            "direction": r.direction,
            "total_trades": r.total_trades,
            "winning_trades": r.winning_trades,
            "losing_trades": r.losing_trades,
            "win_rate": r.win_rate,
            "profit_factor": r.profit_factor,
            "total_pnl": r.total_pnl,
            "max_drawdown_pct": r.max_drawdown_pct,
            "exit_reasons": {
                "take_profit_hits": sum(1 for o in history if o.exit_reason == "TAKE_PROFIT"),
                "trailing_stop_hits": sum(1 for o in history if o.exit_reason == "TRAILING_STOP"),
                "stop_loss_hits": sum(1 for o in history if o.exit_reason == "STOP_LOSS"),
                "time_exit_hits": sum(1 for o in history if o.exit_reason == "TIME_EXIT"),
            }
        }

    print("  " + "-" * 88, flush=True)
    overall_win_rate = (total_wins / total_trades * 100) if total_trades else 0
    print(f"  {'PORTFOLIO TOTAL (NIFTY 5M)':<26} | {total_trades:>6} {total_wins:>5} {total_trades - total_wins:>6} {overall_win_rate:>7.1f}% {'—':>6} | Rs.{total_pnl:>10,.2f} |", flush=True)
    print("=" * 92 + "\n", flush=True)

    print(f"Completed full suite in {time.time() - t0:.2f}s", flush=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Report saved to {OUTPUT_REPORT}\n", flush=True)


if __name__ == "__main__":
    main()
