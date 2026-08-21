"""
Comprehensive SENSEX Multi-Strategy Backtest Suite (CE & PE)
============================================================
Evaluates 12 distinct quantitative strategies across 1-year SENSEX historical data.
Uses ITM strike selection (~Rs.600 target premium, lot size = 20, strike step = 100).

Indicators Tested:
  - Opening Range Breakout (ORB 09:15-09:30)
  - MACD Histogram Momentum Crossovers (12, 26, 9)
  - EMA Support / Resistance Pullback Bounces (20-EMA / 50-EMA)
  - Heikin-Ashi Trend Continuations (wickless candles)
  - RSI + Stochastic Momentum Thrusts (RSI 14 / Stoch 14,3,3)
  - Bollinger Bands Volatility Squeeze Breakouts (20, 2.0 std)
"""
import json
import math
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.simulator.paper_trader import PaperTrader, RiskLimitExceeded
from src.backtester.report import build_report
from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days, parse_option_symbol

SENSEX_CSV = PROJECT_ROOT / "data" / "historical" / "sensex_1year.csv"
OUTPUT_REPORT = PROJECT_ROOT / "data" / "backtest_results" / "sensex_strategy_report.json"
SENSEX_LOT_SIZE = 20
SENSEX_STRIKE_STEP = 100


# ============================================================================
# Vectorized Precomputation across SENSEX Data
# ============================================================================

def precompute_sensex_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.sort_values("Timestamp").reset_index(drop=True)

    # 1. EMAs (20 and 50)
    df["ema_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["ema_50"] = df["Close"].ewm(span=50, adjust=False).mean()

    # 2. MACD (12, 26, 9)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    df["macd_hist"] = macd_line - signal_line
    df["macd_hist_prev"] = df["macd_hist"].shift(1).fillna(0.0)

    # 3. RSI (14)
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = (100 - (100 / (1 + rs))).fillna(50.0)
    df["rsi_prev"] = df["rsi"].shift(1).fillna(50.0)

    # 4. Stochastic (14, 3, 3)
    low14 = df["Low"].rolling(14).min()
    high14 = df["High"].rolling(14).max()
    raw_k = 100 * (df["Close"] - low14) / (high14 - low14).replace(0, np.nan)
    df["stoch_k"] = raw_k.rolling(3).mean().fillna(50.0)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean().fillna(50.0)

    # 5. Bollinger Bands (20, 2.0 std)
    bb_mid = df["Close"].rolling(20).mean()
    bb_std = df["Close"].rolling(20).std()
    df["bb_upper"] = bb_mid + 2.0 * bb_std
    df["bb_lower"] = bb_mid - 2.0 * bb_std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / bb_mid.replace(0, np.nan)
    df["bb_width_avg"] = df["bb_width"].rolling(20).mean()

    # 6. Heikin-Ashi
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

    # 7. 1H 50-EMA Trend Filter
    df_indexed = df.set_index("Timestamp")
    df_1h = df_indexed.resample("1h").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last"
    }).dropna()
    df_1h["ema_50_1h"] = df_1h["Close"].ewm(span=50, adjust=False).mean()

    df = pd.merge_asof(
        df.sort_values("Timestamp"),
        df_1h[["ema_50_1h"]].reset_index().sort_values("Timestamp"),
        on="Timestamp",
        direction="backward"
    )

    # 8. Opening Range (09:15-09:30) High / Low per Day
    df["date"] = df["Timestamp"].dt.date
    df["time"] = df["Timestamp"].dt.time

    orb_bars = df[df["time"].between(dtime(9, 15), dtime(9, 25))]
    orb_highs = orb_bars.groupby("date")["High"].max().rename("orb_high")
    orb_lows = orb_bars.groupby("date")["Low"].min().rename("orb_low")

    df = df.merge(orb_highs, on="date", how="left")
    df = df.merge(orb_lows, on="date", how="left")

    return df


# ============================================================================
# SENSEX ITM Strike Selector & Mark-to-Market
# ============================================================================

def select_sensex_itm_strike(spot: float, option_type: str, dte: float, target_premium: float = 600.0) -> tuple[str, float]:
    strike_step = SENSEX_STRIKE_STEP
    atm_strike = round(spot / strike_step) * strike_step
    best_strike = atm_strike
    best_price = black_scholes_price(spot, atm_strike, dte, option_type)
    best_diff = abs(best_price - target_premium)

    for k in range(1, 15):
        strike = atm_strike - k * strike_step if option_type == "CE" else atm_strike + k * strike_step
        price = black_scholes_price(spot, strike, dte, option_type)
        diff = abs(price - target_premium)
        if diff < best_diff:
            best_diff = diff
            best_strike = strike
            best_price = price
        elif price > target_premium + 200:
            break

    return f"SENSEX{int(best_strike)}{option_type}", float(best_strike)


