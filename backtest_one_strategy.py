"""One-off: backtest a single strategy class against the full historical CSV and write its
trade-by-trade history to data/backtest_results/{NAME}_history.json. Used to fan out full-year
backtests across strategies in parallel processes (each BaseStrategy backtest is independent --
own DataManager/PaperTrader -- so there's no shared state to worry about running them concurrently).
Usage: python backtest_one_strategy.py <module_path> <ClassName>
"""
import importlib
import json
import sys
import time
from pathlib import Path

import pandas as pd

from src.backtester.backtest_engine import BacktestEngine
from src.backtester.report import build_report
from src.config import Config

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
RESULTS_DIR = PROJECT_ROOT / "data" / "backtest_results"


def main(module_path: str, class_name: str) -> None:
    module = importlib.import_module(module_path)
    strategy_cls = getattr(module, class_name)
    strategy = strategy_cls()

    config = Config.load()
    df = pd.read_csv(DATA_PATH, parse_dates=["Timestamp"])

    t0 = time.time()
    engine = BacktestEngine(risk_params=config.risk_params)
    trader = engine._backtest_single(strategy, df)
    history = trader.get_trade_history()
    r = build_report(strategy.name, strategy.direction, history, 1_000_000)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{strategy.name}_history.json"
    out_path.write_text(json.dumps([
        {"entry_time": str(o.entry_time), "exit_time": str(o.exit_time),
         "realized_pnl": o.realized_pnl, "exit_reason": o.exit_reason}
        for o in history
    ], indent=2))

    print(f"[{strategy.name}] ({time.time() - t0:.1f}s) trades={r.total_trades} "
          f"win_rate={r.win_rate}% profit_factor={r.profit_factor} total_pnl={r.total_pnl} "
          f"max_dd={r.max_drawdown} max_dd_pct={r.max_drawdown_pct}%", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])