import sys
from pathlib import Path
from datetime import time as dtime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.config import Config
from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader
from src.strategies.engine import create_nifty_strategies
from src.backtester.report import build_report

def main():
    print("[fast_cutoff_analytics] Running Fast 15-Day Backtest Cutoff Comparison...")
    cfg = Config.load()
    nifty_csv = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
    if not nifty_csv.exists():
        print(f"Error: {nifty_csv} not found")
        return

    df = pd.read_csv(nifty_csv)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    
    # 15 trading days (~5800 candles) for instantaneous feedback
    df_slice = df.tail(5800).reset_index(drop=True)
    
    print(f"Dataset slice: {len(df_slice)} candles ({df_slice['Timestamp'].iloc[0]} to {df_slice['Timestamp'].iloc[-1]})")

    def run_pass(cutoff):
        dm = DataManager(window_size=3000, underlying="NIFTY")
        strategies = create_nifty_strategies()
        traders = {s.name: PaperTrader(initial_capital=1_000_000, lot_size=65, max_trades_per_day_per_strategy=2, trailing_stop_enabled=True) for s in strategies}

        for row in df_slice.itertuples(index=False):
            candle = Candle(timestamp=row.Timestamp, open=row.Open, high=row.High, low=row.Low, close=row.Close, volume=int(row.Volume))
            dm.replay_candle(candle)
            state = dm.get_state()
            spot = state.get("nifty_price")
            if spot is None:
                continue

            t = candle.timestamp.time()

            for s in strategies:
                trader = traders[s.name]
                prices = {o.symbol: spot * 0.01 for o in trader.get_positions()}
                trader.update_positions(prices, timestamp=state["timestamp"], time_exit_mins=120)

                if cutoff and t < cutoff:
                    continue

                sig = s.evaluate(state)
                if sig:
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

    print("Evaluating Baseline (09:15+ IST)...", flush=True)
    base_reports = run_pass(cutoff=None)
    
    print("Evaluating Experiment (09:25+ IST)...", flush=True)
    exp_reports = run_pass(cutoff=dtime(9, 25))

    print("\n" + "="*105)
    print(f"{'NIFTY Strategy Name':<38} | {'Base Net PnL':<14} | {'Exp (09:25+) PnL':<16} | {'PnL Diff':<12} | {'Base Win%':<9} | {'Exp Win%'}")
    print("="*105)

    b_tot, e_tot = 0.0, 0.0
    b_tr, e_tr = 0, 0

    for s in create_nifty_strategies():
        name = s.name
        rb, re = base_reports[name], exp_reports[name]
        diff = re.total_pnl - rb.total_pnl
        b_tot += rb.total_pnl
        e_tot += re.total_pnl
        b_tr += rb.total_trades
        e_tr += re.total_trades

        diff_str = f"+Rs.{diff:,.2f}" if diff >= 0 else f"-Rs.{abs(diff):,.2f}"
        print(f"{name:<38} | Rs.{rb.total_pnl:>10,.2f} | Rs.{re.total_pnl:>12,.2f} | {diff_str:>12} | {rb.win_rate:>8.1f}% | {re.win_rate:>8.1f}%")

    print("-" * 105)
    net_diff = e_tot - b_tot
    net_diff_str = f"+Rs.{net_diff:,.2f}" if net_diff >= 0 else f"-Rs.{abs(net_diff):,.2f}"
    print(f"{'TOTAL NIFTY PORTFOLIO':<38} | Rs.{b_tot:>10,.2f} | Rs.{e_tot:>12,.2f} | {net_diff_str:>12}")
    print(f"Total Executed Trades: Baseline = {b_tr} trades | Experiment (09:25+) = {e_tr} trades")
    print("="*105 + "\n")

if __name__ == '__main__':
    main()
