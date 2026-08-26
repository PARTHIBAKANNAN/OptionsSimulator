"""
Comprehensive BANKNIFTY Multi-Strategy Backtest Suite (CE & PE)
===============================================================
Evaluates 11 distinct quantitative strategies across 1-year BANKNIFTY historical data.
Uses ITM strike selection (~Rs.500 target premium, lot size = 30, strike step = 100).
Tuesday weekly expiry.

Strategies Tested:
  - BANKNIFTY_ORB_BULLISH_5M_ITM (CE)
  - BANKNIFTY_MACD_BULLISH_1M_ATM (CE)
  - BANKNIFTY_SUPPORT_BOUNCE_5M_ITM (CE)
  - BANKNIFTY_HEIKIN_ASHI_BULLISH_5M_ITM (CE)
  - BANKNIFTY_ORB_BEARISH_5M_ITM (PE)
  - BANKNIFTY_MACD_BEARISH_1M_ATM (PE)
  - BANKNIFTY_RESISTANCE_REJECTION_5M_ITM (PE)
  - BANKNIFTY_HEIKIN_ASHI_BEARISH_5M_ITM (PE)
  - BANKNIFTY_SUPPORT_BOUNCE_1M_ATM (CE)
  - BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM (PE)
  - BANKNIFTY_ORB_BEARISH_1M_ATM (PE)
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
from src.backtester.report import build_report, asdict
from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days, parse_option_symbol

BANKNIFTY_CSV = PROJECT_ROOT / "data" / "historical" / "banknifty_1year.csv"
OUTPUT_REPORT = PROJECT_ROOT / "data" / "backtest_results" / "banknifty_strategy_report.json"
BANKNIFTY_LOT_SIZE = 30
BANKNIFTY_STRIKE_STEP = 100
BANKNIFTY_ITM_PREMIUM = 500.0


# ============================================================================
# Vectorized Precomputation across BANKNIFTY Data
# ============================================================================

def precompute_banknifty_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.sort_values("Timestamp").reset_index(drop=True)

    # 1. EMAs (20 and 50)
    df["ema_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["ema_50"] = df["Close"].ewm(span=50, adjust=False).mean()

    # 1H 50-EMA proxy (approx 12 5m bars per hour -> span 600)
    df["ema_50_1h"] = df["Close"].ewm(span=600, adjust=False).mean()

    # 2. MACD (12, 26, 9)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    df["macd_hist"] = macd_line - signal_line
    df["macd_hist_prev"] = df["macd_hist"].shift(1).fillna(0.0)

    # 3. RSI (14)
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14, min_periods=14).mean()
    avg_loss = loss.rolling(window=14, min_periods=14).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    # 4. Stochastic (14, 3, 3)
    low14 = df["Low"].rolling(14).min()
    high14 = df["High"].rolling(14).max()
    raw_k = 100 * (df["Close"] - low14) / (high14 - low14 + 1e-9)
    df["stoch_k"] = raw_k.rolling(3).mean()
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    # 5. Bollinger Bands (20, 2.0 std)
    bb_mid = df["Close"].rolling(20).mean()
    bb_std = df["Close"].rolling(20).std()
    df["bb_upper"] = bb_mid + 2.0 * bb_std
    df["bb_lower"] = bb_mid - 2.0 * bb_std

    # 6. Heikin Ashi
    ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4.0
    ha_open = np.zeros(len(df))
    ha_open[0] = (df["Open"].iloc[0] + df["Close"].iloc[0]) / 2.0
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i - 1] + ha_close.iloc[i - 1]) / 2.0
    ha_open_s = pd.Series(ha_open, index=df.index)
    ha_high = pd.concat([df["High"], ha_open_s, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([df["Low"], ha_open_s, ha_close], axis=1).min(axis=1)

    df["ha_open"] = ha_open_s
    df["ha_high"] = ha_high
    df["ha_low"] = ha_low
    df["ha_close"] = ha_close
    df["ha_prev_open"] = ha_open_s.shift(1).fillna(ha_open_s.iloc[0])
    df["ha_prev_close"] = ha_close.shift(1).fillna(ha_close.iloc[0])

    # 7. Opening Range (09:15 - 09:30)
    df["date"] = df["Timestamp"].dt.date
    df["time"] = df["Timestamp"].dt.time

    orb_window = df[df["time"] < dtime(9, 30)]
    orb_highs = orb_window.groupby("date")["High"].max().rename("orb_high")
    orb_lows = orb_window.groupby("date")["Low"].min().rename("orb_low")

    df = df.merge(orb_highs, on="date", how="left")
    df = df.merge(orb_lows, on="date", how="left")

    return df


# ============================================================================
# Strike Selection Helper
# ============================================================================

def select_banknifty_strike(spot: float, option_type: str, dte: float, mode: str = "ITM",
                            target_premium: float = BANKNIFTY_ITM_PREMIUM) -> tuple[str, float]:
    atm_strike = round(spot / BANKNIFTY_STRIKE_STEP) * BANKNIFTY_STRIKE_STEP
    if mode == "ATM":
        return f"BANKNIFTY{int(atm_strike)}{option_type}", float(atm_strike)

    best_strike = atm_strike
    best_price = black_scholes_price(spot, atm_strike, dte, option_type)
    best_diff = abs(best_price - target_premium)

    for k in range(1, 25):
        strike = atm_strike - k * BANKNIFTY_STRIKE_STEP if option_type == "CE" else atm_strike + k * BANKNIFTY_STRIKE_STEP
        price = black_scholes_price(spot, strike, dte, option_type)
        diff = abs(price - target_premium)
        if diff < best_diff:
            best_diff = diff
            best_strike = strike
            best_price = price
        elif price > target_premium + 300:
            break

    return f"BANKNIFTY{int(best_strike)}{option_type}", float(best_strike)


def mark_to_market(trader: PaperTrader, spot: float, ts: datetime) -> dict:
    prices = {}
    dte = next_weekly_expiry_days(ts, index="BANKNIFTY")
    for pos in trader.get_positions():
        strike, opt_type = parse_option_symbol(pos.symbol)
        if strike is not None and opt_type is not None:
            prices[pos.symbol] = black_scholes_price(spot, strike, dte, opt_type)
    return prices


# ============================================================================
# Simulator Engine
# ============================================================================

def simulate_banknifty_strategy(name: str, direction: str, df: pd.DataFrame, condition_fn,
                                mode: str = "ITM", target_tp_pts: float = 150.0) -> tuple[object, list]:
    trader = PaperTrader(
        initial_capital=1_000_000,
        lot_size=BANKNIFTY_LOT_SIZE,
        max_concurrent_positions=5,
        max_daily_loss=10000,
        max_trades_per_day_per_strategy=2,
        trailing_stop_enabled=True,
        trailing_activation_pct=10.0,
        trailing_stop_pct=15.0,
        consecutive_loss_limit=3,
        consecutive_loss_cooldown_days=1,
        max_drawdown_pct_of_capital=25.0,
        drawdown_cooldown_days=3,
        drawdown_breaker_grace_trades=3,
        capital_by_strategy={name: 60000.0},
        charges_rates={
            "brokerage_flat": 20.0,
            "brokerage_pct": 0.03,
            "stt_sell_pct": 0.1,
            "exchange_txn_pct": 0.03503,
            "sebi_fee_pct": 0.0001,
            "stamp_duty_buy_pct": 0.003,
            "gst_pct": 18.0,
        },
        enable_wallets=True,
    )

    stop_loss_pct = 20.0
    time_exit_mins = 120
    target_prem = BANKNIFTY_ITM_PREMIUM if mode == "ITM" else 250.0

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]
        ts = row["Timestamp"]
        spot = row["Close"]

        current_prices = mark_to_market(trader, spot, ts)
        trader.update_positions(current_prices, timestamp=ts, time_exit_mins=time_exit_mins)

        if row["time"] < dtime(9, 20) or row["time"] > dtime(15, 15):
            continue

        should_enter = condition_fn(row, prev_row)
        if not should_enter:
            continue

        dte = next_weekly_expiry_days(ts, index="BANKNIFTY")
        symbol, strike = select_banknifty_strike(spot, direction, dte, mode=mode, target_premium=target_prem)
        entry_price = black_scholes_price(spot, strike, dte, direction)

        stop_loss = max(entry_price * (1 - stop_loss_pct / 100), 0.05)
        take_profit = entry_price + target_tp_pts

        try:
            trader.place_order(
                symbol=symbol, side="BUY", qty=1, price=entry_price,
                stop_loss=stop_loss, take_profit=take_profit,
                strategy=name, timestamp=ts, lot_size=BANKNIFTY_LOT_SIZE
            )
        except RiskLimitExceeded:
            continue

    history = trader.get_trade_history()
    report = build_report(name, direction, history, 1_000_000)
    return report, history


# ============================================================================
# Strategy Condition Definitions
# ============================================================================

# --- BULLISH (CE) ---

def cond_banknifty_orb_bullish(row, prev):
    if row["time"] < dtime(9, 30) or pd.isna(row["orb_high"]):
        return False
    crossed = (prev["time"] < dtime(9, 30) and row["Close"] > row["orb_high"]) or (prev["Close"] <= row["orb_high"] < row["Close"])
    return crossed and (pd.isna(row["ema_50_1h"]) or row["Close"] > row["ema_50_1h"])

def cond_banknifty_macd_bullish(row, prev):
    if pd.isna(row["ema_50_1h"]):
        return False
    return (row["macd_hist"] > 0 and prev["macd_hist"] <= 0) and (row["Close"] > row["ema_50_1h"])

def cond_banknifty_support_bounce(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] <= row["ema_50_1h"]:
        return False
    rng = row["High"] - row["Low"]
    if rng <= 0:
        return False
    closes_strong = (row["Close"] - row["Low"]) / rng >= 0.60
    return (prev["Low"] <= row["ema_20"] and row["Close"] > row["ema_20"]) and closes_strong

def cond_banknifty_heikin_ashi_bullish(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] <= row["ema_50_1h"]:
        return False
    body = row["ha_close"] - row["ha_open"]
    prev_bullish = row["ha_prev_close"] > row["ha_prev_open"]
    if body <= 0 or not prev_bullish:
        return False
    lower_wick = row["ha_open"] - row["ha_low"]
    return lower_wick <= 0.15 * body


# --- BEARISH (PE) ---

def cond_banknifty_orb_bearish(row, prev):
    if row["time"] < dtime(9, 30) or pd.isna(row["orb_low"]):
        return False
    crossed = (prev["time"] < dtime(9, 30) and row["Close"] < row["orb_low"]) or (prev["Close"] >= row["orb_low"] > row["Close"])
    return crossed and (pd.isna(row["ema_50_1h"]) or row["Close"] < row["ema_50_1h"])

def cond_banknifty_macd_bearish(row, prev):
    if pd.isna(row["ema_50_1h"]):
        return False
    return (row["macd_hist"] < 0 and prev["macd_hist"] >= 0) and (row["Close"] < row["ema_50_1h"])

def cond_banknifty_resistance_rejection(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] >= row["ema_50_1h"]:
        return False
    rng = row["High"] - row["Low"]
    if rng <= 0:
        return False
    closes_weak = (row["High"] - row["Close"]) / rng >= 0.60
    return (prev["High"] >= row["ema_20"] and row["Close"] < row["ema_20"]) and closes_weak

def cond_banknifty_heikin_ashi_bearish(row, prev):
    if pd.isna(row["ema_50_1h"]) or row["Close"] >= row["ema_50_1h"]:
        return False
    body = row["ha_open"] - row["ha_close"]
    prev_bearish = row["ha_prev_open"] > row["ha_prev_close"]
    if body <= 0 or not prev_bearish:
        return False
    upper_wick = row["ha_high"] - row["ha_open"]
    return upper_wick <= 0.15 * body


# ============================================================================
# Main Execution Runner
# ============================================================================

def main():
    t0 = time.time()
    print("\n" + "=" * 98, flush=True)
    print("  FAST BANKNIFTY MULTI-STRATEGY BACKTEST SUITE (1-YEAR: 11 STRATEGIES)", flush=True)
    print("  Strike: ITM (~Rs.500) & ATM | Lot: 30 | TP: 150 pts | SL: 20% | Trailing: +10%/15%", flush=True)
    print("=" * 98 + "\n", flush=True)

    df_raw = pd.read_csv(BANKNIFTY_CSV)
    print(f"Loaded {len(df_raw):,} BANKNIFTY bars ({df_raw['Timestamp'].min()} to {df_raw['Timestamp'].max()}). Precomputing...", end="", flush=True)
    t_pre = time.time()
    df = precompute_banknifty_data(df_raw)
    print(f" done ({time.time() - t_pre:.2f}s)\n", flush=True)

    strategies = [
        # 5M ITM Strategies
        ("BANKNIFTY_ORB_BULLISH_5M_ITM", "CE", cond_banknifty_orb_bullish, "ITM"),
        ("BANKNIFTY_MACD_BULLISH_1M_ATM", "CE", cond_banknifty_macd_bullish, "ATM"),
        ("BANKNIFTY_SUPPORT_BOUNCE_5M_ITM", "CE", cond_banknifty_support_bounce, "ITM"),
        ("BANKNIFTY_HEIKIN_ASHI_BULLISH_5M_ITM", "CE", cond_banknifty_heikin_ashi_bullish, "ITM"),
        ("BANKNIFTY_SUPPORT_BOUNCE_1M_ATM", "CE", cond_banknifty_support_bounce, "ATM"),
        
        # PE Strategies
        ("BANKNIFTY_ORB_BEARISH_5M_ITM", "PE", cond_banknifty_orb_bearish, "ITM"),
        ("BANKNIFTY_MACD_BEARISH_1M_ATM", "PE", cond_banknifty_macd_bearish, "ATM"),
        ("BANKNIFTY_RESISTANCE_REJECTION_5M_ITM", "PE", cond_banknifty_resistance_rejection, "ITM"),
        ("BANKNIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "PE", cond_banknifty_heikin_ashi_bearish, "ITM"),
        ("BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "PE", cond_banknifty_heikin_ashi_bearish, "ATM"),
        ("BANKNIFTY_ORB_BEARISH_1M_ATM", "PE", cond_banknifty_orb_bearish, "ATM"),
    ]

    results = {}
    print(f"  {'Strategy':<40} | {'Trades':>6} {'Wins':>5} {'Losses':>6} {'Win Rate':>8} {'PF':>6} | {'Total P&L (Rs)':>14} | {'Max DD%':>7}", flush=True)
    print("  " + "-" * 98, flush=True)

    total_pnl = 0.0
    total_trades = 0
    total_wins = 0

    for name, direction, cond_fn, mode in strategies:
        r, history = simulate_banknifty_strategy(name, direction, df, cond_fn, mode=mode, target_tp_pts=150.0)
        total_pnl += r.total_pnl
        total_trades += r.total_trades
        total_wins += r.winning_trades

        pf_str = f"{r.profit_factor:.2f}" if r.profit_factor < 900 else "inf"
        print(f"  {r.strategy:<40} | {r.total_trades:>6} {r.winning_trades:>5} {r.losing_trades:>6} {r.win_rate:>7.1f}% {pf_str:>6} | Rs.{r.total_pnl:>12,.2f} | {r.max_drawdown_pct:>6.2f}%", flush=True)

        results[r.strategy] = {
            "direction": r.direction,
            "total_trades": r.total_trades,
            "winning_trades": r.winning_trades,
            "losing_trades": r.losing_trades,
            "win_rate": r.win_rate,
            "profit_factor": r.profit_factor,
            "total_pnl": r.total_pnl,
            "max_drawdown": r.max_drawdown,
            "max_drawdown_pct": r.max_drawdown_pct,
            "consecutive_wins": r.consecutive_wins,
            "consecutive_losses": r.consecutive_losses,
        }

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_REPORT, "w") as f:
        json.dump(results, f, indent=2)

    overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
    print("  " + "-" * 98, flush=True)
    print(f"  {'PORTFOLIO TOTAL / SUMMARY':<40} | {total_trades:>6} {total_wins:>5} {total_trades - total_wins:>6} {overall_wr:>7.1f}% {'-':>6} | Rs.{total_pnl:>12,.2f} |", flush=True)
    print("=" * 98 + "\n", flush=True)
    print(f"Report successfully saved to {OUTPUT_REPORT} ({time.time() - t0:.2f}s total execution)")


if __name__ == "__main__":
    main()
