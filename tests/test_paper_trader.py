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


def test_stop_loss_fills_at_the_configured_stop_not_the_overshot_mark():
    # Exits are only checked once per candle close, so a fast move can already be well past the
    # stop by the time this runs — fill at stop_loss, not at whatever worse price was observed,
    # or every SL loss gets inflated beyond the intended risk (see docs/ARCHITECTURE.md).
    trader = PaperTrader(slippage_pct=0, lot_size=75)
    trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0, stop_loss=60.0, take_profit=100.0)
    closed = trader.update_positions({"NIFTY24500CE": 40.0})  # gapped 20pts past the 60 stop
    assert closed[0].exit_price == 60.0
    assert closed[0].realized_pnl == pytest.approx((60.0 - 65.0) * 1 * 75)


def test_take_profit_fills_at_the_configured_target_not_the_overshot_mark():
    trader = PaperTrader(slippage_pct=0, lot_size=75)
    trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0, stop_loss=60.0, take_profit=100.0)
    closed = trader.update_positions({"NIFTY24500CE": 140.0})  # gapped 40pts past the 100 target
    assert closed[0].exit_price == 100.0
    assert closed[0].realized_pnl == pytest.approx((100.0 - 65.0) * 1 * 75)


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


def test_trailing_stop_arms_after_activation_and_exits_on_pullback():
    trader = PaperTrader(slippage_pct=0, trailing_stop_enabled=True,
                          trailing_activation_pct=10, trailing_stop_pct=15)
    trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, take_profit=1000.0)

    # +20% run, past the 10% activation threshold — trailing arms, peak=120, floor=120*0.85=102.
    closed = trader.update_positions({"NIFTY24500CE": 120.0})
    assert closed == []

    # Pulls back below the trailing floor without ever hitting stop_loss/take_profit.
    closed = trader.update_positions({"NIFTY24500CE": 101.0})
    assert len(closed) == 1
    assert closed[0].exit_reason == "TRAILING_STOP"
    assert closed[0].exit_price == pytest.approx(102.0)


def test_trailing_stop_never_exits_below_breakeven_right_after_arming():
    # activation=10%, trail=15%: raw trail math right after arming ((1+.10)*(1-.15)=0.935) sits
    # BELOW entry — a "trailing stop" that locks in a loss defeats its purpose. Must clamp to
    # entry_price. See docs/ARCHITECTURE.md.
    trader = PaperTrader(slippage_pct=0, trailing_stop_enabled=True,
                          trailing_activation_pct=10, trailing_stop_pct=15)
    trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, take_profit=1000.0)

    # Peak just clears the +10% activation threshold — arms with peak=111, raw floor=94.35.
    closed = trader.update_positions({"NIFTY24500CE": 111.0})
    assert closed == []

    # Immediate pullback below the raw (unclamped) floor but still under entry+peak.
    closed = trader.update_positions({"NIFTY24500CE": 99.0})
    assert len(closed) == 1
    assert closed[0].exit_reason == "TRAILING_STOP"
    assert closed[0].exit_price == pytest.approx(100.0)  # clamped to breakeven, not 94.35
    assert closed[0].realized_pnl == pytest.approx(0.0)


def test_trailing_stop_does_not_arm_before_activation_threshold():
    trader = PaperTrader(slippage_pct=0, trailing_stop_enabled=True,
                          trailing_activation_pct=10, trailing_stop_pct=15)
    trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0)

    closed = trader.update_positions({"NIFTY24500CE": 105.0})  # only +5%, below activation
    assert closed == []
    closed = trader.update_positions({"NIFTY24500CE": 95.0})  # pulls back, but never armed
    assert closed == []


def test_max_trades_per_day_per_strategy_enforced():
    trader = PaperTrader(slippage_pct=0, max_concurrent_positions=10, max_trades_per_day_per_strategy=2)
    day = datetime(2026, 1, 1, 9, 20)
    trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0, strategy="MACD_BULLISH", timestamp=day)
    trader.place_order("NIFTY24600CE", "BUY", qty=1, price=40.0, strategy="MACD_BULLISH", timestamp=day)
    with pytest.raises(RiskLimitExceeded):
        trader.place_order("NIFTY24700CE", "BUY", qty=1, price=30.0, strategy="MACD_BULLISH", timestamp=day)

    # A different strategy on the same day is unaffected — the cap is per-strategy.
    trader.place_order("NIFTY24500PE", "BUY", qty=1, price=50.0, strategy="MACD_BEARISH", timestamp=day)


def test_max_trades_per_day_per_strategy_resets_next_day():
    trader = PaperTrader(slippage_pct=0, max_concurrent_positions=10, max_trades_per_day_per_strategy=2)
    day1 = datetime(2026, 1, 1, 9, 20)
    day2 = datetime(2026, 1, 2, 9, 20)
    trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0, strategy="MACD_BULLISH", timestamp=day1)
    trader.place_order("NIFTY24600CE", "BUY", qty=1, price=40.0, strategy="MACD_BULLISH", timestamp=day1)
    order = trader.place_order("NIFTY24700CE", "BUY", qty=1, price=30.0, strategy="MACD_BULLISH", timestamp=day2)
    assert order.status == "OPEN"


def test_cancel_order():
    trader = PaperTrader(slippage_pct=0)
    order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=65.0)
    assert trader.cancel_order(order.order_id) is True
    assert trader.orders[order.order_id].status == "CANCELLED"
    assert len(trader.get_positions()) == 0


