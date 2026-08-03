"""
CLI entry point — backtesting only. Live paper trading now runs as the web app in backend/
(see docs/ARCHITECTURE.md): `python backend/run.py`, with the dashboard at
http://127.0.0.1:8001 (or https://trading-dashboard-1.duckdns.org/options-simulator/ once deployed).
"""
from pathlib import Path

import pandas as pd

from src.config import Config
from src.backtester.backtest_engine import BacktestEngine
from src.backtester.report import print_backtest_report, save_report

PROJECT_ROOT = Path(__file__).resolve().parent
HISTORICAL_DATA_PATH = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
BACKTEST_REPORT_PATH = PROJECT_ROOT / "data" / "backtest_results" / "report.json"


def run_backtest(config: Config) -> None:
    if not HISTORICAL_DATA_PATH.exists():
        print(f"\nHistorical data not found at {HISTORICAL_DATA_PATH}")
        print("Run: python fetch_historical_data.py 90\n")
        return

    print("\nLoading historical data...")
    df = pd.read_csv(HISTORICAL_DATA_PATH, parse_dates=["Timestamp"])

    print(f"Running backtest over {len(df):,} candles...\n")
    engine = BacktestEngine(risk_params=config.risk_params)
    reports = engine.run(df)

    print_backtest_report(reports)
    save_report(reports, BACKTEST_REPORT_PATH)
    print(f"\nFull report saved to {BACKTEST_REPORT_PATH}")


if __name__ == "__main__":
    run_backtest(Config.load())
