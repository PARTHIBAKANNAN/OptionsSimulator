"""
CLI entry point — backtesting only. Live paper trading now runs as the web app in backend/
(see docs/ARCHITECTURE.md): `python backend/run.py`, with the dashboard at
http://127.0.0.1:8001 (or https://trading-dashboard-1.duckdns.org/options-simulator/ once deployed).
"""
from pathlib import Path

import pandas as pd

from src.config import Config
from src.backtester.backtest_engine import BacktestEngine
from src.backtester.report import (
    load_capital_by_strategy, print_backtest_report, save_capital_requirements, save_daily_report,
    save_report,
)

PROJECT_ROOT = Path(__file__).resolve().parent
HISTORICAL_DATA_PATH = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
BACKTEST_REPORT_PATH = PROJECT_ROOT / "data" / "backtest_results" / "report.json"
DAILY_REPORT_PATH = PROJECT_ROOT / "data" / "backtest_results" / "daily_report.json"
CAPITAL_REPORT_PATH = PROJECT_ROOT / "data" / "backtest_results" / "capital_requirements.json"


def run_backtest(config: Config) -> None:
    if not HISTORICAL_DATA_PATH.exists():
        print(f"\nHistorical data not found at {HISTORICAL_DATA_PATH}")
        print("Run: python fetch_historical_data.py 90\n")
        return

    print("\nLoading historical data...")
    df = pd.read_csv(HISTORICAL_DATA_PATH, parse_dates=["Timestamp"])

    # Feed the PREVIOUS run's capital-per-strategy numbers in as the drawdown circuit breaker's
    # reference — no chicken-and-egg problem: the first-ever run just has no breaker until this
    # file exists, then each run's output informs the next run's risk limits.
    capital_by_strategy = load_capital_by_strategy(CAPITAL_REPORT_PATH)
    if capital_by_strategy:
        print(f"Loaded capital allocations from a prior run for {len(capital_by_strategy)} strategies "
              f"(drawdown circuit breaker active).")

    print(f"Running backtest over {len(df):,} candles...\n")
    engine = BacktestEngine(risk_params=config.risk_params, capital_by_strategy=capital_by_strategy)
    reports = engine.run(df)

    print_backtest_report(reports)
    save_report(reports, BACKTEST_REPORT_PATH)
    save_daily_report(engine.trade_histories, DAILY_REPORT_PATH)
    save_capital_requirements(reports, engine.trade_histories, CAPITAL_REPORT_PATH)
    print(f"\nFull report saved to {BACKTEST_REPORT_PATH}")
    print(f"Day-by-day breakdown saved to {DAILY_REPORT_PATH}")
    print(f"Required capital per strategy saved to {CAPITAL_REPORT_PATH}")


if __name__ == "__main__":
    run_backtest(Config.load())
