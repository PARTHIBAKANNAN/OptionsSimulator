import sys
from pathlib import Path
from datetime import time as dtime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.config import Config
from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader, RiskLimitExceeded
from src.strategies.engine import create_nifty_strategies
from src.backtester.report import build_report

def run_experiment(df, strategies, cutoff_time=None):
    dm = DataManager(window_size=3000, underlying="NIFTY")
    traders = {}
    for s in strategies:
        traders[s.name] = PaperTrader(
            initial_capital=1_000_000,
            lot_size=65,
            max_concurrent_positions=None,
            max_daily_loss=None,
            max_trades_per_day_per_strategy=2,
            trailing_stop_enabled=True,
            enable_wallets=True
        )

    for row in df.itertuples(index=False):
        candle = Candle(timestamp=row.Timestamp, open=row.Open, high=row.High,
                         low=row.Low, close=row.Close, volume=int(row.Volume))
        dm.replay_candle(candle)
        state = dm.get_state()
        spot = state.get("nifty_price")
        if spot is None:
            continue

        t = candle.timestamp.time()

        for s in strategies:
            trader = traders[s.name]
            current_prices = {order.symbol: spot * 0.01 for order in trader.get_positions()}
            trader.update_positions(current_prices, timestamp=state["timestamp"], time_exit_mins=120)

            if cutoff_time and t < cutoff_time:
                continue

            sig = s.evaluate(state)
            if sig is not None:
                if s.last_signal_time and sig.timestamp - s.last_signal_time < pd.Timedelta(minutes=5):
                    pass
                else:
                    s.last_signal_time = sig.timestamp
                    stop_loss = max(sig.entry_price * 0.80, 0.05)
                    take_profit = sig.entry_price + 150.0
                    try:
                        trader.place_order(
                            symbol=sig.strike, side="BUY", qty=1,
                            price=sig.entry_price, stop_loss=stop_loss, take_profit=take_profit,
                            strategy=sig.strategy, timestamp=sig.timestamp,
                        )
                    except RiskLimitExceeded:
                        pass

    reports = {}
    for s in strategies:
        history = traders[s.name].get_trade_history()
        reports[s.name] = build_report(s.name, s.direction, history, 1_000_000)
    return reports

def main():
    print("[superfast_0925_experiment] Running 90-Day Backtest Comparison...")
    nifty_csv = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
    if not nifty_csv.exists():
        print(f"Error: {nifty_csv} not found")
        return

    df = pd.read_csv(nifty_csv)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    
    df_slice = df.tail(30000).reset_index(drop=True)
    strategies_base = create_nifty_strategies()
    strategies_exp = create_nifty_strategies()

    print(f"Dataset slice: {len(df_slice)} candles ({df_slice['Timestamp'].iloc[0]} to {df_slice['Timestamp'].iloc[-1]})")
    
    print("\n1. Running Baseline (09:15+ IST)...", flush=True)
    base_reports = run_experiment(df_slice, strategies_base, cutoff_time=None)

    print("2. Running Experiment (Avoiding 09:15 - 09:25 AM IST)...", flush=True)
    exp_reports = run_experiment(df_slice, strategies_exp, cutoff_time=dtime(9, 25))

    print("\n" + "="*105)
    print(f"{'NIFTY Strategy Name':<38} | {'Base Net PnL':<14} | {'Exp (09:25+) PnL':<16} | {'PnL Diff':<12} | {'Base Win%':<9} | {'Exp Win%'}")
    print("="*105)

    base_tot_net = 0.0
    exp_tot_net = 0.0
    base_tot_trades = 0
    exp_tot_trades = 0

    for s in create_nifty_strategies():
        name = s.name
        rb = base_reports[name]
        re = exp_reports[name]

        b_net = rb.net_pnl
        e_net = re.net_pnl
        diff = e_net - b_net

        base_tot_net += b_net
        exp_tot_net += e_net
        base_tot_trades += rb.total_trades
        exp_tot_trades += re.total_trades

        diff_str = f"+Rs.{diff:,.2f}" if diff >= 0 else f"-Rs.{abs(diff):,.2f}"
        print(f"{name:<38} | Rs.{b_net:>10,.2f} | Rs.{e_net:>12,.2f} | {diff_str:>12} | {rb.win_rate:>8.1f}% | {re.win_rate:>8.1f}%")

    print("-" * 105)
    net_diff = exp_tot_net - base_tot_net
    net_diff_str = f"+Rs.{net_diff:,.2f}" if net_diff >= 0 else f"-Rs.{abs(net_diff):,.2f}"
    print(f"{'TOTAL NIFTY PORTFOLIO':<38} | Rs.{base_tot_net:>10,.2f} | Rs.{exp_tot_net:>12,.2f} | {net_diff_str:>12}")
    print(f"Total Executed Trades: Baseline = {base_tot_trades} trades | Experiment (09:25+) = {exp_tot_trades} trades")
    print("="*105 + "\n")

if __name__ == '__main__':
    main()
