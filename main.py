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
HISTORICAL_DIR = PROJECT_ROOT / "data" / "historical"
# Each of the 44 strategies must replay ITS OWN index's price history — feeding all of them the
# same (NIFTY) series was a real bug: SENSEX/BANKNIFTY strategies were being backtested against
# NIFTY spot prices with their own strike-step rounding applied on top. See BacktestEngine.run's
# docstring and docs/ARCHITECTURE.md.
HISTORICAL_PATHS = {
    "NIFTY": HISTORICAL_DIR / "nifty_365days.csv",
    "SENSEX": HISTORICAL_DIR / "sensex_365days.csv",
    "BANKNIFTY": HISTORICAL_DIR / "banknifty_365days.csv",
}
BACKTEST_REPORT_PATH = PROJECT_ROOT / "data" / "backtest_results" / "report.json"
DAILY_REPORT_PATH = PROJECT_ROOT / "data" / "backtest_results" / "daily_report.json"
CAPITAL_REPORT_PATH = PROJECT_ROOT / "data" / "backtest_results" / "capital_requirements.json"


def run_backtest(config: Config) -> None:
    missing = [name for name, path in HISTORICAL_PATHS.items() if not path.exists()]
    if missing:
        print(f"\nHistorical data missing for: {', '.join(missing)}")
        print("Run: python fetch_365day_historical.py\n")
        return

    print("\nLoading historical data for NIFTY, SENSEX, and BANKNIFTY...")
    data_by_index = {
        name: pd.read_csv(path, parse_dates=["Timestamp"]) for name, path in HISTORICAL_PATHS.items()
    }
    for name, df in data_by_index.items():
        print(f"  {name}: {len(df):,} candles, {df['Timestamp'].min()} -> {df['Timestamp'].max()}")

    # Feed the PREVIOUS run's capital-per-strategy numbers in as the drawdown circuit breaker's
    # reference — no chicken-and-egg problem: the first-ever run just has no breaker until this
    # file exists, then each run's output informs the next run's risk limits.
    capital_by_strategy = load_capital_by_strategy(CAPITAL_REPORT_PATH)
    if capital_by_strategy:
        print(f"Loaded capital allocations from a prior run for {len(capital_by_strategy)} strategies "
              f"(drawdown circuit breaker active).")

    total_candles = sum(len(df) for df in data_by_index.values())
    print(f"\nRunning backtest over {total_candles:,} candles across 3 indices...\n")
    engine = BacktestEngine(risk_params=config.risk_params, capital_by_strategy=capital_by_strategy)
    reports = engine.run(data_by_index)

    print_backtest_report(reports)
    save_report(reports, BACKTEST_REPORT_PATH)
    save_daily_report(engine.trade_histories, DAILY_REPORT_PATH)
    save_capital_requirements(reports, engine.trade_histories, CAPITAL_REPORT_PATH)
    print(f"\nFull report saved to {BACKTEST_REPORT_PATH}")
    print(f"Day-by-day breakdown saved to {DAILY_REPORT_PATH}")
    print(f"Required capital per strategy saved to {CAPITAL_REPORT_PATH}")


if __name__ == "__main__":
    run_backtest(Config.load())
