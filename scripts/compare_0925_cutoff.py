import sys
from pathlib import Path
from datetime import time as dtime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.config import Config
from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader, RiskLimitExceeded
from src.strategies.engine import create_nifty_strategies, StrategyEngine
from src.backtester.report import build_report
from src.backtester.backtest_engine import BacktestEngine

def main():
    print("[compare_0925_cutoff] Running 90-Day NIFTY Backtest Comparison...")
    cfg = Config.load()
    
    nifty_csv = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
    if not nifty_csv.exists():
        print(f"Error: {nifty_csv} not found")
        return
        
    df = pd.read_csv(nifty_csv)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    
    strategies = create_nifty_strategies()
    
    # Run 1: Baseline (09:15+ IST)
    print("Running Baseline Backtest (09:15 - 15:15 IST)...", flush=True)
    base_reports = {}
    for strat in strategies:
        print(f"  > Baseline evaluating {strat.name}...", flush=True)
        base_engine = BacktestEngine(risk_params=cfg.risk_params, index="NIFTY")
        trader = base_engine._backtest_single(strat, df)
        history = trader.get_trade_history()
        base_reports[strat.name] = build_report(strat.name, strat.direction, history, 1_000_000)
    
    # Run 2: Experiment (09:25+ IST)
    print("Running Experiment Backtest (Avoiding 09:15 - 09:25 AM IST)...", flush=True)
    class ExpEngine(BacktestEngine):
        def _backtest_single(self, strategy, df):
            data_manager = DataManager(window_size=3000)
            trader = PaperTrader(
                initial_capital=self.initial_capital,
                lot_size=self.lot_size,
                max_concurrent_positions=None,
                max_daily_loss=None,
                max_trades_per_day_per_strategy=self.max_trades_per_day_per_strategy,
                trailing_stop_enabled=self.trailing_stop_enabled,
                trailing_activation_pct=self.trailing_activation_pct,
                trailing_stop_pct=self.trailing_stop_pct,
                capital_by_strategy=self.capital_by_strategy,
                logger=self.logger,
            )
            engine = StrategyEngine(strategies=[strategy], logger=self.logger)

            for row in df.itertuples(index=False):
                candle = Candle(timestamp=row.Timestamp, open=row.Open, high=row.High,
                                 low=row.Low, close=row.Close, volume=int(row.Volume))
                data_manager.replay_candle(candle)
                state = data_manager.get_state()
                if state["nifty_price"] is None:
                    continue

                current_prices = self._mark_to_market(trader, state)
                trader.update_positions(current_prices, timestamp=state["timestamp"],
                                         time_exit_mins=self.time_exit_mins)

                # AVOID TRADES BEFORE 09:25 AM IST
                if state["timestamp"].time() < dtime(9, 25):
                    continue

                for signal in engine.evaluate_all(state):
                    stop_loss = max(signal.entry_price * (1 - self.stop_loss_pct / 100), 0.05)
                    take_profit = signal.entry_price + self.take_profit_pts
                    try:
                        trader.place_order(
                            symbol=signal.strike, side="BUY", qty=self.qty_per_signal,
                            price=signal.entry_price, stop_loss=stop_loss, take_profit=take_profit,
                            strategy=signal.strategy, timestamp=signal.timestamp,
                        )
                    except RiskLimitExceeded:
                        continue

            return trader

    exp_reports = {}
    exp_engine = ExpEngine(risk_params=cfg.risk_params, index="NIFTY")
    for strat in strategies:
        print(f"  > Experiment evaluating {strat.name}...", flush=True)
        trader = exp_engine._backtest_single(strat, df)
        history = trader.get_trade_history()
        exp_reports[strat.name] = build_report(strat.name, strat.direction, history, 1_000_000)
    
    print("\n" + "="*105)
    print(f"{'NIFTY Strategy Name':<38} | {'Base Net PnL':<14} | {'Exp (09:25+) PnL':<16} | {'PnL Diff':<12} | {'Base Win%':<9} | {'Exp Win%'}")
    print("="*105)

    base_tot_net = 0.0
    exp_tot_net = 0.0
    base_tot_trades = 0
    exp_tot_trades = 0

    for strategy in strategies:
        name = strategy.name
        rb = base_reports.get(name)
        re = exp_reports.get(name)
        if not rb or not re:
            continue

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
