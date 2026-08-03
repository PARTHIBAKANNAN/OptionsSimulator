from datetime import datetime, timedelta

import pytest

from src.simulator.paper_trader import PaperTrader, RiskLimitExceeded


def test_order_placed_successfully():
    trader = PaperTrader(slippage_pct=0)
    order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0)
    assert order.status == "OPEN"
    assert order.entry_price == 65.0
    assert len(trader.get_positions()) == 1


def test_slippage_applied_on_buy():
    trader = PaperTrader(slippage_pct=1.0)
    order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0)
    assert order.entry_price == pytest.approx(101.0)


def test_position_closed_on_stop_loss():
    trader = PaperTrader(slippage_pct=0, lot_size=75)
    order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0, stop_loss=60.0, take_profit=100.0)
    closed = trader.update_positions({"NIFTY24500CE": 59.0})
    assert len(closed) == 1
    assert closed[0].exit_reason == "STOP_LOSS"
    assert closed[0].status == "CLOSED"
    assert len(trader.get_positions()) == 0


def test_position_closed_on_take_profit():
    trader = PaperTrader(slippage_pct=0)
    trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0, stop_loss=60.0, take_profit=100.0)
    closed = trader.update_positions({"NIFTY24500CE": 105.0})
    assert closed[0].exit_reason == "TAKE_PROFIT"


def test_time_exit_closes_position():
    trader = PaperTrader(slippage_pct=0)
    entry_time = datetime(2026, 1, 1, 9, 20)
    trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0, timestamp=entry_time)
    later = entry_time + timedelta(minutes=121)
    closed = trader.update_positions({"NIFTY24500CE": 66.0}, timestamp=later, time_exit_mins=120)
    assert closed[0].exit_reason == "TIME_EXIT"


def test_pnl_calculated_correctly():
    trader = PaperTrader(slippage_pct=0, lot_size=75)
    order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0)
    trader.close_position(order.order_id, price=75.0)
    pnl = trader.get_pnl()
    assert pnl["realized_pnl"] == pytest.approx((75.0 - 65.0) * 1 * 75)


def test_max_concurrent_positions_enforced():
    trader = PaperTrader(slippage_pct=0, max_concurrent_positions=1)
    trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0)
    with pytest.raises(RiskLimitExceeded):
        trader.place_order("NIFTY24600CE", "BUY", qty=1, price=40.0)


def test_daily_loss_limit_enforced():
    trader = PaperTrader(slippage_pct=0, lot_size=75, max_daily_loss=100, max_concurrent_positions=10)
    order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0)
    trader.close_position(order.order_id, price=63.0)  # (63-65)*1*75 = -150, past the 100 daily limit
    with pytest.raises(RiskLimitExceeded):
        trader.place_order("NIFTY24600CE", "BUY", qty=1, price=40.0)


def test_cancel_order():
    trader = PaperTrader(slippage_pct=0)
    order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0)
    assert trader.cancel_order(order.order_id) is True
    assert trader.orders[order.order_id].status == "CANCELLED"
    assert len(trader.get_positions()) == 0
