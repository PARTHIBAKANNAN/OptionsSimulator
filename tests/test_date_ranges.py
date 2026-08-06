from datetime import date, datetime

import pytest

from src.utils.date_ranges import IST, resolve_range


# 2026-08-06 is a Thursday.
NOW = datetime(2026, 8, 6, 12, 0, tzinfo=IST)


def test_today():
    assert resolve_range("today", now=NOW) == (date(2026, 8, 6), date(2026, 8, 6))


def test_yesterday():
    assert resolve_range("yesterday", now=NOW) == (date(2026, 8, 5), date(2026, 8, 5))


def test_this_week_runs_monday_through_today_not_into_the_future():
    assert resolve_range("this_week", now=NOW) == (date(2026, 8, 3), date(2026, 8, 6))


def test_last_week_is_the_full_prior_monday_through_sunday():
    assert resolve_range("last_week", now=NOW) == (date(2026, 7, 27), date(2026, 8, 2))


def test_this_month_runs_first_of_month_through_today():
    assert resolve_range("this_month", now=NOW) == (date(2026, 8, 1), date(2026, 8, 6))


def test_30d_is_30_calendar_days_inclusive_of_today():
    start, end = resolve_range("30d", now=NOW)
    assert end == date(2026, 8, 6)
    assert (end - start).days == 29  # 30 days total, inclusive on both ends


def test_60d_and_90d():
    assert (date(2026, 8, 6) - resolve_range("60d", now=NOW)[0]).days == 59
    assert (date(2026, 8, 6) - resolve_range("90d", now=NOW)[0]).days == 89


def test_custom_range_passes_through_given_dates():
    start, end = date(2026, 1, 1), date(2026, 1, 15)
    assert resolve_range("custom", start=start, end=end) == (start, end)


def test_custom_range_requires_both_start_and_end():
    with pytest.raises(ValueError, match="requires both"):
        resolve_range("custom", start=date(2026, 1, 1))
    with pytest.raises(ValueError, match="requires both"):
        resolve_range("custom", end=date(2026, 1, 1))


def test_custom_range_rejects_start_after_end():
    with pytest.raises(ValueError, match="start must not be after end"):
        resolve_range("custom", start=date(2026, 1, 15), end=date(2026, 1, 1))


def test_unknown_range_key_rejected():
    with pytest.raises(ValueError, match="Unknown range"):
        resolve_range("last_year")


def test_defaults_to_real_current_time_when_now_not_given():
    # Just confirm it doesn't blow up and returns a sane (start <= end) pair using the real clock.
    start, end = resolve_range("this_week")
    assert start <= end
