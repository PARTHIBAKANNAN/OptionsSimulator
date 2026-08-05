from datetime import date, datetime

from src.utils.options_pricing import (
    black_scholes_price, format_display_symbol, is_expiry_day, next_weekly_expiry_date,
    next_weekly_expiry_days, parse_option_symbol,
)


def test_parse_option_symbol():
    assert parse_option_symbol("NIFTY24500CE") == (24500.0, "CE")
    assert parse_option_symbol("NIFTY24500PE") == (24500.0, "PE")
    assert parse_option_symbol("garbage") == (None, None)


def test_black_scholes_ce_increases_with_spot():
    low = black_scholes_price(spot=24000, strike=24500, days_to_expiry=5, option_type="CE")
    high = black_scholes_price(spot=25000, strike=24500, days_to_expiry=5, option_type="CE")
    assert high > low


def test_black_scholes_at_expiry_is_pure_intrinsic():
    assert black_scholes_price(spot=24600, strike=24500, days_to_expiry=0, option_type="CE") == 100.0
    assert black_scholes_price(spot=24400, strike=24500, days_to_expiry=0, option_type="CE") == 0.0
    assert black_scholes_price(spot=24400, strike=24500, days_to_expiry=0, option_type="PE") == 100.0


# ---- Post-2025-09-01 (current regime): NIFTY weekly expiry is Tuesday -----------------------

def test_next_weekly_expiry_days_on_a_monday_counts_forward_to_tuesday():
    monday = datetime(2026, 8, 3, 10, 0)  # 2026-08-03 is a Monday
    assert next_weekly_expiry_days(monday) == 1.0


def test_next_weekly_expiry_days_on_tuesday_morning_is_a_small_fraction_not_seven():
    # 2026-08-04 is a Tuesday. Regression test: this used to unconditionally treat Thursday as
    # expiry regardless of date, overpricing every option traded on the actual expiry day — see
    # docs/ARCHITECTURE.md.
    tuesday_morning = datetime(2026, 8, 4, 9, 20)
    days = next_weekly_expiry_days(tuesday_morning)
    assert 0 < days < 0.3


def test_next_weekly_expiry_days_on_tuesday_after_close_rolls_to_next_week():
    tuesday_evening = datetime(2026, 8, 4, 16, 0)
    assert next_weekly_expiry_days(tuesday_evening) == 7.0


def test_is_expiry_day_post_change():
    assert is_expiry_day(datetime(2026, 8, 4, 10, 0)) is True  # Tuesday
    assert is_expiry_day(datetime(2026, 8, 4, 16, 0)) is False  # past close
    assert is_expiry_day(datetime(2026, 8, 3, 10, 0)) is False  # Monday
    assert is_expiry_day(datetime(2026, 8, 6, 10, 0)) is False  # Thursday — no longer expiry day


# ---- Pre-2025-09-01 (old regime): NIFTY weekly expiry was Thursday ---------------------------

def test_next_weekly_expiry_days_before_the_change_still_uses_thursday():
    # 2025-08-25 is a Monday, well before the 2025-09-01 cutover.
    monday = datetime(2025, 8, 25, 10, 0)
    assert next_weekly_expiry_days(monday) == 3.0


def test_is_expiry_day_before_the_change_uses_thursday_not_tuesday():
    # 2025-08-28 is the last Thursday before the cutover; 2025-08-26 is the Tuesday of that same week.
    assert is_expiry_day(datetime(2025, 8, 28, 10, 0)) is True  # Thursday, old regime
    assert is_expiry_day(datetime(2025, 8, 26, 10, 0)) is False  # Tuesday, not yet the expiry day


def test_is_expiry_day_right_at_the_cutover():
    assert is_expiry_day(datetime(2025, 9, 2, 10, 0)) is True  # first Tuesday expiry, new regime
    assert is_expiry_day(datetime(2025, 9, 4, 10, 0)) is False  # that week's Thursday, no longer expiry


# ---- next_weekly_expiry_date / format_display_symbol (display-only contract naming) ----------

def test_next_weekly_expiry_date_on_a_monday_counts_forward_to_tuesday():
    monday = datetime(2026, 8, 3, 10, 0)  # 2026-08-03 is a Monday
    assert next_weekly_expiry_date(monday) == date(2026, 8, 4)


def test_next_weekly_expiry_date_on_expiry_day_before_close_is_today():
    assert next_weekly_expiry_date(datetime(2026, 8, 4, 9, 20)) == date(2026, 8, 4)


def test_next_weekly_expiry_date_on_expiry_day_after_close_rolls_to_next_week():
    assert next_weekly_expiry_date(datetime(2026, 8, 4, 16, 0)) == date(2026, 8, 11)


def test_format_display_symbol_embeds_the_expiry_date():
    assert format_display_symbol("NIFTY22400PE", date(2026, 8, 11)) == "NIFTY11Aug202622400PE"
    assert format_display_symbol("NIFTY24600CE", date(2026, 1, 6)) == "NIFTY06Jan202624600CE"


def test_format_display_symbol_passes_through_unparseable_symbols_unchanged():
    assert format_display_symbol("garbage", date(2026, 8, 11)) == "garbage"