def test_consecutive_loss_breaker_pauses_after_limit_and_resumes_after_cooldown():
    trader = PaperTrader(slippage_pct=0, max_concurrent_positions=10, max_trades_per_day_per_strategy=10,
                          consecutive_loss_limit=2, consecutive_loss_cooldown_days=1)
    day1 = datetime(2026, 1, 5, 9, 20)

    o1 = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day1)
    trader.close_position(o1.order_id, price=90.0, timestamp=day1)  # loss #1
    o2 = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day1)
    trader.close_position(o2.order_id, price=90.0, timestamp=day1)  # loss #2 -> breaker trips

    # Still day1: paused.
    with pytest.raises(RiskLimitExceeded):
        trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day1)

    # A different strategy is unaffected.
    other = trader.place_order("NIFTY24500PE", "BUY", qty=1, price=50.0, strategy="ORB_BEARISH", timestamp=day1)
    assert other.status == "OPEN"

    # After the 1-day cooldown, day2, it resumes.
    day2 = datetime(2026, 1, 6, 9, 20)
    resumed = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day2)
    assert resumed.status == "OPEN"


def test_consecutive_loss_breaker_resets_on_a_win():
    trader = PaperTrader(slippage_pct=0, max_concurrent_positions=10, max_trades_per_day_per_strategy=10,
                          consecutive_loss_limit=2, consecutive_loss_cooldown_days=1)
    day = datetime(2026, 1, 5, 9, 20)

    o1 = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day)
    trader.close_position(o1.order_id, price=90.0, timestamp=day)  # loss #1
    o2 = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day)
    trader.close_position(o2.order_id, price=110.0, timestamp=day)  # a win resets the streak

    # Never hit 2 losses in a row, so no pause.
    order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day)
    assert order.status == "OPEN"


def test_drawdown_breaker_pauses_once_capital_pct_breached():
    trader = PaperTrader(slippage_pct=0, lot_size=65, max_concurrent_positions=10,
                          max_trades_per_day_per_strategy=10, max_daily_loss=1_000_000,
                          max_drawdown_pct_of_capital=25, drawdown_cooldown_days=3,
                          capital_by_strategy={"ORB_BULLISH": 15000})
    day = datetime(2026, 1, 5, 9, 20)

    # A single loss of (100-70)*1*65 = 1,950 -> 13% of 15,000, under the 25% trigger.
    o1 = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day)
    trader.close_position(o1.order_id, price=70.0, timestamp=day)
    order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day)
    assert order.status == "OPEN"

    # A second loss of the same size pushes cumulative drawdown to 3,900 (26% of 15,000) -> trips.
    trader.close_position(order.order_id, price=70.0, timestamp=day)
    with pytest.raises(RiskLimitExceeded):
        trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day)

    # Resumes after the 3-day cooldown.
    later = day + timedelta(days=3)
    resumed = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=later)
    assert resumed.status == "OPEN"


def test_drawdown_breaker_grants_grace_trades_after_resuming_instead_of_re_trapping():
    # Regression test: drawdown is measured from the all-time peak, which only improves on a new
    # high. Without a grace window, resuming and then closing even one so-so trade (not a new
    # high) would immediately re-trigger another pause — trapping the strategy out of most of its
    # future trades. See docs/ARCHITECTURE.md.
    trader = PaperTrader(slippage_pct=0, lot_size=65, max_concurrent_positions=10,
                          max_trades_per_day_per_strategy=10, max_daily_loss=1_000_000,
                          max_drawdown_pct_of_capital=25, drawdown_cooldown_days=1,
                          drawdown_breaker_grace_trades=2, capital_by_strategy={"ORB_BULLISH": 15000})
    day = datetime(2026, 1, 5, 9, 20)

    # Two losses of 1,950 each -> cumulative drawdown 3,900 (26% of 15,000) -> trips.
    for _ in range(2):
        order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day)
        trader.close_position(order.order_id, price=70.0, timestamp=day)
    with pytest.raises(RiskLimitExceeded):
        trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day)

    # Resumes after the 1-day cooldown.
    day2 = day + timedelta(days=1)

    # Grace trade #1: another small loss, not a new high — must NOT re-trigger a pause.
    order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day2)
    trader.close_position(order.order_id, price=98.0, timestamp=day2)
    still_open = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day2)
    assert still_open.status == "OPEN"

    # Grace trade #2: same — still must not re-trigger.
    trader.close_position(still_open.order_id, price=98.0, timestamp=day2)
    still_open_2 = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day2)
    assert still_open_2.status == "OPEN"

    # Grace exhausted: a third non-recovering loss now re-evaluates, and drawdown is still past
    # the threshold, so it re-triggers as expected (the fix grants breathing room, not immunity).
    trader.close_position(still_open_2.order_id, price=98.0, timestamp=day2)
    with pytest.raises(RiskLimitExceeded):
        trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day2)


def test_drawdown_breaker_disabled_without_allocated_capital():
    trader = PaperTrader(slippage_pct=0, lot_size=65, max_concurrent_positions=10,
                          max_trades_per_day_per_strategy=10, max_daily_loss=1_000_000,
                          max_drawdown_pct_of_capital=25, drawdown_cooldown_days=3)
    day = datetime(2026, 1, 5, 9, 20)
    for _ in range(5):
        order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day)
        trader.close_position(order.order_id, price=50.0, timestamp=day)  # big repeated losses

    # No entry in capital_by_strategy for ORB_BULLISH -> breaker can't evaluate, never trips.
    order = trader.place_order("NIFTY24500CE", "BUY", qty=1, price=100.0, strategy="ORB_BULLISH", timestamp=day)
    assert order.status == "OPEN"
