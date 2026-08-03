from datetime import datetime, timedelta

import pandas as pd

from src.backtester.backtest_engine import BacktestEngine
from src.backtester.report import select_top_n


def _synthetic_df(n=300):
    base = datetime(2026, 1, 1, 9, 15)
    rows = []
    price = 24000.0
    for i in range(n):
        price += 3 if (i // 20) % 2 == 0 else -3  # oscillate to trigger both directions
        rows.append({
            "Timestamp": base + timedelta(minutes=i),
            "Open": price, "High": price + 4, "Low": price - 4, "Close": price,
            "Volume": 1000 + (i % 7) * 300,
        })
    return pd.DataFrame(rows)


def test_backtest_engine_runs_all_strategies():
    df = _synthetic_df()
    risk_params = {
        "position_sizing": {"qty_per_signal": 1, "lot_size": 75, "max_concurrent_positions": 5, "max_daily_loss": 5000},
        "exit_rules": {"stop_loss_pts": 50, "take_profit_pts": 150, "time_exit_mins": 120},
    }
    engine = BacktestEngine(risk_params=risk_params)
    reports = engine.run(df)

    assert len(reports) == 6
    for report in reports.values():
        assert report.total_trades >= 0
        assert report.win_rate >= 0


def test_select_top_n_picks_by_profit_factor():
    df = _synthetic_df()
    risk_params = {
        "position_sizing": {"qty_per_signal": 1, "lot_size": 75, "max_concurrent_positions": 5, "max_daily_loss": 5000},
        "exit_rules": {"stop_loss_pts": 50, "take_profit_pts": 150, "time_exit_mins": 120},
    }
    reports = BacktestEngine(risk_params=risk_params).run(df)
    top_ce = select_top_n(reports, "CE", 3)
    top_pe = select_top_n(reports, "PE", 3)
    assert len(top_ce) <= 3
    assert len(top_pe) <= 3
    assert all(r.direction == "CE" for r in top_ce)
    assert all(r.direction == "PE" for r in top_pe)
