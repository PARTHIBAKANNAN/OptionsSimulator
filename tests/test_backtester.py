from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.backtester.backtest_engine import BacktestEngine
from src.backtester.report import (
    build_daily_breakdown, build_report, load_capital_by_strategy, required_capital_per_strategy, select_top_n,
)
from src.simulator.paper_trader import PaperTrader
from src.strategies.iron_fly_hedge import IronFlyHedge
from src.strategies.rsi_oversold_bullish import RSIOversoldBullish


def _synthetic_df(n=300):
    base = datetime(2026, 1, 6, 9, 15)
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
        "exit_rules": {"stop_loss_pct": 20, "take_profit_pts": 150, "time_exit_mins": 120},
    }
    engine = BacktestEngine(risk_params=risk_params)
    reports = engine.run(df)

    assert len(reports) == 5  # 4 directional strategies + IRON_FLY_HEDGE (enabled by default when unset)
    for report in reports.values():
        assert report.total_trades >= 0
        assert report.win_rate >= 0


def test_select_top_n_picks_by_profit_factor():
    df = _synthetic_df()
    risk_params = {
        "position_sizing": {"qty_per_signal": 1, "lot_size": 75, "max_concurrent_positions": 5, "max_daily_loss": 5000},
        "exit_rules": {"stop_loss_pct": 20, "take_profit_pts": 150, "time_exit_mins": 120},
    }
    reports = BacktestEngine(risk_params=risk_params).run(df)
    top_ce = select_top_n(reports, "CE", 3)
    top_pe = select_top_n(reports, "PE", 3)
    assert len(top_ce) <= 3
    assert len(top_pe) <= 3
    assert all(r.direction == "CE" for r in top_ce)
    assert all(r.direction == "PE" for r in top_pe)


def test_backtest_engine_exposes_trade_histories_per_strategy():
    df = _synthetic_df()
    risk_params = {
        "position_sizing": {"qty_per_signal": 1, "lot_size": 75, "max_concurrent_positions": 5, "max_daily_loss": 5000},
        "exit_rules": {"stop_loss_pct": 20, "take_profit_pts": 150, "time_exit_mins": 120},
    }
    engine = BacktestEngine(risk_params=risk_params)
    reports = engine.run(df)

    assert set(engine.trade_histories.keys()) == set(reports.keys())
    for name, report in reports.items():
        assert len(engine.trade_histories[name]) == report.total_trades


def _flat_expiry_day_df(n=370):
    # 2026-01-06 is a Tuesday, the current NIFTY weekly expiry day (see options_pricing.py) — spans
    # 09:15 through past the 15:15 force-exit time.
    base = datetime(2026, 1, 6, 9, 15)
    rows = []
    for i in range(n):
        price = 24000.0  # dead flat, so Iron Fly survives to its force-exit instead of SL/TP
        rows.append({
            "Timestamp": base + timedelta(minutes=i),
            "Open": price, "High": price + 1, "Low": price - 1, "Close": price,
            "Volume": 1000,
        })
    return pd.DataFrame(rows)


def test_backtest_engine_runs_iron_fly_on_expiry_day_and_takes_profit_on_a_flat_day():
    # Spot pinned dead flat at the ATM strike all day — theta decay alone crosses the 50%-of-credit
    # profit target well before the 15:15 force-exit, which is the economically correct outcome.
    df = _flat_expiry_day_df()
    risk_params = {
        "position_sizing": {"qty_per_signal": 1, "lot_size": 65, "max_concurrent_positions": 5, "max_daily_loss": 5000},
        "exit_rules": {"stop_loss_pct": 20, "take_profit_pts": 150, "time_exit_mins": 120},
        "iron_fly": {"enabled": True, "wing_width_pts": 200, "entry_time": "09:45", "force_exit_time": "15:15"},
    }
    engine = BacktestEngine(risk_params=risk_params)
    reports = engine.run(df)

    iron_fly_trades = engine.trade_histories["IRON_FLY_HEDGE"]
    assert len(iron_fly_trades) == 1
    assert iron_fly_trades[0].exit_reason == "PROFIT_TARGET"
    assert iron_fly_trades[0].realized_pnl > 0
    assert reports["IRON_FLY_HEDGE"].total_trades == 1


def test_backtest_engine_runs_iron_fly_and_force_exits_when_targets_are_unreachable():
    df = _flat_expiry_day_df()
    risk_params = {
        "position_sizing": {"qty_per_signal": 1, "lot_size": 65, "max_concurrent_positions": 5, "max_daily_loss": 5000},
        "exit_rules": {"stop_loss_pct": 20, "take_profit_pts": 150, "time_exit_mins": 120},
        "iron_fly": {
            "enabled": True, "wing_width_pts": 200, "entry_time": "09:45", "force_exit_time": "15:15",
            "profit_target_pct_of_credit": 99.9, "stop_loss_pct_of_max_loss": 99.9,
        },
    }
    engine = BacktestEngine(risk_params=risk_params)
    reports = engine.run(df)

    iron_fly_trades = engine.trade_histories["IRON_FLY_HEDGE"]
    assert len(iron_fly_trades) == 1
    assert iron_fly_trades[0].exit_reason == "FORCE_EXIT"
    assert reports["IRON_FLY_HEDGE"].total_trades == 1


