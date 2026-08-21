"""
Master 21-Strategy Backtest Generator & Persistence Engine
==========================================================
Replays 1-year historical data across all 21 active strategies:
- 9 Existing 1-Minute ATM Baseline Strategies (4 NIFTY + 5 SENSEX)
- 12 New 5-Minute ITM Suite (6 NIFTY + 6 SENSEX)

Generates:
1. data/backtest_results/report.json (21 strategy scorecard)
2. data/backtest_results/capital_requirements.json (realistic ~Rs.16k-17k per-lot capital)
3. data/backtest_results/{STRATEGY_NAME}_history.json (individual trade histories)
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
from src.backtester.report import build_report, BacktestReport
from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days, parse_option_symbol

NIFTY_5M_CSV = PROJECT_ROOT / "data" / "historical" / "nifty_5min.csv"
SENSEX_CSV = PROJECT_ROOT / "data" / "historical" / "sensex_1year.csv"
RESULTS_DIR = PROJECT_ROOT / "data" / "backtest_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Vectorized Precomputation for NIFTY & SENSEX
# ============================================================================

def precompute_nifty(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.sort_values("Timestamp").reset_index(drop=True)

    df["ema_20_5m"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["ema_50_5m"] = df["Close"].ewm(span=50, adjust=False).mean()

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    df["macd_hist_5m"] = macd_line - signal_line
    df["macd_hist_5m_prev"] = df["macd_hist_5m"].shift(1).fillna(0.0)

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

    df_indexed = df.set_index("Timestamp")
    df_1h = df_indexed.resample("1h").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    df_1h["ema_50_1h"] = df_1h["Close"].ewm(span=50, adjust=False).mean()

    df = pd.merge_asof(
        df.sort_values("Timestamp"),
        df_1h[["ema_50_1h"]].reset_index().sort_values("Timestamp"),
        on="Timestamp", direction="backward"
    )

    df["date"] = df["Timestamp"].dt.date
    df["time"] = df["Timestamp"].dt.time
    orb_bars = df[df["time"].between(dtime(9, 15), dtime(9, 25))]
    df = df.merge(orb_bars.groupby("date")["High"].max().rename("orb_high"), on="date", how="left")
    df = df.merge(orb_bars.groupby("date")["Low"].min().rename("orb_low"), on="date", how="left")
    return df


def precompute_sensex(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.sort_values("Timestamp").reset_index(drop=True)

    df["ema_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["ema_50"] = df["Close"].ewm(span=50, adjust=False).mean()

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    df["macd_hist"] = macd_line - signal_line
    df["macd_hist_prev"] = df["macd_hist"].shift(1).fillna(0.0)

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

    df_indexed = df.set_index("Timestamp")
    df_1h = df_indexed.resample("1h").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    df_1h["ema_50_1h"] = df_1h["Close"].ewm(span=50, adjust=False).mean()

    df = pd.merge_asof(
        df.sort_values("Timestamp"),
        df_1h[["ema_50_1h"]].reset_index().sort_values("Timestamp"),
        on="Timestamp", direction="backward"
    )

    df["date"] = df["Timestamp"].dt.date
    df["time"] = df["Timestamp"].dt.time
    orb_bars = df[df["time"].between(dtime(9, 15), dtime(9, 25))]
    df = df.merge(orb_bars.groupby("date")["High"].max().rename("orb_high"), on="date", how="left")
    df = df.merge(orb_bars.groupby("date")["Low"].min().rename("orb_low"), on="date", how="left")
    return df


# ============================================================================
# Strike Selection Helpers
# ============================================================================

def select_strike(spot: float, option_type: str, dte: float, underlying: str,
                  strike_mode: str = "ITM") -> tuple[str, float]:
    strike_step = 50 if underlying == "NIFTY" else 100
    atm_strike = round(spot / strike_step) * strike_step
    if strike_mode == "ATM":
        return f"{underlying}{int(atm_strike)}{option_type}", float(atm_strike)

    target_premium = 200.0 if underlying == "NIFTY" else 600.0
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
        elif price > target_premium + 150:
            break

    return f"{underlying}{int(best_strike)}{option_type}", float(best_strike)


# ============================================================================
# Simulator
# ============================================================================

def run_simulation(name: str, direction: str, underlying: str, strike_mode: str,
                   df: pd.DataFrame, condition_fn, tp_pts: float) -> tuple[BacktestReport, list]:
    lot_size = 65 if underlying == "NIFTY" else 20
    trader = PaperTrader(
        initial_capital=1_000_000,
        lot_size=lot_size,
        max_concurrent_positions=5,
        max_daily_loss=5000,
        max_trades_per_day_per_strategy=2,
        trailing_stop_enabled=True,
        trailing_activation_pct=15.0,
        trailing_stop_pct=15.0,
    )

    stop_loss_pct = 20.0
    time_exit_mins = 90
    last_signal_time = None
    min_cooldown_secs = 15 * 60

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]
        ts = row["Timestamp"]
        spot = row["Close"]

        # Mark to market
        dte = next_weekly_expiry_days(ts, index=underlying)
        prices = {}
        for order in trader.get_positions():
            strike, opt_type = parse_option_symbol(order.symbol)
            if strike:
                prices[order.symbol] = black_scholes_price(spot, strike, dte, opt_type)
        trader.update_positions(prices, timestamp=ts, time_exit_mins=time_exit_mins)

        # Cooldown gate
        if last_signal_time and (ts - last_signal_time).total_seconds() < min_cooldown_secs:
            continue

        if not condition_fn(row, prev_row):
            continue

        symbol, strike = select_strike(spot, direction, dte, underlying, strike_mode)
        entry_price = black_scholes_price(spot, strike, dte, direction)
        stop_loss = max(entry_price * (1 - stop_loss_pct / 100), 0.05)
        take_profit = entry_price + tp_pts

        try:
            trader.place_order(
                symbol=symbol, side="BUY", qty=1, price=entry_price,
                stop_loss=stop_loss, take_profit=take_profit,
                strategy=name, timestamp=ts, lot_size=lot_size
            )
            last_signal_time = ts
        except RiskLimitExceeded:
            continue

    history = trader.get_trade_history()
    report = build_report(name, direction, history, 1_000_000)
    return report, history


# ============================================================================
# Strategy Catalog (21 Strategies)
# ============================================================================

def main():
    t0 = time.time()
    print("\n" + "=" * 94, flush=True)
    print("  GENERATING MASTER 21-STRATEGY SCORECARD & PERSISTENCE REPORT", flush=True)
    print("=" * 94 + "\n", flush=True)

    df_nifty = precompute_nifty(pd.read_csv(NIFTY_5M_CSV))
    df_sensex = precompute_sensex(pd.read_csv(SENSEX_CSV))

    # --- Condition Functions ---
    def c_orb_bull(r, p):
        if r["time"] < dtime(9, 30) or pd.isna(r["orb_high"]): return False
        c = (p["time"] < dtime(9, 30) and r["Close"] > r["orb_high"]) or (p["Close"] <= r["orb_high"] < r["Close"])
        return c and (pd.isna(r["ema_50_1h"]) or r["Close"] > r["ema_50_1h"])

    def c_orb_bear(r, p):
        if r["time"] < dtime(9, 30) or pd.isna(r["orb_low"]): return False
        c = (p["time"] < dtime(9, 30) and r["Close"] < r["orb_low"]) or (p["Close"] >= r["orb_low"] > r["Close"])
        return c and (pd.isna(r["ema_50_1h"]) or r["Close"] < r["ema_50_1h"])

    def c_macd_bull(r, p):
        hist = r.get("macd_hist_5m", r.get("macd_hist"))
        p_hist = r.get("macd_hist_5m_prev", r.get("macd_hist_prev"))
        return (hist > 0 and p_hist <= 0) and (pd.isna(r["ema_50_1h"]) or r["Close"] > r["ema_50_1h"])

    def c_macd_bear(r, p):
        hist = r.get("macd_hist_5m", r.get("macd_hist"))
        p_hist = r.get("macd_hist_5m_prev", r.get("macd_hist_prev"))
        return (hist < 0 and p_hist >= 0) and (pd.isna(r["ema_50_1h"]) or r["Close"] < r["ema_50_1h"])

    def c_ha_bull(r, p):
        if pd.isna(r["ema_50_1h"]) or r["Close"] <= r["ema_50_1h"]: return False
        b = r["ha_close"] - r["ha_open"]
        pb = r["ha_prev_close"] > r["ha_prev_open"]
        return b > 0 and pb and (r["ha_open"] - r["ha_low"] <= 0.15 * b)

    def c_ha_bear(r, p):
        if pd.isna(r["ema_50_1h"]) or r["Close"] >= r["ema_50_1h"]: return False
        b = r["ha_open"] - r["ha_close"]
        pb = r["ha_prev_open"] > r["ha_prev_close"]
        return b > 0 and pb and (r["ha_high"] - r["ha_open"] <= 0.15 * b)

    def c_sup_bounce(r, p):
        ema = r.get("ema_20_5m", r.get("ema_20"))
        if pd.isna(r["ema_50_1h"]) or r["Close"] <= r["ema_50_1h"] or ema is None: return False
        rng = r["High"] - r["Low"]
        if rng <= 0 or (r["Close"] - r["Low"]) / rng < 0.60: return False
        return p["Low"] <= ema and r["Close"] > ema

    def c_res_reject(r, p):
        ema = r.get("ema_20_5m", r.get("ema_20"))
        if pd.isna(r["ema_50_1h"]) or r["Close"] >= r["ema_50_1h"] or ema is None: return False
        rng = r["High"] - r["Low"]
        if rng <= 0 or (r["High"] - r["Close"]) / rng < 0.60: return False
        return p["High"] >= ema and r["Close"] < ema

    # Strategy Definition Roster (21 Strategies)
    strategies = [
        # --- 9 Existing 1-Minute ATM Baseline Strategies ---
        ("NIFTY_ORB_BULLISH_1M_ATM", "CE", "NIFTY", "ATM", df_nifty, c_orb_bull, 50.0),
        ("NIFTY_MACD_BULLISH_1M_ATM", "CE", "NIFTY", "ATM", df_nifty, c_macd_bull, 50.0),
        ("NIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "PE", "NIFTY", "ATM", df_nifty, c_ha_bear, 50.0),
        ("NIFTY_MACD_BEARISH_1M_ATM", "PE", "NIFTY", "ATM", df_nifty, c_macd_bear, 50.0),
        ("SENSEX_MACD_BULLISH_1M_ATM", "CE", "SENSEX", "ATM", df_sensex, c_macd_bull, 150.0),
        ("SENSEX_SUPPORT_BOUNCE_1M_ATM", "CE", "SENSEX", "ATM", df_sensex, c_sup_bounce, 150.0),
        ("SENSEX_HEIKIN_ASHI_BEARISH_1M_ATM", "PE", "SENSEX", "ATM", df_sensex, c_ha_bear, 150.0),
        ("SENSEX_MACD_BEARISH_1M_ATM", "PE", "SENSEX", "ATM", df_sensex, c_macd_bear, 150.0),
        ("SENSEX_ORB_BEARISH_1M_ATM", "PE", "SENSEX", "ATM", df_sensex, c_orb_bear, 150.0),

        # --- 12 New 5-Minute ITM Suite ---
        ("NIFTY_SUPPORT_BOUNCE_5M_ITM", "CE", "NIFTY", "ITM", df_nifty, c_sup_bounce, 50.0),
        ("NIFTY_HEIKIN_ASHI_BULLISH_5M_ITM", "CE", "NIFTY", "ITM", df_nifty, c_ha_bull, 50.0),
        ("NIFTY_ORB_BULLISH_5M_ITM", "CE", "NIFTY", "ITM", df_nifty, c_orb_bull, 50.0),
        ("NIFTY_RESISTANCE_REJECTION_5M_ITM", "PE", "NIFTY", "ITM", df_nifty, c_res_reject, 50.0),
        ("NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "PE", "NIFTY", "ITM", df_nifty, c_ha_bear, 50.0),
        ("NIFTY_ORB_BEARISH_5M_ITM", "PE", "NIFTY", "ITM", df_nifty, c_orb_bear, 50.0),

        ("SENSEX_SUPPORT_BOUNCE_5M_ITM", "CE", "SENSEX", "ITM", df_sensex, c_sup_bounce, 150.0),
        ("SENSEX_HEIKIN_ASHI_BULLISH_5M_ITM", "CE", "SENSEX", "ITM", df_sensex, c_ha_bull, 150.0),
        ("SENSEX_ORB_BULLISH_5M_ITM", "CE", "SENSEX", "ITM", df_sensex, c_orb_bull, 150.0),
        ("SENSEX_RESISTANCE_REJECTION_5M_ITM", "PE", "SENSEX", "ITM", df_sensex, c_res_reject, 150.0),
        ("SENSEX_HEIKIN_ASHI_BEARISH_5M_ITM", "PE", "SENSEX", "ITM", df_sensex, c_ha_bear, 150.0),
        ("SENSEX_ORB_BEARISH_5M_ITM", "PE", "SENSEX", "ITM", df_sensex, c_orb_bear, 150.0),
    ]

    report_data = {}
    capital_data = {}

    print(f"  {'#':<2} {'Strategy':<36} | {'Trades':>6} {'Wins':>5} {'Losses':>6} {'Win Rate':>8} {'PF':>6} | {'Total P&L (Rs)':>14} | {'Capital':>9}", flush=True)
    print("  " + "-" * 98, flush=True)

    total_pnl = 0.0
    total_trades = 0
    total_wins = 0

    for idx, (name, direction, underlying, strike_mode, df, cond_fn, tp_pts) in enumerate(strategies, 1):
        r, history = run_simulation(name, direction, underlying, strike_mode, df, cond_fn, tp_pts)
        total_pnl += r.total_pnl
        total_trades += r.total_trades
        total_wins += r.winning_trades

        # Realistic capital requirement: 1-lot margin + 30% cushion
        lot_size = 65 if underlying == "NIFTY" else 20
        target_prem = 200.0 if underlying == "NIFTY" else 600.0
        if strike_mode == "ATM":
            target_prem = 120.0 if underlying == "NIFTY" else 350.0
        trade_margin = target_prem * lot_size
        rec_capital = math.ceil(trade_margin * 1.30 / 1000.0) * 1000.0

        pf_str = f"{r.profit_factor:.2f}" if r.profit_factor < 900 else "inf"
        print(f"  {idx:<2} {r.strategy:<36} | {r.total_trades:>6} {r.winning_trades:>5} {r.losing_trades:>6} {r.win_rate:>7.1f}% {pf_str:>6} | Rs.{r.total_pnl:>10,.2f} | Rs.{rec_capital:>7,.0f}", flush=True)

        report_data[r.strategy] = {
            "strategy": r.strategy,
            "direction": r.direction,
            "underlying": underlying,
            "strike_mode": strike_mode,
            "total_trades": r.total_trades,
            "winning_trades": r.winning_trades,
            "losing_trades": r.losing_trades,
            "win_rate": r.win_rate,
            "profit_factor": r.profit_factor,
            "total_pnl": r.total_pnl,
            "max_drawdown_pct": r.max_drawdown_pct,
            "recommended_capital": rec_capital,
        }

        capital_data[r.strategy] = {
            "avg_trade_risk": round(trade_margin, 2),
            "max_historical_drawdown": r.max_drawdown,
            "recommended_capital": rec_capital,
        }

        # Write individual trade history JSON
        history_path = RESULTS_DIR / f"{r.strategy}_history.json"
        history_path.write_text(json.dumps([
            {"entry_time": str(o.entry_time), "exit_time": str(o.exit_time),
             "symbol": o.symbol, "entry_price": o.entry_price, "exit_price": o.exit_price,
             "realized_pnl": o.realized_pnl, "exit_reason": o.exit_reason}
            for o in history
        ], indent=2))

    print("  " + "-" * 98, flush=True)
    overall_wr = (total_wins / total_trades * 100) if total_trades else 0
    print(f"  {'COMBINED 21-STRATEGY MASTER PORTFOLIO':<39} | {total_trades:>6} {total_wins:>5} {total_trades - total_wins:>6} {overall_wr:>7.1f}% {'—':>6} | Rs.{total_pnl:>10,.2f} |", flush=True)
    print("=" * 94 + "\n", flush=True)

    # Save consolidated report.json and capital_requirements.json
    (RESULTS_DIR / "report.json").write_text(json.dumps(report_data, indent=2))
    (RESULTS_DIR / "capital_requirements.json").write_text(json.dumps(capital_data, indent=2))
    print(f"All 21 strategies saved to {RESULTS_DIR / 'report.json'} ({time.time() - t0:.1f}s)\n", flush=True)


if __name__ == "__main__":
    main()
