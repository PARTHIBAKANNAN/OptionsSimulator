from datetime import datetime

from src.strategies.iron_fly_hedge import IronFlyHedge

# 2026-01-06 is a Tuesday — the current NIFTY weekly expiry day (NSE moved Thursday -> Tuesday
# 2025-09-01, see src/utils/options_pricing.py). 2026-01-05 is the Monday before it.
TUESDAY = datetime(2026, 1, 6, 9, 45)
MONDAY = datetime(2026, 1, 5, 9, 45)


def test_does_not_enter_on_a_non_expiry_day():
    hedge = IronFlyHedge()
    assert hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": MONDAY}) is None


def test_does_not_enter_on_the_old_regimes_expiry_weekday():
    # Thursday used to be expiry day (pre-2025-09-01) — it no longer is, so a Thursday in the
    # current regime must not trigger an entry even though it once would have.
    hedge = IronFlyHedge()
    thursday_now = datetime(2026, 1, 8, 9, 45)
    assert hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": thursday_now}) is None


def test_enters_on_the_old_regimes_thursday_expiry_before_the_2025_change():
    hedge = IronFlyHedge()
    old_thursday = datetime(2025, 8, 28, 9, 45)  # the last Thursday expiry before the 2025-09-01 switch
    position = hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": old_thursday})
    assert position is not None


def test_does_not_enter_before_configured_entry_time():
    hedge = IronFlyHedge(entry_time=datetime(2026, 1, 6, 9, 45).time())
    early = datetime(2026, 1, 6, 9, 20)
    assert hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": early}) is None


def test_enters_on_expiry_day_with_four_legs_and_positive_credit():
    hedge = IronFlyHedge(wing_width_pts=200, strike_step=100)
    position = hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": TUESDAY})

    assert position is not None
    assert len(position.legs) == 4
    sides = {(leg.strike, leg.option_type): leg.side for leg in position.legs}
    assert sides[(24800, "CE")] == "SELL"
    assert sides[(24800, "PE")] == "SELL"
    assert sides[(25000, "CE")] == "BUY"
    assert sides[(24600, "PE")] == "BUY"
    assert position.net_credit > 0  # short ATM straddle collects more than the wings cost
    assert position.max_loss > 0


def test_does_not_enter_twice_on_the_same_expiry_day():
    hedge = IronFlyHedge()
    hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": TUESDAY})
    hedge.position = None  # simulate it having already been closed once today
    later = datetime(2026, 1, 6, 11, 0)
    assert hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": later}) is None


def test_force_exits_at_the_configured_time_if_nothing_else_triggered():
    hedge = IronFlyHedge(profit_target_pct_of_credit=99, stop_loss_pct_of_max_loss=99,
                          force_exit_time=datetime(2026, 1, 6, 15, 15).time())
    hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": TUESDAY})
    at_close = datetime(2026, 1, 6, 15, 15)
    closed = hedge.check_exit({"nifty_price": 24800.0, "timestamp": at_close})
    assert closed is not None
    assert closed.exit_reason == "FORCE_EXIT"
    assert closed.status == "CLOSED"
    assert hedge.position is None


def test_exits_early_on_profit_target_when_spot_stays_near_the_atm_strike():
    hedge = IronFlyHedge()
    hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": TUESDAY})
    # Spot pinned at the ATM strike, well before force-exit — heavy same-day theta decay alone
    # should capture >=50% of the credit.
    still_flat = datetime(2026, 1, 6, 14, 30)
    closed = hedge.check_exit({"nifty_price": 24800.0, "timestamp": still_flat})
    assert closed is not None
    assert closed.exit_reason == "PROFIT_TARGET"
    assert closed.realized_pnl > 0


def test_exits_early_on_stop_loss_when_spot_runs_through_a_wing():
    hedge = IronFlyHedge()
    hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": TUESDAY})
    # Spot jumps 200pts past the call wing shortly after entry.
    breakout = datetime(2026, 1, 6, 10, 0)
    closed = hedge.check_exit({"nifty_price": 25000.0, "timestamp": breakout})
    assert closed is not None
    assert closed.exit_reason == "STOP_LOSS"
    assert closed.realized_pnl < 0


def test_check_exit_is_a_noop_with_no_open_position():
    hedge = IronFlyHedge()
    assert hedge.check_exit({"nifty_price": 24800.0, "timestamp": TUESDAY}) is None


def test_skips_entry_on_an_abnormally_volatile_morning():
    hedge = IronFlyHedge(max_vol_regime_ratio_to_enter=1.5)
    state = {"nifty_price": 24800.0, "timestamp": TUESDAY, "indicators": {"vol_regime_ratio": 2.0}}
    assert hedge.maybe_enter(state) is None


def test_still_enters_on_a_calm_morning_with_the_vol_gate_configured():
    hedge = IronFlyHedge(max_vol_regime_ratio_to_enter=1.5)
    state = {"nifty_price": 24800.0, "timestamp": TUESDAY, "indicators": {"vol_regime_ratio": 0.8}}
    assert hedge.maybe_enter(state) is not None


def test_vol_gate_does_not_retry_later_the_same_day_after_skipping():
    hedge = IronFlyHedge(max_vol_regime_ratio_to_enter=1.5)
    hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": TUESDAY, "indicators": {"vol_regime_ratio": 2.0}})
    later_calm = datetime(2026, 1, 6, 11, 0)
    # Even though it calmed down later, the day was already consumed by the morning skip.
    assert hedge.maybe_enter({"nifty_price": 24800.0, "timestamp": later_calm,
                               "indicators": {"vol_regime_ratio": 0.5}}) is None


def test_vol_gate_disabled_by_default_ignores_missing_regime_data():
    hedge = IronFlyHedge()
    state = {"nifty_price": 24800.0, "timestamp": TUESDAY}  # no "indicators" key at all
    assert hedge.maybe_enter(state) is not None
