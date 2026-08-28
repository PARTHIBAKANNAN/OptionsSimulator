import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader
from src.strategies.engine import create_all_strategies, create_nifty_strategies
from src.backtester.report import build_report

def calculate_poc(candles_window):
    """Calculates Point of Control (POC) - the price level with highest volume in window."""
    if not candles_window:
        return None
    price_bins = {}
    for c in candles_window:
        # Group price into 10-point bins
        bin_price = round(c.close / 10.0) * 10.0
        price_bins[bin_price] = price_bins.get(bin_price, 0) + c.volume
    if not price_bins:
        return None
    # Price bin with max volume
    return max(price_bins, key=price_bins.get)

def run_proof_experiment(df, variant="baseline"):
    dm = DataManager(window_size=3000, underlying="NIFTY")
    strategies = create_nifty_strategies()
    traders = {s.name: PaperTrader(initial_capital=1_000_000, lot_size=65, max_trades_per_day_per_strategy=2, trailing_stop_enabled=True) for s in strategies}

    session_candles = []
    current_day = None

    for row in df.itertuples(index=False):
        candle = Candle(timestamp=row.Timestamp, open=row.Open, high=row.High, low=row.Low, close=row.Close, volume=int(row.Volume))
        
        # Reset session window on new day
        day = candle.timestamp.date()
        if day != current_day:
            current_day = day
            session_candles = []
        session_candles.append(candle)

        dm.replay_candle(candle)
        state = dm.get_state()
        spot = state.get("nifty_price")
        if spot is None:
            continue

        indicators = state.get("indicators", {})
        ema9 = indicators.get("ema_9_1m")
        poc = calculate_poc(session_candles[-60:]) if len(session_candles) >= 15 else spot  # 60-candle rolling POC

        for s in strategies:
            trader = traders[s.name]
            prices = {o.symbol: spot * 0.01 for o in trader.get_positions()}
            trader.update_positions(prices, timestamp=state["timestamp"], time_exit_mins=120)

            sig = s.evaluate(state)
            if sig:
                # Apply Variant Enhancements
                if variant == "ema9_only":
                    if ema9 is None:
                        continue
                    # Require price to be on correct side of 9-EMA
                    if sig.direction == "CE" and spot < ema9:
                        continue
                    if sig.direction == "PE" and spot > ema9:
                        continue
                elif variant == "poc_retest":
                    # Require price to be within 0.4% of intraday POC volume node
                    if poc and abs(spot - poc) / spot > 0.004:
                        continue
                elif variant == "combined_pro":
                    if ema9 is None:
                        continue
                    # Require both EMA 9 trend + POC retest proximity (within 0.5%)
                    if sig.direction == "CE" and spot < ema9:
                        continue
                    if sig.direction == "PE" and spot > ema9:
                        continue
                    if poc and abs(spot - poc) / spot > 0.005:
                        continue

                if not (s.last_signal_time and sig.timestamp - s.last_signal_time < pd.Timedelta(minutes=5)):
                    s.last_signal_time = sig.timestamp
                    try:
                        trader.place_order(symbol=sig.strike, side="BUY", qty=1, price=sig.entry_price, stop_loss=sig.entry_price*0.8, take_profit=sig.entry_price+150, strategy=sig.strategy, timestamp=sig.timestamp)
                    except Exception:
                        pass

    reports = {}
    for s in strategies:
        history = traders[s.name].get_trade_history()
        reports[s.name] = build_report(s.name, s.direction, history, 1_000_000)
    return reports

def main():
    print("=== QUANT PROOF OF CONCEPT: EMA9 vs POC vs COMBINED SUITE ===")
    nifty_csv = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
    if not nifty_csv.exists():
        print(f"Error: {nifty_csv} not found")
        return

    df = pd.read_csv(nifty_csv)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    
    # 6000-candle dataset slice (approx 15 trading days) for fast, deep comparison
    df_slice = df.tail(6000).reset_index(drop=True)
    print(f"Dataset: {len(df_slice)} candles ({df_slice['Timestamp'].iloc[0]} to {df_slice['Timestamp'].iloc[-1]})\n")

    print("1. Running Baseline Strategies...", flush=True)
    base = run_proof_experiment(df_slice, variant="baseline")

    print("2. Running Variant 1: EMA 9 Trend Confirmation...", flush=True)
    v_ema9 = run_proof_experiment(df_slice, variant="ema9_only")

    print("3. Running Variant 2: Volume Profile (POC) Retest Filter...", flush=True)
    v_poc = run_proof_experiment(df_slice, variant="poc_retest")

    print("4. Running Variant 3: Combined Pro Suite (EMA 9 + POC Retest)...", flush=True)
    v_comb = run_proof_experiment(df_slice, variant="combined_pro")

    print("\n" + "="*125)
    print(f"{'NIFTY Strategy Name':<36} | {'Baseline Net PnL':<16} | {'EMA9 Filter PnL':<16} | {'POC Retest PnL':<16} | {'Combined Pro PnL':<16} | {'Win% Change'}")
    print("="*125)

    strategies = create_nifty_strategies()
    b_tot, e9_tot, poc_tot, comb_tot = 0.0, 0.0, 0.0, 0.0
    b_tr, comb_tr = 0, 0

    for s in strategies:
        name = s.name
        rb = base[name]
        re9 = v_ema9[name]
        rpoc = v_poc[name]
        rcomb = v_comb[name]

        b_tot += rb.total_pnl
        e9_tot += re9.total_pnl
        poc_tot += rpoc.total_pnl
        comb_tot += rcomb.total_pnl
        b_tr += rb.total_trades
        comb_tr += rcomb.total_trades

        win_diff = rcomb.win_rate - rb.win_rate
        win_str = f"{win_diff:+.1f}%"

        print(f"{name:<36} | Rs.{rb.total_pnl:>12,.2f} | Rs.{re9.total_pnl:>12,.2f} | Rs.{rpoc.total_pnl:>12,.2f} | Rs.{rcomb.total_pnl:>12,.2f} | {rb.win_rate:.1f}% -> {rcomb.win_rate:.1f}% ({win_str})")

    print("-" * 125)
    net_diff = comb_tot - b_tot
    net_diff_str = f"+Rs.{net_diff:,.2f}" if net_diff >= 0 else f"-Rs.{abs(net_diff):,.2f}"
    print(f"{'TOTAL PORTFOLIO SUMMARY':<36} | Rs.{b_tot:>12,.2f} | Rs.{e9_tot:>12,.2f} | Rs.{poc_tot:>12,.2f} | Rs.{comb_tot:>12,.2f} | Net Diff: {net_diff_str}")
    print(f"Total Trades: Baseline = {b_tr} trades | Combined Pro Suite = {comb_tr} trades")
    print("="*125 + "\n")

if __name__ == '__main__':
    main()
