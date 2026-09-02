"""
Master 44-Strategy Real-Indicator Vectorized Backtest Engine
============================================================
Fast vectorized calculation of real indicators (Supertrend, CMF, VWAP, Bollinger Bands,
Heikin-Ashi, MACD, RSI, ORB) across NIFTY, SENSEX, and BANKNIFTY historical datasets.
Generates:
1. data/backtest_results/report.json
2. data/backtest_results/daily_report.json
3. data/backtest_results/capital_requirements.json
4. data/backtest_results/{STRATEGY_NAME}_history.json
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
from src.backtester.report import build_report, build_daily_breakdown, required_capital_per_strategy
from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days, parse_option_symbol
from src.utils import indicators as ind

NIFTY_1M_CSV = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
NIFTY_5M_CSV = PROJECT_ROOT / "data" / "historical" / "nifty_5min.csv"
SENSEX_CSV = PROJECT_ROOT / "data" / "historical" / "sensex_1year.csv"
BANKNIFTY_CSV = PROJECT_ROOT / "data" / "historical" / "banknifty_1year.csv"
RESULTS_DIR = PROJECT_ROOT / "data" / "backtest_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.sort_values("Timestamp").reset_index(drop=True)

    df["date"] = df["Timestamp"].dt.date
    df["time"] = df["Timestamp"].dt.time

    # EMAs
    df["ema_20"] = ind.ema(df["Close"], 20)
    df["ema_50"] = ind.ema(df["Close"], 50)

    # MACD
    macd_df = ind.macd(df["Close"])
    df["macd_hist"] = macd_df["histogram"]
    df["macd_hist_prev"] = df["macd_hist"].shift(1).fillna(0.0)

    # RSI
    df["rsi"] = ind.rsi(df["Close"], 14)

    # Supertrend (10, 3.0) and (7, 2.0)
    st_df = ind.supertrend(df["High"], df["Low"], df["Close"], period=10, multiplier=3.0)
    df["supertrend"] = st_df["supertrend"]
    df["supertrend_dir"] = st_df["direction"]

    st_df7 = ind.supertrend(df["High"], df["Low"], df["Close"], period=7, multiplier=2.0)
    df["supertrend_dir_7"] = st_df7["direction"]

    # CMF
    df["cmf"] = ind.chaikin_money_flow(df["High"], df["Low"], df["Close"], df["Volume"], 20)

    # Session VWAP
    df["vwap"] = ind.vwap(df["High"], df["Low"], df["Close"], df["Volume"], df["date"])

    # Bollinger Bands (20, 2.0)
    bb_df = ind.bollinger_bands(df["Close"], 20, 2.0)
    df["bb_upper"] = bb_df["upper"]
    df["bb_lower"] = bb_df["lower"]
    df["bb_mid"] = bb_df["mid"]
    df["bb_bandwidth"] = ind.bollinger_bandwidth(df["Close"], 20, 2.0)
    df["bb_bandwidth_20avg"] = df["bb_bandwidth"].rolling(20).mean()

    # Heikin Ashi
    ha_df = ind.heikin_ashi(df)
    df["ha_open"] = ha_df["ha_open"]
    df["ha_close"] = ha_df["ha_close"]
    df["ha_high"] = ha_df["ha_high"]
    df["ha_low"] = ha_df["ha_low"]
    df["ha_prev_open"] = ha_df["ha_open"].shift(1).fillna(ha_df["ha_open"].iloc[0])
    df["ha_prev_close"] = ha_df["ha_close"].shift(1).fillna(ha_df["ha_close"].iloc[0])

    # Volume ratio
    df["vol_ratio"] = ind.volume_ratio(df["Volume"], 20)

    # ORB 9:15 to 9:30
    orb_bars = df[df["time"].between(dtime(9, 15), dtime(9, 30))]
    df = df.merge(orb_bars.groupby("date")["High"].max().rename("orb_high"), on="date", how="left")
    df = df.merge(orb_bars.groupby("date")["Low"].min().rename("orb_low"), on="date", how="left")
    return df


def simulate_strategy_vectorized(
    df: pd.DataFrame,
    strategy_name: str,
    direction: str,
    index: str = "NIFTY",
    is_itm: bool = False,
    lot_size: int = 65,
) -> tuple[object, list]:
    strike_step = 50 if index == "NIFTY" else 100

    trader = PaperTrader(
        initial_capital=1_000_000,
        lot_size=lot_size,
        max_concurrent_positions=5,
        max_daily_loss=5000,
        max_trades_per_day_per_strategy=2,
        trailing_stop_enabled=True,
        trailing_activation_pct=10.0,
        trailing_stop_pct=15.0,
        trailing_tiers_pct=[
            {"gain_pct": 10, "lock_pct": 0},
            {"gain_pct": 20, "lock_pct": 5},
            {"gain_pct": 30, "lock_pct": 10},
        ],
    )

    last_signal_time = None
    trades_today = {}

    for row in df.itertuples(index=False):
        ts = row.Timestamp
        curr_date = row.date
        curr_time = row.time
        spot = row.Close

        # Trading window: 09:25 AM to 15:15 PM
        if not (dtime(9, 25) <= curr_time <= dtime(15, 15)):
            continue

        dte = next_weekly_expiry_days(ts, index=index)

        # Mark to market update
        prices = {}
        for order in trader.get_positions():
            strike, opt_type = parse_option_symbol(order.symbol)
            if strike is not None:
                prices[order.symbol] = black_scholes_price(spot, strike, dte, opt_type)

        trader.update_positions(prices, timestamp=ts, time_exit_mins=120)

        # Single position lock for this strategy
        if any(getattr(o, "strategy", "") == strategy_name for o in trader.get_positions()):
            continue

        # Daily trade limit (2 trades/day)
        day_trades = trades_today.get(curr_date, 0)
        if day_trades >= 2:
            continue

        # Cooldown check (15 minutes)
        if last_signal_time and (ts - last_signal_time).total_seconds() < 900:
            continue

        # Evaluate strategy specific signal
        has_signal = False

        # --- VWAP / POC Strategies ---
        if "VWAP_POC_PULLBACK" in strategy_name:
            if row.Low <= row.vwap and row.Close > row.vwap and row.rsi > 50.0:
                has_signal = True
        elif "VWAP_POC_BREAKDOWN" in strategy_name:
            if row.High >= row.vwap and row.Close < row.vwap and row.rsi < 45.0:
                has_signal = True

        # --- Supertrend + CMF Strategies ---
        elif "SUPERTREND_CMF_BULLISH" in strategy_name:
            if row.supertrend_dir == 1 and row.cmf > 0.02 and row.Close > row.ema_20:
                has_signal = True
        elif "SUPERTREND_CMF_BEARISH" in strategy_name:
            if row.supertrend_dir == -1 and row.cmf < -0.02 and row.Close < row.ema_20:
                has_signal = True

        # --- Dual Supertrend + BB Strategies ---
        elif "DUAL_SUPERTREND_BB_CE" in strategy_name:
            if row.supertrend_dir == 1 and row.supertrend_dir_7 == 1 and row.Close > row.bb_mid:
                has_signal = True
        elif "DUAL_SUPERTREND_BB_PE" in strategy_name:
            if row.supertrend_dir == -1 and row.supertrend_dir_7 == -1 and row.Close < row.bb_mid:
                has_signal = True

        # --- Bollinger Squeeze Volatility Explosion ---
        elif "BB_SQUEEZE_EXPLOSION_CE" in strategy_name:
            is_expanding = row.bb_bandwidth > (row.bb_bandwidth_20avg * 1.15 if row.bb_bandwidth_20avg else 0.01)
            if is_expanding and row.Close > row.bb_upper and row.rsi > 55.0:
                has_signal = True
        elif "BB_SQUEEZE_EXPLOSION_PE" in strategy_name:
            is_expanding = row.bb_bandwidth > (row.bb_bandwidth_20avg * 1.15 if row.bb_bandwidth_20avg else 0.01)
            if is_expanding and row.Close < row.bb_lower and row.rsi < 45.0:
                has_signal = True

        # --- VWAP + BB Liquidity Sweep Rebound ---
        elif "VWAP_BB_LIQUIDITY_REBOUND_CE" in strategy_name:
            rng = row.High - row.Low
            if rng > 0:
                swept_lower_band = row.Low <= row.bb_lower
                reclaimed = row.Close > row.bb_lower and row.Close > row.Open
                bullish_close = (row.Close - row.Low) / rng >= 0.50
                under_vwap = row.Close <= row.vwap * 1.01
                if swept_lower_band and reclaimed and bullish_close and under_vwap:
                    has_signal = True

        # --- Gamma Wall / Support Breakdown ---
        elif "GAMMA_WALL_BREAKOUT_PE" in strategy_name:
            if row.Close < row.bb_lower and row.rsi < 40.0:
                has_signal = True

        # --- OI Squeeze Proxies ---
        elif "OI_SHORT_SQUEEZE_CE" in strategy_name:
            rng = row.High - row.Low
            if rng > 0 and row.Close > row.ema_20 and row.vol_ratio >= 1.20:
                if (row.Close - row.Low) / rng >= 0.55:
                    has_signal = True
        elif "OI_LONG_UNWINDING_PE" in strategy_name:
            rng = row.High - row.Low
            if rng > 0 and row.Close < row.ema_20 and row.vol_ratio >= 1.20:
                if (row.High - row.Close) / rng >= 0.55:
                    has_signal = True

        # --- MACD Strategies ---
        elif "MACD_BULLISH" in strategy_name:
            if row.macd_hist > 0 and row.macd_hist_prev <= 0 and row.Close > row.ema_20:
                has_signal = True
        elif "MACD_BEARISH" in strategy_name:
            if row.macd_hist < 0 and row.macd_hist_prev >= 0 and row.Close < row.ema_20:
                has_signal = True

        # --- Heikin Ashi Trend Strategies ---
        elif "HEIKIN_ASHI_BULLISH" in strategy_name:
            is_ha_green = row.ha_close > row.ha_open
            was_ha_red = row.ha_prev_close <= row.ha_prev_open
            lower_wick = row.ha_open - row.ha_low
            body = row.ha_close - row.ha_open
            flat_bottom = body > 0 and (lower_wick <= 0.15 * body)
            if is_ha_green and (was_ha_red or flat_bottom) and row.Close > row.ema_50:
                has_signal = True
        elif "HEIKIN_ASHI_BEARISH" in strategy_name or "HEIKIN_ASHI_TREND_BEARISH" in strategy_name:
            is_ha_red = row.ha_close < row.ha_open
            was_ha_green = row.ha_prev_close >= row.ha_prev_open
            upper_wick = row.ha_high - row.ha_open
            body = row.ha_open - row.ha_close
            flat_top = body > 0 and (upper_wick <= 0.15 * body)
            if is_ha_red and (was_ha_green or flat_top) and row.Close < row.ema_50:
                has_signal = True

        # --- Opening Range Breakout (ORB) ---
        elif "ORB_BULLISH" in strategy_name:
            if not pd.isna(row.orb_high) and row.Close > row.orb_high and curr_time >= dtime(9, 30):
                has_signal = True
        elif "ORB_BEARISH" in strategy_name:
            if not pd.isna(row.orb_low) and row.Close < row.orb_low and curr_time >= dtime(9, 30):
                has_signal = True

        # --- Support Bounce & Resistance Rejection ---
        elif "SUPPORT_BOUNCE" in strategy_name:
            if row.Low <= row.ema_20 and row.Close > row.ema_20 and row.Close > row.Open:
                has_signal = True
        elif "RESISTANCE_REJECTION" in strategy_name:
            if row.High >= row.ema_20 and row.Close < row.ema_20 and row.Close < row.Open:
                has_signal = True

        if not has_signal:
            continue

        # Strike selection
        atm_strike = round(spot / strike_step) * strike_step
        if is_itm:
            strike = atm_strike - (2 * strike_step) if direction == "CE" else atm_strike + (2 * strike_step)
        else:
            strike = atm_strike

        opt_symbol = f"{index}{int(strike)}{direction}"
        entry_price = black_scholes_price(spot, strike, dte, direction)
        if entry_price <= 1.0:
            continue

        stop_loss = max(entry_price * 0.80, 0.05)  # 20% Stop Loss
        take_profit = entry_price * 1.40            # 40% Take Profit

        try:
            trader.place_order(
                symbol=opt_symbol,
                side="BUY",
                qty=1,
                price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy=strategy_name,
                timestamp=ts,
                lot_size=lot_size,
            )
            last_signal_time = ts
            trades_today[curr_date] = day_trades + 1
        except RiskLimitExceeded:
            continue

    history = trader.get_trade_history()
    report = build_report(strategy_name, direction, history, 1_000_000)
    return report, history


def main():
    t0 = time.time()
    print("=" * 80)
    print("RUNNING 44-STRATEGY MASTER BACKTEST WITH REAL INDICATORS & PERCENTAGE EXITS")
    print("=" * 80)

    print("Loading datasets & computing real indicators (Supertrend, CMF, VWAP, BB, HA, MACD, RSI)...")
    df_nifty_1m = compute_all_indicators(pd.read_csv(NIFTY_1M_CSV))
    df_nifty_5m = compute_all_indicators(pd.read_csv(NIFTY_5M_CSV))
    df_sensex = compute_all_indicators(pd.read_csv(SENSEX_CSV))
    df_banknifty = compute_all_indicators(pd.read_csv(BANKNIFTY_CSV))
    print(f"All indicators vectorized in {time.time() - t0:.2f}s\n")

    strategy_defs = [
        # --- 4 NIFTY 1M ATM Baseline Strategies ---
        ("NIFTY_MACD_BULLISH_1M_ATM", "CE", "NIFTY", False, df_nifty_1m, 65),
        ("NIFTY_ORB_BULLISH_1M_ATM", "CE", "NIFTY", False, df_nifty_1m, 65),
        ("NIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "PE", "NIFTY", False, df_nifty_1m, 65),
        ("NIFTY_MACD_BEARISH_1M_ATM", "PE", "NIFTY", False, df_nifty_1m, 65),

        # --- 6 NIFTY 5M ITM Strategies ---
        ("NIFTY_SUPPORT_BOUNCE_5M_ITM", "CE", "NIFTY", True, df_nifty_5m, 65),
        ("NIFTY_HEIKIN_ASHI_BULLISH_5M_ITM", "CE", "NIFTY", True, df_nifty_5m, 65),
        ("NIFTY_ORB_BULLISH_5M_ITM", "CE", "NIFTY", True, df_nifty_5m, 65),
        ("NIFTY_RESISTANCE_REJECTION_5M_ITM", "PE", "NIFTY", True, df_nifty_5m, 65),
        ("NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "PE", "NIFTY", True, df_nifty_5m, 65),
        ("NIFTY_ORB_BEARISH_5M_ITM", "PE", "NIFTY", True, df_nifty_5m, 65),

        # --- 4 NIFTY 5M Expansion Strategies ---
        ("NIFTY_VWAP_POC_PULLBACK_CE", "CE", "NIFTY", True, df_nifty_5m, 65),
        ("NIFTY_VWAP_POC_BREAKDOWN_PE", "PE", "NIFTY", True, df_nifty_5m, 65),
        ("NIFTY_SUPERTREND_CMF_BULLISH_CE", "CE", "NIFTY", True, df_nifty_5m, 65),
        ("NIFTY_SUPERTREND_CMF_BEARISH_PE", "PE", "NIFTY", True, df_nifty_5m, 65),

        # --- 5 SENSEX 1M ATM Baseline Strategies ---
        ("SENSEX_MACD_BULLISH_1M_ATM", "CE", "SENSEX", False, df_sensex, 20),
        ("SENSEX_SUPPORT_BOUNCE_1M_ATM", "CE", "SENSEX", False, df_sensex, 20),
        ("SENSEX_HEIKIN_ASHI_BEARISH_1M_ATM", "PE", "SENSEX", False, df_sensex, 20),
        ("SENSEX_MACD_BEARISH_1M_ATM", "PE", "SENSEX", False, df_sensex, 20),
        ("SENSEX_ORB_BEARISH_1M_ATM", "PE", "SENSEX", False, df_sensex, 20),

        # --- 6 SENSEX 5M ITM Strategies ---
        ("SENSEX_SUPPORT_BOUNCE_5M_ITM", "CE", "SENSEX", True, df_sensex, 20),
        ("SENSEX_HEIKIN_ASHI_BULLISH_5M_ITM", "CE", "SENSEX", True, df_sensex, 20),
        ("SENSEX_ORB_BULLISH_5M_ITM", "CE", "SENSEX", True, df_sensex, 20),
        ("SENSEX_RESISTANCE_REJECTION_5M_ITM", "PE", "SENSEX", True, df_sensex, 20),
        ("SENSEX_HEIKIN_ASHI_BEARISH_5M_ITM", "PE", "SENSEX", True, df_sensex, 20),
        ("SENSEX_ORB_BEARISH_5M_ITM", "PE", "SENSEX", True, df_sensex, 20),

        # --- 4 SENSEX Expansion Strategies ---
        ("SENSEX_BB_SQUEEZE_EXPLOSION_CE", "CE", "SENSEX", True, df_sensex, 20),
        ("SENSEX_BB_SQUEEZE_EXPLOSION_PE", "PE", "SENSEX", True, df_sensex, 20),
        ("SENSEX_OI_SHORT_SQUEEZE_CE", "CE", "SENSEX", False, df_sensex, 20),
        ("SENSEX_OI_LONG_UNWINDING_PE", "PE", "SENSEX", False, df_sensex, 20),

        # --- 5 BANKNIFTY 1M ATM Baseline Strategies ---
        ("BANKNIFTY_MACD_BULLISH_1M_ATM", "CE", "BANKNIFTY", False, df_banknifty, 30),
        ("BANKNIFTY_SUPPORT_BOUNCE_1M_ATM", "CE", "BANKNIFTY", False, df_banknifty, 30),
        ("BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "PE", "BANKNIFTY", False, df_banknifty, 30),
        ("BANKNIFTY_MACD_BEARISH_1M_ATM", "PE", "BANKNIFTY", False, df_banknifty, 30),
        ("BANKNIFTY_ORB_BEARISH_1M_ATM", "PE", "BANKNIFTY", False, df_banknifty, 30),

        # --- 6 BANKNIFTY 5M ITM Strategies ---
        ("BANKNIFTY_SUPPORT_BOUNCE_5M_ITM", "CE", "BANKNIFTY", True, df_banknifty, 30),
        ("BANKNIFTY_HEIKIN_ASHI_BULLISH_5M_ITM", "CE", "BANKNIFTY", True, df_banknifty, 30),
        ("BANKNIFTY_ORB_BULLISH_5M_ITM", "CE", "BANKNIFTY", True, df_banknifty, 30),
        ("BANKNIFTY_RESISTANCE_REJECTION_5M_ITM", "PE", "BANKNIFTY", True, df_banknifty, 30),
        ("BANKNIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "PE", "BANKNIFTY", True, df_banknifty, 30),
        ("BANKNIFTY_ORB_BEARISH_5M_ITM", "PE", "BANKNIFTY", True, df_banknifty, 30),

        # --- 4 BANKNIFTY Expansion Strategies ---
        ("BANKNIFTY_DUAL_SUPERTREND_BB_CE", "CE", "BANKNIFTY", True, df_banknifty, 30),
        ("BANKNIFTY_DUAL_SUPERTREND_BB_PE", "PE", "BANKNIFTY", True, df_banknifty, 30),
        ("BANKNIFTY_VWAP_BB_LIQUIDITY_REBOUND_CE", "CE", "BANKNIFTY", True, df_banknifty, 30),
        ("BANKNIFTY_GAMMA_WALL_BREAKOUT_PE", "PE", "BANKNIFTY", True, df_banknifty, 30),
    ]

    reports: dict[str, object] = {}
    trade_histories: dict[str, list] = {}

    print(f"Simulating all {len(strategy_defs)} strategies across 3 indices...")
    for i, (name, direction, idx, is_itm, df, lot_sz) in enumerate(strategy_defs, 1):
        s_t0 = time.time()
        rep, hist = simulate_strategy_vectorized(df, name, direction, index=idx, is_itm=is_itm, lot_size=lot_sz)
        reports[name] = rep
        trade_histories[name] = hist
        strike = "ITM" if is_itm else "ATM"
        s_dt = time.time() - s_t0
        print(f"  [{i:2d}/{len(strategy_defs)}] [{idx:9s}|{strike}] {name:<42} -> {rep.total_trades:3d} trades | Win: {rep.win_rate:5.1f}% | P&L: Rs.{rep.total_pnl:10,.2f} ({s_dt:.2f}s)")

    # 1. Report JSON
    report_dict = {
        name: {
            "strategy": r.strategy,
            "direction": r.direction,
            "total_trades": r.total_trades,
            "win_rate": r.win_rate,
            "profit_factor": r.profit_factor,
            "total_pnl": r.total_pnl,
            "max_drawdown_pct": r.max_drawdown_pct,
        }
        for name, r in reports.items()
    }
    (RESULTS_DIR / "report.json").write_text(json.dumps(report_dict, indent=2))

    # 2. Daily Report
    daily_breakdown = {
        name: build_daily_breakdown(hist)
        for name, hist in trade_histories.items()
    }
    (RESULTS_DIR / "daily_report.json").write_text(json.dumps(daily_breakdown, indent=2))

    # 3. Capital Requirements
    cap_reqs = required_capital_per_strategy(reports, trade_histories)
    for name, req in cap_reqs.items():
        is_sx = name.startswith("SENSEX")
        is_bn = name.startswith("BANKNIFTY")
        base_margin = 17000.0 if is_sx else (15000.0 if is_bn else 16000.0)
        req["avg_trade_risk"] = round(base_margin, 2)
        req["recommended_capital"] = round(base_margin + max(req.get("max_historical_drawdown", 0), 1000.0), 2)
    (RESULTS_DIR / "capital_requirements.json").write_text(json.dumps(cap_reqs, indent=2))

    # 4. Individual Trade Histories
    for name, hist in trade_histories.items():
        serializable = []
        for o in hist:
            serializable.append({
                "symbol": o.symbol,
                "strategy": getattr(o, "strategy", name),
                "entry_price": o.entry_price,
                "entry_time": o.entry_time.isoformat() if isinstance(o.entry_time, datetime) else str(o.entry_time),
                "exit_price": o.exit_price,
                "exit_time": o.exit_time.isoformat() if isinstance(o.exit_time, datetime) else str(o.exit_time),
                "exit_reason": o.exit_reason,
                "realized_pnl": o.realized_pnl,
                "qty": getattr(o, "qty", 1),
            })
        (RESULTS_DIR / f"{name}_history.json").write_text(json.dumps(serializable, indent=2))

    tot_trades = sum(r.total_trades for r in reports.values())
    tot_pnl = sum(r.total_pnl for r in reports.values())
    print("\n" + "=" * 80)
    print(f"SUCCESS: Generated Backtests for {len(reports)} Strategies | {tot_trades:,} Trades | Total Portfolio P&L: Rs.{tot_pnl:,.2f} in {time.time() - t0:.1f}s")
    print("=" * 80)


if __name__ == "__main__":
    main()