def mark_to_market(trader: PaperTrader, spot: float, timestamp: datetime) -> dict:
    prices = {}
    dte = next_weekly_expiry_days(timestamp, index="SENSEX")
    for order in trader.get_positions():
        strike, option_type = parse_option_symbol(order.symbol)
        if strike is None:
            continue
        prices[order.symbol] = black_scholes_price(
            spot=spot, strike=strike, days_to_expiry=dte, option_type=option_type
        )
    return prices


# ============================================================================
# Simulator Engine
# ============================================================================

def simulate_sensex_strategy(name: str, direction: str, df: pd.DataFrame, condition_fn,
                             target_tp_pts: float = 150.0) -> tuple[object, list]:
    trader = PaperTrader(
        initial_capital=1_000_000,
        lot_size=SENSEX_LOT_SIZE,
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

        current_prices = mark_to_market(trader, spot, ts)
        trader.update_positions(current_prices, timestamp=ts, time_exit_mins=time_exit_mins)

        should_enter = condition_fn(row, prev_row)
        if not should_enter:
            continue

        dte = next_weekly_expiry_days(ts, index="SENSEX")
        symbol, strike = select_sensex_itm_strike(spot, direction, dte, target_premium=600.0)
        entry_price = black_scholes_price(spot, strike, dte, direction)

        stop_loss = max(entry_price * (1 - stop_loss_pct / 100), 0.05)
        take_profit = entry_price + target_tp_pts

        try:
            trader.place_order(
                symbol=symbol, side="BUY", qty=1, price=entry_price,
                stop_loss=stop_loss, take_profit=take_profit,
                strategy=name, timestamp=ts, lot_size=SENSEX_LOT_SIZE
            )
        except RiskLimitExceeded:
            continue

    history = trader.get_trade_history()
    report = build_report(name, direction, history, 1_000_000)
    return report, history


# ============================================================================
# Strategy Condition Library (6 Bullish CE & 6 Bearish PE)
# ============================================================================

# --- BULLISH (CE) ---

def cond_sensex_orb_bullish(row, prev):
    if row["time"] < dtime(9, 30) or pd.isna(row["orb_high"]):
        return False
    crossed = (prev["time"] < dtime(9, 30) and row["Close"] > row["orb_high"]) or (prev["Close"] <= row["orb_high"] < row["Close"])
    return crossed and (pd.isna(row["ema_50_1h"]) or row["Close"] > row["ema_50_1h"])

def cond_sensex_macd_bullish(row, prev):
    if pd.isna(row["ema_50_1h"]):
        return False
    return (row["macd_hist"] > 0 and prev["macd_hist"] <= 0) and (row["Close"] > row["ema_50_1h"])

def cond_sensex_support_bounce(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] <= row["ema_50_1h"]:
        return False
    rng = row["High"] - row["Low"]
    if rng <= 0:
        return False
    closes_strong = (row["Close"] - row["Low"]) / rng >= 0.60
    return (prev["Low"] <= row["ema_20"] and row["Close"] > row["ema_20"]) and closes_strong

def cond_sensex_heikin_ashi_bullish(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] <= row["ema_50_1h"]:
        return False
    body = row["ha_close"] - row["ha_open"]
    prev_bullish = row["ha_prev_close"] > row["ha_prev_open"]
    if body <= 0 or not prev_bullish:
        return False
    lower_wick = row["ha_open"] - row["ha_low"]
    return lower_wick <= 0.15 * body

def cond_sensex_rsi_momentum_bullish(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] <= row["ema_50_1h"]:
        return False
    rsi_cross = row["rsi"] >= 52 and prev["rsi"] < 52
    stoch_bull = row["stoch_k"] > row["stoch_d"]
    return rsi_cross and stoch_bull

def cond_sensex_bb_squeeze_bullish(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] <= row["ema_50_1h"]:
        return False
    was_squeezed = prev["bb_width"] < prev["bb_width_avg"]
    breaks_upper = row["Close"] > row["bb_upper"]
    return was_squeezed and breaks_upper


# --- BEARISH (PE) ---

def cond_sensex_orb_bearish(row, prev):
    if row["time"] < dtime(9, 30) or pd.isna(row["orb_low"]):
        return False
    crossed = (prev["time"] < dtime(9, 30) and row["Close"] < row["orb_low"]) or (prev["Close"] >= row["orb_low"] > row["Close"])
    return crossed and (pd.isna(row["ema_50_1h"]) or row["Close"] < row["ema_50_1h"])

def cond_sensex_macd_bearish(row, prev):
    if pd.isna(row["ema_50_1h"]):
        return False
    return (row["macd_hist"] < 0 and prev["macd_hist"] >= 0) and (row["Close"] < row["ema_50_1h"])

def cond_sensex_resistance_rejection(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] >= row["ema_50_1h"]:
        return False
    rng = row["High"] - row["Low"]
    if rng <= 0:
        return False
    closes_weak = (row["High"] - row["Close"]) / rng >= 0.60
    return (prev["High"] >= row["ema_20"] and row["Close"] < row["ema_20"]) and closes_weak

def cond_sensex_heikin_ashi_bearish(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] >= row["ema_50_1h"]:
        return False
    body = row["ha_open"] - row["ha_close"]
    prev_bearish = row["ha_prev_open"] > row["ha_prev_close"]
    if body <= 0 or not prev_bearish:
        return False
    upper_wick = row["ha_high"] - row["ha_open"]
    return upper_wick <= 0.15 * body

def cond_sensex_rsi_momentum_bearish(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] >= row["ema_50_1h"]:
        return False
    rsi_cross = row["rsi"] <= 48 and prev["rsi"] > 48
    stoch_bear = row["stoch_k"] < row["stoch_d"]
    return rsi_cross and stoch_bear

def cond_sensex_bb_squeeze_bearish(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] >= row["ema_50_1h"]:
        return False
    was_squeezed = prev["bb_width"] < prev["bb_width_avg"]
    breaks_lower = row["Close"] < row["bb_lower"]
    return was_squeezed and breaks_lower


# ============================================================================
# Main Execution Runner
# ============================================================================

def main():
    t0 = time.time()
    print("\n" + "=" * 94, flush=True)
    print("  FAST SENSEX MULTI-STRATEGY BACKTEST SUITE (1-YEAR: 12 STRATEGIES)", flush=True)
    print("  Strike: ITM (~Rs.600) | Lot: 20 | TP: 150 pts | SL: 20% | Trailing: +15%/15%", flush=True)
    print("=" * 94 + "\n", flush=True)

    df_raw = pd.read_csv(SENSEX_CSV)
    print(f"Loaded {len(df_raw):,} SENSEX bars. Precomputing indicators...", end="", flush=True)
    t_pre = time.time()
    df = precompute_sensex_data(df_raw)
    print(f" done ({time.time() - t_pre:.2f}s)\n", flush=True)

    strategies = [
        # CE Strategies
        ("SENSEX_ORB_BULLISH", "CE", cond_sensex_orb_bullish),
        ("SENSEX_MACD_BULLISH", "CE", cond_sensex_macd_bullish),
        ("SENSEX_SUPPORT_BOUNCE", "CE", cond_sensex_support_bounce),
        ("SENSEX_HEIKIN_ASHI_BULLISH", "CE", cond_sensex_heikin_ashi_bullish),
        ("SENSEX_RSI_MOMENTUM_BULLISH", "CE", cond_sensex_rsi_momentum_bullish),
        ("SENSEX_BB_SQUEEZE_BULLISH", "CE", cond_sensex_bb_squeeze_bullish),

        # PE Strategies
        ("SENSEX_ORB_BEARISH", "PE", cond_sensex_orb_bearish),
        ("SENSEX_MACD_BEARISH", "PE", cond_sensex_macd_bearish),
        ("SENSEX_RESISTANCE_REJECTION", "PE", cond_sensex_resistance_rejection),
        ("SENSEX_HEIKIN_ASHI_BEARISH", "PE", cond_sensex_heikin_ashi_bearish),
        ("SENSEX_RSI_MOMENTUM_BEARISH", "PE", cond_sensex_rsi_momentum_bearish),
        ("SENSEX_BB_SQUEEZE_BEARISH", "PE", cond_sensex_bb_squeeze_bearish),
    ]

    results = {}
    print(f"  {'Strategy':<32} | {'Trades':>6} {'Wins':>5} {'Losses':>6} {'Win Rate':>8} {'PF':>6} | {'Total P&L (Rs)':>14} | {'Max DD%':>7}", flush=True)
    print("  " + "-" * 90, flush=True)

    total_pnl = 0.0
    total_trades = 0
    total_wins = 0

    for name, direction, cond_fn in strategies:
        r, history = simulate_sensex_strategy(name, direction, df, cond_fn, target_tp_pts=150.0)
        total_pnl += r.total_pnl
        total_trades += r.total_trades
        total_wins += r.winning_trades

        pf_str = f"{r.profit_factor:.2f}" if r.profit_factor < 900 else "inf"
        print(f"  {r.strategy:<32} | {r.total_trades:>6} {r.winning_trades:>5} {r.losing_trades:>6} {r.win_rate:>7.1f}% {pf_str:>6} | Rs.{r.total_pnl:>10,.2f} | {r.max_drawdown_pct:>6.2f}%", flush=True)

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

    print("  " + "-" * 90, flush=True)
    overall_win_rate = (total_wins / total_trades * 100) if total_trades else 0
    print(f"  {'PORTFOLIO TOTAL (SENSEX)':<32} | {total_trades:>6} {total_wins:>5} {total_trades - total_wins:>6} {overall_win_rate:>7.1f}% {'—':>6} | Rs.{total_pnl:>10,.2f} |", flush=True)
    print("=" * 94 + "\n", flush=True)

    print(f"Completed full SENSEX suite in {time.time() - t0:.2f}s", flush=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Report saved to {OUTPUT_REPORT}\n", flush=True)


if __name__ == "__main__":
    main()
