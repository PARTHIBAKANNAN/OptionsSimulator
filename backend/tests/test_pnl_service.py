from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app import pnl_service


def test_build_strategy_summary_computes_win_rate_and_net_pnl():
    db_rows = {"MACD_BULLISH": {"trades": 4, "wins": 3, "gross_pnl": 1000.0, "charges": 40.0}}
    wallets = {"MACD_BULLISH": {"balance": 84960.0, "allocated_capital": 85000.0, "pnl_in_wallet": -40.0}}

    rows = pnl_service.build_strategy_summary(["MACD_BULLISH"], db_rows, wallets)

    assert rows == [{
        "strategy": "MACD_BULLISH", "trades": 4, "win_rate": 75.0,
        "gross_pnl": 1000.0, "charges": 40.0, "net_pnl": 960.0,
        "wallet_balance": 84960.0, "allocated_capital": 85000.0,
    }]


def test_build_strategy_summary_includes_strategies_with_zero_trades():
    rows = pnl_service.build_strategy_summary(["ORB_BULLISH"], {}, {})
    assert rows == [{
        "strategy": "ORB_BULLISH", "trades": 0, "win_rate": 0.0,
        "gross_pnl": 0.0, "charges": 0.0, "net_pnl": 0.0,
        "wallet_balance": None, "allocated_capital": None,
    }]


def test_combine_totals_sums_across_strategies():
    strategy_rows = [
        {"strategy": "A", "trades": 2, "gross_pnl": 500.0, "charges": 10.0, "net_pnl": 490.0,
         "wallet_balance": 84990.0, "allocated_capital": 85000.0},
        {"strategy": "B", "trades": 1, "gross_pnl": -200.0, "charges": 5.0, "net_pnl": -205.0,
         "wallet_balance": 19795.0, "allocated_capital": 20000.0},
    ]
    combined = pnl_service.combine_totals(strategy_rows)
    assert combined == {
        "trades": 3, "gross_pnl": 300.0, "charges": 15.0, "net_pnl": 285.0,
        "wallet_balance": 104785.0, "allocated_capital": 105000.0,
    }


def test_combine_totals_wallet_fields_are_none_when_no_strategy_has_a_wallet():
    strategy_rows = [{"strategy": "A", "trades": 0, "gross_pnl": 0.0, "charges": 0.0,
                       "net_pnl": 0.0, "wallet_balance": None, "allocated_capital": None}]
    combined = pnl_service.combine_totals(strategy_rows)
    assert combined["wallet_balance"] is None
    assert combined["allocated_capital"] is None


@pytest.mark.asyncio
async def test_strategy_pnl_rows_returns_empty_dict_without_a_configured_db():
    with patch("backend.app.pnl_service.db.get_pool", side_effect=RuntimeError):
        assert await pnl_service.strategy_pnl_rows(date(2026, 8, 1), date(2026, 8, 6)) == {}


@pytest.mark.asyncio
async def test_strategy_pnl_rows_keys_by_strategy_name():
    fake_pool = MagicMock()
    fake_pool.fetch = AsyncMock(return_value=[
        {"strategy": "MACD_BULLISH", "trades": 2, "wins": 1, "gross_pnl": 100.0, "charges": 8.0},
    ])
    with patch("backend.app.pnl_service.db.get_pool", return_value=fake_pool):
        rows = await pnl_service.strategy_pnl_rows(date(2026, 8, 1), date(2026, 8, 6))
    assert rows["MACD_BULLISH"]["trades"] == 2


@pytest.mark.asyncio
async def test_daily_net_pnl_series_formats_dates_as_iso_strings():
    fake_pool = MagicMock()
    fake_pool.fetch = AsyncMock(return_value=[{"day": date(2026, 8, 4), "net_pnl": 123.45}])
    with patch("backend.app.pnl_service.db.get_pool", return_value=fake_pool):
        series = await pnl_service.daily_net_pnl_series(date(2026, 8, 1), date(2026, 8, 6))
    assert series == [{"date": "2026-08-04", "net_pnl": 123.45}]


@pytest.mark.asyncio
async def test_closed_trades_in_range_returns_empty_list_without_a_configured_db():
    with patch("backend.app.pnl_service.db.get_pool", side_effect=RuntimeError):
        assert await pnl_service.closed_trades_in_range(date(2026, 8, 1), date(2026, 8, 6)) == []


def test_build_workbook_has_the_three_expected_sheets():
    strategies = pnl_service.build_strategy_summary(["MACD_BULLISH"],
                                                      {"MACD_BULLISH": {"trades": 1, "wins": 1, "gross_pnl": 50.0, "charges": 5.0}},
                                                      {})
    combined = pnl_service.combine_totals(strategies)
    trades = [{
        "order_id": "abc", "strategy": "MACD_BULLISH", "symbol": "NIFTY24500CE", "qty": 1,
        "entry_price": 100.0, "entry_time": None, "exit_price": 150.0, "exit_time": None,
        "exit_reason": "TAKE_PROFIT", "realized_pnl": 50.0, "entry_charges": 3.0, "exit_charges": 2.0,
    }]

    wb = pnl_service.build_workbook(strategies, combined, trades, date(2026, 8, 1), date(2026, 8, 6))

    assert wb.sheetnames == ["Summary", "By Strategy", "Trades"]
    trades_sheet = wb["Trades"]
    assert trades_sheet.cell(row=1, column=1).value == "Order ID"
    assert trades_sheet.cell(row=2, column=1).value == "abc"
    # net P&L = 50 - (3 + 2) = 45
    assert trades_sheet.cell(row=2, column=12).value == 45.0
