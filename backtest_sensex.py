"""One-off: backtest all 6 SENSEX strategies against a SENSEX historical CSV, writing each
trade-by-trade history to data/backtest_results/{NAME}_history.json -- mirrors
backtest_one_strategy.py but fixed to the SENSEX strategy set, SENSEX lot size, and SENSEX's own
expiry-day rule (see src/utils/options_pricing.py's INDEX_EXPIRY_RULES).

Usage: python backtest_sensex.py [path/to/sensex_historical.csv]
Defaults to data/historical/sensex_1year.csv, which does not exist yet -- see
docs/ARCHITECTURE.md for the blocker (Fyers symbol for the SENSEX index is still unconfirmed).
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd

from src.backtester.backtest_engine import BacktestEngine
from src.backtester.report import build_report
from src.config import Config
from src.strategies.sensex_strategies import create_all_sensex_strategies

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "historical" / "sensex_1year.csv"
RESULTS_DIR = PROJECT_ROOT / "data" / "backtest_results"

# Recently changed to 20 (was smaller) -- see docs/ARCHITECTURE.md. Kept separate from
# config/risk_params.json's NIFTY lot_size (65) rather than overwriting the shared config.
SENSEX_LOT_SIZE = 20


def main(data_path: Path) -> None:
    if not data_path.exists():
        raise SystemExit(
            f"SENSEX historical data not found at {data_path}. Need the correct Fyers symbol for "
            f"the SENSEX index first (see docs/ARCHITECTURE.md) -- NIFTY's fetch script "
            f"(fetch_historical_data.py) can be pointed at it once confirmed."
        )

    config = Config.load()
    risk_params = dict(config.risk_params)
    risk_params["position_sizing"] = {**risk_params["position_sizing"], "lot_size": SENSEX_LOT_SIZE}

    df = pd.read_csv(data_path, parse_dates=["Timestamp"])

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for strategy in create_all_sensex_strategies():
        t0 = time.time()
        engine = BacktestEngine(risk_params=risk_params, index="SENSEX")
        trader = engine._backtest_single(strategy, df)
        history = trader.get_trade_history()
        r = build_report(strategy.name, strategy.direction, history, 1_000_000)

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
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA_PATH
    main(path)