def test_backtest_engine_iron_fly_can_be_disabled():
    df = _flat_expiry_day_df()
    risk_params = {
        "position_sizing": {"qty_per_signal": 1, "lot_size": 65, "max_concurrent_positions": 5, "max_daily_loss": 5000},
        "exit_rules": {"stop_loss_pct": 20, "take_profit_pts": 150, "time_exit_mins": 120},
        "iron_fly": {"enabled": False},
    }
    engine = BacktestEngine(risk_params=risk_params)
    reports = engine.run(df)

    assert "IRON_FLY_HEDGE" not in reports
    assert "IRON_FLY_HEDGE" not in engine.trade_histories


def test_build_daily_breakdown_groups_by_entry_date_and_accumulates_pnl():
    trader = PaperTrader(max_concurrent_positions=5)
    day1 = datetime(2026, 1, 5, 9, 15)
    day2 = datetime(2026, 1, 6, 9, 15)

    o1 = trader.place_order("NIFTY24000CE", "BUY", 1, 100, timestamp=day1)
    trader.close_position(o1.order_id, 120, timestamp=day1 + timedelta(minutes=30))  # +20/unit
    o2 = trader.place_order("NIFTY24000CE", "BUY", 1, 100, timestamp=day1 + timedelta(hours=1))
    trader.close_position(o2.order_id, 90, timestamp=day1 + timedelta(hours=2))  # -10/unit
    o3 = trader.place_order("NIFTY24000PE", "BUY", 1, 100, timestamp=day2)
    trader.close_position(o3.order_id, 150, timestamp=day2 + timedelta(minutes=30))  # +50/unit

    days = build_daily_breakdown(trader.get_trade_history())

    assert [d["date"] for d in days] == ["2026-01-05", "2026-01-06"]
    assert days[0]["trades"] == 2
    assert days[0]["wins"] == 1
    assert days[0]["losses"] == 1
    assert days[1]["trades"] == 1
    assert days[1]["cumulative_pnl"] == round(days[0]["pnl"] + days[1]["pnl"], 2)


def test_required_capital_directional_uses_single_trade_cost_plus_buffer():
    trader = PaperTrader(max_concurrent_positions=5, slippage_pct=0, lot_size=65)
    day = datetime(2026, 1, 5, 9, 15)
    order = trader.place_order("NIFTY24000CE", "BUY", 1, 160.0, timestamp=day)
    trader.close_position(order.order_id, 100.0, timestamp=day + timedelta(minutes=30))  # a loss
    history = trader.get_trade_history()
    report = build_report("TEST_STRATEGY", "CE", history, initial_capital=1_000_000)

    result = required_capital_per_strategy({"TEST_STRATEGY": report}, {"TEST_STRATEGY": history})

    info = result["TEST_STRATEGY"]
    avg_trade_risk = 160.0 * 65  # 10,400
    assert info["avg_trade_risk"] == pytest.approx(avg_trade_risk)
    # 10,400 * 1.3 = 13,520 -> rounded up to the nearest 1,000 = 14,000. NOT drawdown-based.
    assert info["recommended_capital"] == 14000
    assert info["max_historical_drawdown"] == report.max_drawdown  # still surfaced, just not driving the number


def test_required_capital_iron_fly_uses_max_loss_not_premium():
    hedge = IronFlyHedge(lot_size=65, qty=1)
    hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": datetime(2026, 1, 6, 9, 45)})
    closed = hedge.check_exit({"nifty_price": 25000.0, "timestamp": datetime(2026, 1, 6, 10, 0)})
    history = [closed]
    report = build_report("IRON_FLY_HEDGE", "HEDGE", history, initial_capital=1_000_000)

    result = required_capital_per_strategy({"IRON_FLY_HEDGE": report}, {"IRON_FLY_HEDGE": history})

    info = result["IRON_FLY_HEDGE"]
    assert info["avg_trade_risk"] == pytest.approx(closed.max_loss * 65)
    assert info["recommended_capital"] > 0


def test_required_capital_skips_strategies_with_no_trades():
    report = build_report("NO_TRADES", "CE", [], initial_capital=1_000_000)
    result = required_capital_per_strategy({"NO_TRADES": report}, {"NO_TRADES": []})
    assert "NO_TRADES" not in result


def test_load_capital_by_strategy_flattens_recommended_capital(tmp_path):

    path = tmp_path / "capital_requirements.json"
    path.write_text('{"ORB_BULLISH": {"avg_trade_risk": 100.0, "max_historical_drawdown": 5000.0, "recommended_capital": 20000.0}}')

    result = load_capital_by_strategy(path)
    assert result == {"ORB_BULLISH": 20000.0}


def test_load_capital_by_strategy_missing_file_returns_empty(tmp_path):

    result = load_capital_by_strategy(tmp_path / "does_not_exist.json")
    assert result == {}


def test_backtest_engine_wires_circuit_breaker_config_into_paper_trader():
    df = _synthetic_df()
    risk_params = {
        "position_sizing": {"qty_per_signal": 1, "lot_size": 65, "max_concurrent_positions": 5, "max_daily_loss": 5000},
        "exit_rules": {"stop_loss_pct": 20, "take_profit_pts": 150, "time_exit_mins": 120},
        "iron_fly": {"enabled": False},
        "circuit_breaker": {"consecutive_loss_limit": 3, "max_drawdown_pct_of_capital": 25},
    }
    engine = BacktestEngine(risk_params=risk_params, capital_by_strategy={"RSI_OVERSOLD_BULLISH": 15000})
    trader = engine._backtest_single(RSIOversoldBullish(), df)

    assert trader.consecutive_loss_limit == 3
    assert trader.max_drawdown_pct_of_capital == 25
    assert trader.capital_by_strategy == {"RSI_OVERSOLD_BULLISH": 15000}
